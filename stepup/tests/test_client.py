from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from stepup import client

from .support import http_error


@override_settings(VONAGE_BRAND_NAME="Setlist")
class StartVerificationTests(SimpleTestCase):
    def test_returns_request_id(self):
        vonage = MagicMock()
        vonage.verify.start_verification.return_value.request_id = "abc-123"

        with patch.object(client, "get_client", return_value=vonage):
            self.assertEqual(client.start_verification("447700900000"), "abc-123")

    def test_sends_a_six_digit_sms_code_to_the_number(self):
        vonage = MagicMock()
        vonage.verify.start_verification.return_value.request_id = "abc-123"

        with patch.object(client, "get_client", return_value=vonage):
            client.start_verification("447700900000")

        request = vonage.verify.start_verification.call_args.args[0]
        self.assertEqual(request.brand, "Setlist")
        self.assertEqual(request.code_length, 6)
        self.assertEqual(request.workflow[0].to, "447700900000")

    def test_concurrent_request_explains_a_code_is_already_on_its_way(self):
        with self._failing(409):
            with self.assertRaises(client.VerificationError) as ctx:
                client.start_verification("447700900000")

        self.assertIn("already a code", ctx.exception.message)

    def test_bad_number_blames_the_number(self):
        with self._failing(422):
            with self.assertRaises(client.VerificationError) as ctx:
                client.start_verification("447700900000")

        self.assertIn("country code", ctx.exception.message)

    def test_credentials_failure_is_not_explained_to_the_user(self):
        with self._failing(401):
            with self.assertRaises(client.VerificationError) as ctx:
                client.start_verification("447700900000")

        message = ctx.exception.message.lower()
        self.assertNotIn("auth", message)
        self.assertNotIn("credential", message)
        self.assertIn("try again later", message)

    @contextmanager
    def _failing(self, status_code):
        """Fail the API call, and assert we logged it on the way past."""
        vonage = MagicMock()
        vonage.verify.start_verification.side_effect = http_error(status_code)
        with self.assertLogs("stepup.client", "WARNING"):
            with patch.object(client, "get_client", return_value=vonage):
                yield


class CheckCodeTests(SimpleTestCase):
    def test_correct_code_returns_without_raising(self):
        vonage = MagicMock()
        with patch.object(client, "get_client", return_value=vonage):
            client.check_code("abc-123", "123456")

        vonage.verify.check_code.assert_called_once_with(request_id="abc-123", code="123456")

    def test_wrong_code_lets_the_user_try_again(self):
        with self._failing(400):
            with self.assertRaises(client.VerificationError) as ctx:
                client.check_code("abc-123", "000000")

        self.assertFalse(ctx.exception.restart)

    def test_expired_request_forces_a_new_code(self):
        with self._failing(404):
            with self.assertRaises(client.VerificationError) as ctx:
                client.check_code("abc-123", "123456")

        self.assertTrue(ctx.exception.restart)
        self.assertIn("expired", ctx.exception.message)

    def test_too_many_attempts_forces_a_new_code(self):
        with self._failing(410):
            with self.assertRaises(client.VerificationError) as ctx:
                client.check_code("abc-123", "123456")

        self.assertTrue(ctx.exception.restart)
        self.assertIn("Too many incorrect attempts", ctx.exception.message)

    def test_rate_limit_is_temporary_not_fatal(self):
        with self._failing(429):
            with self.assertRaises(client.VerificationError) as ctx:
                client.check_code("abc-123", "123456")

        self.assertFalse(ctx.exception.restart)

    @contextmanager
    def _failing(self, status_code):
        """Fail the API call, and assert we logged it on the way past."""
        vonage = MagicMock()
        vonage.verify.check_code.side_effect = http_error(status_code)
        with self.assertLogs("stepup.client", "WARNING"):
            with patch.object(client, "get_client", return_value=vonage):
                yield
