from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse

from . import session


class VerificationRequiredMixin(LoginRequiredMixin):
    """Require a recent verification before this view runs.

    Drop it onto the handful of views that do something irreversible. It extends
    `LoginRequiredMixin`, so an anonymous visitor is sent to log in and a signed-in
    visitor is sent to verify. Those are two different problems with two different
    answers, which is why this is not one `UserPassesTestMixin` test with a branch
    inside it.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not session.is_verified(request.session):
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('stepup:start')}?{query}")
        return super().dispatch(request, *args, **kwargs)
