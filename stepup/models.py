from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

# Vonage wants numbers in E.164 without the leading "+": country code followed by
# the subscriber number, digits only. Validating here means a typo fails in the form
# rather than as an HTTP 422 from the API.
e164 = RegexValidator(
    regex=r"^[1-9]\d{6,14}$",
    message="Enter your number in international format, digits only, e.g. 447700900000.",
)


class VerifiedPhone(models.Model):
    """The phone number we send verification codes to.

    Kept in its own app rather than on a custom user model so that adding step-up
    verification to an existing project is a migration, not a rewrite.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verified_phone",
    )
    number = models.CharField(max_length=15, validators=[e164])
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set the first time a code sent to this number is accepted.",
    )

    def __str__(self):
        return f"{self.user}: {self.masked_number}"

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None

    @property
    def masked_number(self):
        """Show enough of the number to be recognisable, not enough to be useful."""
        return f"•••••• {self.number[-4:]}" if len(self.number) >= 4 else "••••••"
