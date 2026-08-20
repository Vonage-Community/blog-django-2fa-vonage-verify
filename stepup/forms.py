import re

from django import forms

from .models import e164

# Everything people type around a phone number that is decoration, not digits.
DECORATION = re.compile(r"[\s()\-.]")


class PhoneNumberField(forms.CharField):
    """A CharField that normalizes before it validates.

    The order matters. Django runs `to_python()`, then the field validators, then
    `clean_<field>()` on the form. Normalizing in `clean_number()` would be too late:
    the E.164 validator would already have rejected `+44 7700 900000`, a number that
    is perfectly fine once you take the spaces out.
    """

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return DECORATION.sub("", value).lstrip("+")


class PhoneNumberForm(forms.Form):
    """Collects the number a first-time user wants codes sent to."""

    number = PhoneNumberField(
        max_length=15,
        validators=[e164],
        label="Mobile number",
        help_text="International format, digits only. For example 447700900000.",
        widget=forms.TextInput(
            attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "447700900000"}
        ),
    )


class CodeForm(forms.Form):
    """Collects the code from the SMS."""

    code = forms.CharField(
        min_length=4,
        max_length=10,
        label="Verification code",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                # Lets iOS and Android offer the code straight from the SMS.
                "autocomplete": "one-time-code",
                "autofocus": "autofocus",
            }
        ),
    )

    def clean_code(self):
        return DECORATION.sub("", self.cleaned_data["code"])
