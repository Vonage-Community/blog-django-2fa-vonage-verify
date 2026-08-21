from django.conf import settings
from django.db import models
from django.urls import reverse


class Event(models.Model):
    """A show someone can hold a ticket to."""

    artist = models.CharField(max_length=120)
    venue = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    starts_at = models.DateTimeField()

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return f"{self.artist} at {self.venue}"


class Ticket(models.Model):
    """A single seat, owned by exactly one user at a time."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets"
    )
    section = models.CharField(max_length=40)
    seat = models.CharField(max_length=10)
    face_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="What the ticket cost. Shown on the transfer screen so the person "
        "giving it away can see what they are giving away.",
    )

    class Meta:
        ordering = ["event__starts_at", "section", "seat"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "section", "seat"], name="unique_seat_per_event"
            )
        ]

    def __str__(self):
        return f"{self.event} — {self.section} {self.seat}"

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.pk])

    @property
    def reference(self):
        """A quotable order reference for the ticket stub."""
        return f"SL-{self.pk:06d}"


class Transfer(models.Model):
    """An audit record of a ticket changing hands.

    Transfers are the reason this app has two-factor authentication at all: they
    move something of value out of an account and cannot be undone by the sender.
    Recording who moved what, when, and from which verified session is part of
    making that defensible after the fact.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="transfers")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="transfers_sent"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verification_request_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="The Vonage Verify request that authorized this transfer.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket} → {self.recipient}"
