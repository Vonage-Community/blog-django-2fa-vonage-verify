from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class TransferForm(forms.Form):
    """Hand a ticket to another Setlist user."""

    username = forms.CharField(
        max_length=150,
        label="Send to",
        help_text="The username of the person receiving the ticket.",
    )

    def __init__(self, *args, sender=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender = sender

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if self.sender and username.lower() == self.sender.username.lower():
            raise forms.ValidationError("You already hold this ticket.")

        try:
            recipient = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No Setlist user with that username.") from None

        self.recipient = recipient
        return username
