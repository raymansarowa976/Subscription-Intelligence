from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


@login_required
def dashboard_view(request):
    if not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("accounts:verify_token")
    return render(request, "subscriptions/dashboard.html")
