from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from . import client, session
from .forms import CodeForm, PhoneNumberForm
from .models import VerifiedPhone


class StartVerificationView(LoginRequiredMixin, View):
    """Step one: settle on a number, then ask Vonage to send a code to it.

    A user who has already confirmed a number does not get to type a new one here.
    Letting someone change the destination of their own second factor while holding
    only the first factor removes the second factor.
    """

    template_name = "stepup/start.html"

    def get(self, request):
        phone = _confirmed_phone(request.user)
        form = None if phone else PhoneNumberForm()
        return render(request, self.template_name, self._context(request, phone, form))

    def post(self, request):
        phone = _confirmed_phone(request.user)
        form = None

        if phone:
            number = phone.number
        else:
            form = PhoneNumberForm(request.POST)
            if not form.is_valid():
                return render(request, self.template_name, self._context(request, phone, form))
            number = form.cleaned_data["number"]

        try:
            request_id = client.start_verification(number)
        except client.VerificationError as err:
            messages.error(request, err.message)
            return render(request, self.template_name, self._context(request, phone, form))

        session.start_pending(request.session, request_id, number)
        return redirect(_with_next(reverse("stepup:check"), session.safe_next(request)))

    def _context(self, request, phone, form):
        return {"form": form, "phone": phone, "next": session.safe_next(request)}


class CheckCodeView(LoginRequiredMixin, View):
    """Step two: submit the code the user received."""

    template_name = "stepup/check.html"

    def get(self, request):
        if not session.pending_request_id(request.session):
            return redirect(_with_next(reverse("stepup:start"), session.safe_next(request)))
        return render(request, self.template_name, self._context(request, CodeForm()))

    def post(self, request):
        request_id = session.pending_request_id(request.session)
        if not request_id:
            messages.error(request, "That verification is no longer active. Request a new code.")
            return redirect(_with_next(reverse("stepup:start"), session.safe_next(request)))

        form = CodeForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._context(request, form))

        try:
            client.check_code(request_id, form.cleaned_data["code"])
        except client.VerificationError as err:
            messages.error(request, err.message)
            if err.restart:
                session.clear(request.session)
                return redirect(_with_next(reverse("stepup:start"), session.safe_next(request)))
            return render(request, self.template_name, self._context(request, form))

        number = session.pending_number(request.session)
        redirect_to = session.safe_next(request)

        # Rotate the session key on a successful second factor, the same way Django
        # does on login. A session ID captured before the step-up is useless after it.
        request.session.cycle_key()
        _remember_number(request.user, number)
        session.mark_verified(request.session, request_id)
        return redirect(redirect_to)

    def _context(self, request, form):
        return {
            "form": form,
            "masked_number": _mask(session.pending_number(request.session)),
            "next": session.safe_next(request),
        }


def _confirmed_phone(user):
    """The user's confirmed number, or None if they have never completed a check."""
    return VerifiedPhone.objects.filter(user=user, confirmed_at__isnull=False).first()


def _remember_number(user, number):
    """Store the number on first successful verification, then leave it alone.

    `confirmed_at` records when the number was first proven, not when it was last
    used, so a later re-verification must not move it.
    """
    if not number:
        return
    VerifiedPhone.objects.get_or_create(
        user=user,
        defaults={"number": number, "confirmed_at": timezone.now()},
    )


def _mask(number):
    return f"•••••• {number[-4:]}" if number and len(number) >= 4 else "your number"


def _with_next(path, next_url):
    return f"{path}?{urlencode({'next': next_url})}" if next_url else path
