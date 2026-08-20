"""Helpers for faking Vonage responses.

No test in this suite touches the network. `HttpRequestError` only needs a response
object with a status code and a body, so a real `requests.Response` built by hand is
closer to the truth than a mock and costs nothing.
"""

from json import dumps

from requests import Response
from vonage_http_client.errors import HttpRequestError, NotFoundError, RateLimitedError


def http_error(status_code, title="error"):
    """Build the exception the Vonage SDK would raise for a given status code."""
    response = Response()
    response.status_code = status_code
    response.url = "https://api.nexmo.com/v2/verify"
    response._content = dumps({"title": title}).encode()

    if status_code == 404:
        return NotFoundError(response)
    if status_code == 429:
        return RateLimitedError(response)
    return HttpRequestError(response)
