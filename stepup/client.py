"""A thin wrapper around the Vonage Verify v2 API.

Everything the rest of the app knows about Vonage lives in this module. Views call
`start_verification()` and `check_code()`, and get either a result or a
`VerificationError` carrying a message that is safe to show a user.

Why Verify rather than rolling your own OTP: the API owns code generation, code
length, expiry, delivery, retries, the attempt limit, and channel fallback. There
is no `codes` table in this project and no cleanup job, because there is nothing
of ours to expire.
"""

import logging

from django.conf import settings
from pydantic import ValidationError
from vonage import Auth, Vonage
from vonage_http_client.errors import HttpRequestError
from vonage_verify import SmsChannel, VerifyRequest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_client = None


class VerificationError(Exception):
    """A Verify failure with a message intended for the end user.

    `restart` distinguishes "try typing the code again" from "that request is dead,
    go back and request a new code".
    """

    def __init__(self, message, restart=False):
        super().__init__(message)
        self.message = message
        self.restart = restart


def get_client():
    """Build the Vonage client once and reuse it.

    Verify v2 accepts either JWT or Basic authentication. Passing an API key and
    secret selects Basic, which keeps this demo to two environment variables and no
    private key file. For production, application ID plus private key is the better
    default, and it is what you need if you want asynchronous status callbacks.
    """
    global _client
    if _client is None:
        _client = Vonage(
            Auth(
                api_key=settings.VONAGE_API_KEY,
                api_secret=settings.VONAGE_API_SECRET,
            )
        )
    return _client


def start_verification(number):
    """Ask Vonage to send a code to `number`. Returns the request ID.

    The workflow list is ordered. A single SMS channel covers the common case. Add a
    `VoiceChannel(to=number)` after it and Vonage reads the code out over a phone
    call if the SMS has not been acted on within `channel_timeout` seconds.
    """
    try:
        # The SDK models are Pydantic, so a badly shaped number fails here rather
        # than costing a round trip. It raises ValidationError, not HttpRequestError.
        request = VerifyRequest(
            brand=settings.VONAGE_BRAND_NAME,
            code_length=6,
            workflow=[SmsChannel(to=number)],
        )
    except ValidationError as err:
        raise VerificationError(
            "That number does not look right. Check the country code and try again.",
            restart=True,
        ) from err

    try:
        logger.info("Starting verification process ...")
        response = get_client().verify.start_verification(request)
    except HttpRequestError as err:
        raise VerificationError(_start_message(err), restart=True) from err

    return response.request_id


def check_code(request_id, code):
    """Submit a code for `request_id`. Returns None on success, raises otherwise."""
    try:
        logger.info("Checking code for request %s", request_id)
        get_client().verify.check_code(request_id=request_id, code=code)
    except HttpRequestError as err:
        message, restart = _check_message(err)
        raise VerificationError(message, restart=restart) from err


def cancel_verification(request_id):
    """Abandon an in-flight request, e.g. when the user goes back to edit a number.

    Best effort: if the request already completed or expired there is nothing to
    cancel and nothing the user needs to know about it.
    """
    try:
        logger.info("Canceling verification for request %s", request_id)
        get_client().verify.cancel_verification(request_id)
    except HttpRequestError:
        logger.info("Could not cancel Verify request %s", request_id, exc_info=True)


def _status(err):
    return getattr(err.response, "status_code", None)


def _start_message(err):
    status = _status(err)
    logger.warning("Verify start failed with HTTP %s: %s", status, err)

    if status == 409:
        return (
            "There is already a code on its way to that number. "
            "Wait for it to arrive, or try again in a minute."
        )
    if status == 422:
        return "That number does not look right. Check the country code and try again."
    if status == 429:
        return "Too many requests from this account right now. Try again in a moment."
    if status in (401, 403):
        # A credentials problem is ours, not the user's. Do not leak the detail.
        return "We could not send a code just now. Please try again later."
    return "We could not send a code to that number. Please try again."


def _check_message(err):
    status = _status(err)
    logger.warning("Verify check failed with HTTP %s: %s", status, err)

    if status == 400:
        return "That code is not right. Check the message and try again.", False
    if status == 404:
        return "That code has expired. Request a new one.", True
    if status == 410:
        # Verify enforces the attempt limit for us and retires the request.
        return "Too many incorrect attempts. Request a new code.", True
    if status == 429:
        return "Too many attempts right now. Try again in a moment.", False
    return "We could not check that code. Request a new one.", True
