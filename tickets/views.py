from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import DetailView, ListView

from stepup import session
from stepup.mixins import VerificationRequiredMixin

from .forms import TransferForm
from .models import Event, Ticket, Transfer


class EventListView(ListView):
    """The public front page. No login, no verification — nothing is at stake here."""

    model = Event
    template_name = "tickets/event_list.html"
    context_object_name = "events"


class TicketListView(LoginRequiredMixin, ListView):
    """Your tickets. Signing in is enough to look at what you own."""

    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user).select_related("event")


class TicketDetailView(LoginRequiredMixin, DetailView):
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        # Scoping by owner means a wrong ticket ID is a 404, not someone else's seat.
        return Ticket.objects.filter(owner=self.request.user).select_related("event")


class TicketTransferView(VerificationRequiredMixin, View):
    """Give a ticket away. This is the view the second factor exists for.

    Everything above this line is readable with a password. This one moves an asset
    out of the account and the sender cannot take it back, so it asks for proof that
    whoever is driving the session still holds the phone.
    """

    template_name = "tickets/ticket_transfer.html"

    @cached_property
    def ticket(self):
        """Load the ticket lazily, from `get()`/`post()`, never from `dispatch()`.

        The access mixins do their work in `dispatch()`. Fetching the object there
        too — as an earlier draft of this view did — runs the ownership filter
        against `AnonymousUser`, and a visitor who should have been sent to the login
        page gets a 404 instead.
        """
        return get_object_or_404(
            Ticket.objects.select_related("event"),
            pk=self.kwargs["pk"],
            owner=self.request.user.pk,
        )

    def get(self, request, pk):
        return render(request, self.template_name, self._context(TransferForm(sender=request.user)))

    def post(self, request, pk):
        form = TransferForm(request.POST, sender=request.user)
        if not form.is_valid():
            return render(request, self.template_name, self._context(form))

        with transaction.atomic():
            Transfer.objects.create(
                ticket=self.ticket,
                sender=request.user,
                recipient=form.recipient,
                verification_request_id=session.last_request_id(request.session),
            )
            self.ticket.owner = form.recipient
            self.ticket.save(update_fields=["owner"])

        # One verification, one transfer. Leaving the session verified would let a
        # single code authorise every ticket in the account.
        session.clear(request.session)

        messages.success(request, f"{self.ticket.event.artist} is on its way to {form.recipient.username}.")
        return redirect(reverse("tickets:list"))

    def _context(self, form):
        return {
            "form": form,
            "ticket": self.ticket,
            "seconds_remaining": session.seconds_remaining(self.request.session),
        }
