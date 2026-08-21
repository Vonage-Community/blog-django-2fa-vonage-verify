"""Create the demo accounts, shows, and tickets.

Run with `python manage.py seed_demo`. Safe to run more than once.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import Event, Ticket

User = get_user_model()

DEMO_PASSWORD = "setlist-demo"

SHOWS = [
    ("Sylvan Wake", "Paradiso", "Amsterdam", 12, [("Floor", "A12", 145), ("Floor", "A13", 145)]),
    ("Neon Cartographer", "Village Underground", "London", 26, [("Balcony", "C4", 88)]),
    ("The Long Wave", "Barby", "Tel Aviv", 41, [("Standing", "GA", 62)]),
]


class Command(BaseCommand):
    help = "Load demo users, events, and tickets."

    def handle(self, *args, **options):
        owner = self._user("ada")
        self._user("grace")

        now = timezone.now()
        for artist, venue, city, days, seats in SHOWS:
            event, _ = Event.objects.get_or_create(
                artist=artist,
                venue=venue,
                defaults={"city": city, "starts_at": now + timedelta(days=days)},
            )
            for section, seat, face_value in seats:
                Ticket.objects.get_or_create(
                    event=event,
                    section=section,
                    seat=seat,
                    defaults={"owner": owner, "face_value": face_value},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready. Sign in as 'ada' or 'grace' with password '{DEMO_PASSWORD}'."
            )
        )

    def _user(self, username):
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
        return user
