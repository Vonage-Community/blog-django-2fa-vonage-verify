from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from stepup import client, session
from stepup.models import VerifiedPhone

User = get_user_model()


@override_settings(STEP_UP_TTL_SECONDS=300)
class StartVerificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="setlist-demo")
        self.client.force_login(self.user)

    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.client.logout()
        response = self.client.get(reverse("stepup:start"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_first_time_user_is_asked_for_a_number(self):
        response = self.client.get(reverse("stepup:start"))
        self.assertContains(response, "Mobile number")

    def test_posting_a_number_starts_a_verification(self):
        with patch.object(client, "start_verification", return_value="abc-123") as start:
            response = self.client.post(
                reverse("stepup:start"),
                {"number": "+44 7700 900000", "next": "/tickets/1/transfer/"},
            )

        start.assert_called_once_with("447700900000")
        self.assertEqual(self.client.session[session.REQUEST_ID_KEY], "abc-123")
        self.assertIn(reverse("stepup:check"), response.url)
        self.assertIn("next=%2Ftickets%2F1%2Ftransfer%2F", response.url)

    def test_an_unverified_number_is_not_stored(self):
        """The number only becomes ours once a code sent to it comes back correct."""
        with patch.object(client, "start_verification", return_value="abc-123"):
            self.client.post(reverse("stepup:start"), {"number": "447700900000"})

        self.assertFalse(VerifiedPhone.objects.exists())

    def test_a_malformed_number_never_reaches_the_api(self):
        with patch.object(client, "start_verification") as start:
            response = self.client.post(reverse("stepup:start"), {"number": "nope"})

        start.assert_not_called()
        self.assertContains(response, "international format")

    def test_a_confirmed_user_cannot_redirect_codes_to_a_new_number(self):
        VerifiedPhone.objects.create(
            user=self.user, number="447700900000", confirmed_at="2026-01-01T00:00:00Z"
        )

        with patch.object(client, "start_verification", return_value="abc-123") as start:
            self.client.post(reverse("stepup:start"), {"number": "15550000000"})

        start.assert_called_once_with("447700900000")

    def test_an_api_failure_is_shown_and_the_flow_stops(self):
        error = client.VerificationError("There is already a code on its way.", restart=True)
        with patch.object(client, "start_verification", side_effect=error):
            response = self.client.post(reverse("stepup:start"), {"number": "447700900000"})

        self.assertContains(response, "already a code on its way")
        self.assertNotIn(session.REQUEST_ID_KEY, self.client.session)


@override_settings(STEP_UP_TTL_SECONDS=300)
class CheckCodeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="setlist-demo")
        self.client.force_login(self.user)
        self._start_pending()

    def _start_pending(self, request_id="abc-123", number="447700900000"):
        store = self.client.session
        session.start_pending(store, request_id, number)
        store.save()

    def test_without_a_pending_request_the_user_is_sent_back_to_the_start(self):
        store = self.client.session
        session.clear(store)
        store.save()

        response = self.client.get(reverse("stepup:check"))
        self.assertIn(reverse("stepup:start"), response.url)

    def test_the_masked_number_is_shown_not_the_whole_thing(self):
        response = self.client.get(reverse("stepup:check"))
        self.assertContains(response, "0000")
        self.assertNotContains(response, "447700900000")

    def test_a_correct_code_verifies_the_session_and_returns_the_user(self):
        with patch.object(client, "check_code") as check:
            response = self.client.post(
                reverse("stepup:check"), {"code": "123 456", "next": "/tickets/1/transfer/"}
            )

        check.assert_called_once_with("abc-123", "123456")
        self.assertRedirects(response, "/tickets/1/transfer/", fetch_redirect_response=False)
        self.assertTrue(session.is_verified(self.client.session))

    def test_a_correct_code_confirms_the_number_for_next_time(self):
        with patch.object(client, "check_code"):
            self.client.post(reverse("stepup:check"), {"code": "123456"})

        phone = VerifiedPhone.objects.get(user=self.user)
        self.assertEqual(phone.number, "447700900000")
        self.assertTrue(phone.is_confirmed)

    def test_a_wrong_code_keeps_the_user_on_the_page_to_retry(self):
        error = client.VerificationError("That code is not right.", restart=False)
        with patch.object(client, "check_code", side_effect=error):
            response = self.client.post(reverse("stepup:check"), {"code": "000000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That code is not right")
        self.assertFalse(session.is_verified(self.client.session))
        self.assertEqual(self.client.session[session.REQUEST_ID_KEY], "abc-123")

    def test_a_dead_request_sends_the_user_back_for_a_new_code(self):
        error = client.VerificationError("That code has expired.", restart=True)
        with patch.object(client, "check_code", side_effect=error):
            response = self.client.post(reverse("stepup:check"), {"code": "123456"})

        self.assertIn(reverse("stepup:start"), response.url)
        self.assertNotIn(session.REQUEST_ID_KEY, self.client.session)

    def test_verification_does_not_follow_next_off_site(self):
        with patch.object(client, "check_code"):
            response = self.client.post(
                reverse("stepup:check"), {"code": "123456", "next": "https://evil.example/"}
            )

        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_the_session_key_is_rotated_after_a_successful_step_up(self):
        before = self.client.session.session_key

        with patch.object(client, "check_code"):
            self.client.post(reverse("stepup:check"), {"code": "123456"})

        self.assertNotEqual(self.client.session.session_key, before)
