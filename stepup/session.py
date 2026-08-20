"""Where a step-up verification lives between requests.

Two deliberate choices here:

1. Verification is stored on the **session**, not the user. The same person signed
   in on a laptop and a phone has two sessions, and verifying one does not verify
   the other.
2. It **expires**. A boolean flag set once and never cleared is not step-up
   authentication, it is a slightly slower login.
"""

import time

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

VERIFIED_AT_KEY = "stepup_verified_at"
REQUEST_ID_KEY = "stepup_request_id"
NUMBER_KEY = "stepup_number"
LAST_REQUEST_ID_KEY = "stepup_last_request_id"


def mark_verified(session, request_id=""):
    """Record that this session just passed a verification."""
    session[VERIFIED_AT_KEY] = time.time()
    session.pop(REQUEST_ID_KEY, None)
    session.pop(NUMBER_KEY, None)
    if request_id:
        session[LAST_REQUEST_ID_KEY] = request_id


def is_verified(session):
    """True if this session verified recently enough to still count."""
    verified_at = session.get(VERIFIED_AT_KEY)
    if not verified_at:
        return False
    return (time.time() - verified_at) < settings.STEP_UP_TTL_SECONDS


def seconds_remaining(session):
    verified_at = session.get(VERIFIED_AT_KEY)
    if not verified_at:
        return 0
    return max(0, int(settings.STEP_UP_TTL_SECONDS - (time.time() - verified_at)))


def clear(session):
    for key in (VERIFIED_AT_KEY, REQUEST_ID_KEY, NUMBER_KEY, LAST_REQUEST_ID_KEY):
        session.pop(key, None)


def start_pending(session, request_id, number):
    """Remember the in-flight Verify request so the check view can complete it."""
    session[REQUEST_ID_KEY] = request_id
    session[NUMBER_KEY] = number


def pending_request_id(session):
    return session.get(REQUEST_ID_KEY)


def pending_number(session):
    return session.get(NUMBER_KEY)


def last_request_id(session):
    """The Verify request that authorised the current verification, for audit records."""
    return session.get(LAST_REQUEST_ID_KEY, "")


def safe_next(request, fallback="/"):
    """Return the ?next= target only if it points back at this site.

    Django's login view does this and so must anything else that redirects to a
    user-supplied URL. Without the check, `?next=https://evil.example` turns your
    verification flow into an open redirect — a credible-looking link on your own
    domain that lands the user somewhere else entirely.
    """
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback
