import time
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from stepup import session


@override_settings(STEP_UP_TTL_SECONDS=300)
class VerificationFreshnessTests(SimpleTestCase):
    def test_a_new_session_is_not_verified(self):
        self.assertFalse(session.is_verified({}))

    def test_marking_verified_makes_it_verified(self):
        store = {}
        session.mark_verified(store, "abc-123")
        self.assertTrue(session.is_verified(store))

    def test_verification_expires(self):
        store = {}
        with patch.object(time, "time", return_value=1_000.0):
            session.mark_verified(store)

        with patch.object(time, "time", return_value=1_000.0 + 301):
            self.assertFalse(session.is_verified(store))

    def test_verification_survives_up_to_the_ttl(self):
        store = {}
        with patch.object(time, "time", return_value=1_000.0):
            session.mark_verified(store)

        with patch.object(time, "time", return_value=1_000.0 + 299):
            self.assertTrue(session.is_verified(store))
            self.assertEqual(session.seconds_remaining(store), 1)

    def test_marking_verified_clears_the_in_flight_request(self):
        store = {}
        session.start_pending(store, "abc-123", "447700900000")
        session.mark_verified(store, "abc-123")

        self.assertIsNone(session.pending_request_id(store))
        self.assertIsNone(session.pending_number(store))

    def test_clear_revokes_verification(self):
        store = {}
        session.mark_verified(store)
        session.clear(store)
        self.assertFalse(session.is_verified(store))


class SafeNextTests(SimpleTestCase):
    """`?next=` is user input. It gets validated before anything redirects to it."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_allows_a_relative_path(self):
        request = self.factory.get("/verify/", {"next": "/tickets/3/transfer/"})
        self.assertEqual(session.safe_next(request), "/tickets/3/transfer/")

    def test_rejects_another_host(self):
        request = self.factory.get("/verify/", {"next": "https://evil.example/phish"})
        self.assertEqual(session.safe_next(request), "/")

    def test_rejects_a_protocol_relative_url(self):
        request = self.factory.get("/verify/", {"next": "//evil.example/phish"})
        self.assertEqual(session.safe_next(request), "/")

    def test_falls_back_when_absent(self):
        self.assertEqual(session.safe_next(self.factory.get("/verify/")), "/")

    def test_post_wins_over_querystring(self):
        request = self.factory.post("/verify/?next=/a/", {"next": "/b/"})
        self.assertEqual(session.safe_next(request), "/b/")
