from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from stepup import session
from tickets.models import Event, Ticket, Transfer

User = get_user_model()


@override_settings(STEP_UP_TTL_SECONDS=300)
class TransferAccessTests(TestCase):
    """Which views the second factor guards, and which it deliberately does not."""

    def setUp(self):
        self.ada = User.objects.create_user("ada", password="setlist-demo")
        self.grace = User.objects.create_user("grace", password="setlist-demo")
        self.event = Event.objects.create(
            artist="Sylvan Wake",
            venue="Paradiso",
            city="Amsterdam",
            starts_at=timezone.now() + timedelta(days=12),
        )
        self.ticket = Ticket.objects.create(
            event=self.event, owner=self.ada, section="Floor", seat="A12"
        )
        self.url = reverse("tickets:transfer", args=[self.ticket.pk])

    def _verify(self):
        store = self.client.session
        session.mark_verified(store, "abc-123")
        store.save()

    def test_reading_your_own_tickets_needs_only_a_password(self):
        self.client.force_login(self.ada)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, "Sylvan Wake")

    def test_an_anonymous_visitor_is_sent_to_log_in_not_to_verify(self):
        response = self.client.get(self.url)
        self.assertIn(reverse("login"), response.url)

    def test_a_signed_in_user_without_verification_is_sent_to_verify(self):
        self.client.force_login(self.ada)
        response = self.client.get(self.url)

        self.assertIn(reverse("stepup:start"), response.url)
        self.assertIn("next=", response.url)

    def test_a_verified_user_reaches_the_transfer_form(self):
        self.client.force_login(self.ada)
        self._verify()

        response = self.client.get(self.url)
        self.assertContains(response, "Transfer your ticket")

    def test_a_stale_verification_does_not_count(self):
        self.client.force_login(self.ada)
        self._verify()

        store = self.client.session
        store[session.VERIFIED_AT_KEY] -= 301
        store.save()

        response = self.client.get(self.url)
        self.assertIn(reverse("stepup:start"), response.url)

    def test_you_cannot_transfer_a_ticket_you_do_not_hold(self):
        self.client.force_login(self.grace)
        self._verify()

        self.assertEqual(self.client.get(self.url).status_code, 404)


@override_settings(STEP_UP_TTL_SECONDS=300)
class TransferTests(TestCase):
    def setUp(self):
        self.ada = User.objects.create_user("ada", password="setlist-demo")
        self.grace = User.objects.create_user("grace", password="setlist-demo")
        self.event = Event.objects.create(
            artist="Sylvan Wake",
            venue="Paradiso",
            city="Amsterdam",
            starts_at=timezone.now() + timedelta(days=12),
        )
        self.ticket = Ticket.objects.create(
            event=self.event, owner=self.ada, section="Floor", seat="A12"
        )
        self.url = reverse("tickets:transfer", args=[self.ticket.pk])

        self.client.force_login(self.ada)
        store = self.client.session
        session.mark_verified(store, "abc-123")
        store.save()

    def test_a_transfer_moves_the_ticket(self):
        self.client.post(self.url, {"username": "grace"})

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.owner, self.grace)

    def test_a_transfer_records_which_verification_authorised_it(self):
        self.client.post(self.url, {"username": "grace"})

        transfer = Transfer.objects.get()
        self.assertEqual(transfer.sender, self.ada)
        self.assertEqual(transfer.recipient, self.grace)
        self.assertEqual(transfer.verification_request_id, "abc-123")

    def test_one_verification_authorises_exactly_one_transfer(self):
        second = Ticket.objects.create(
            event=self.event, owner=self.ada, section="Floor", seat="A13"
        )
        self.client.post(self.url, {"username": "grace"})

        response = self.client.get(reverse("tickets:transfer", args=[second.pk]))
        self.assertIn(reverse("stepup:start"), response.url)

    def test_an_unknown_recipient_leaves_the_ticket_alone(self):
        response = self.client.post(self.url, {"username": "nobody"})

        self.assertContains(response, "No Setlist user with that username")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.owner, self.ada)

    def test_you_cannot_transfer_a_ticket_to_yourself(self):
        response = self.client.post(self.url, {"username": "ada"})

        self.assertContains(response, "You already hold this ticket")
        self.assertFalse(Transfer.objects.exists())
