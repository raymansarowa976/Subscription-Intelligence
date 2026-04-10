from django.contrib.auth.views import LoginView
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages

from .forms import SignupForm
from .authentication_forms import SubscriptionAuthenticationForm

User = get_user_model()


class SubscriptionLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    authentication_form = SubscriptionAuthenticationForm

    def get_success_url(self):
        return reverse("dashboard")


def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        user.is_active = False
        user.save(update_fields=['is_active'])

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        link = request.build_absolute_uri(
            reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        )

        send_mail(
            'Activate your account',
            f'Please click the link to verify your email: {link}',
            'noreply@subscriptionmanager.com',
            [user.email],
            fail_silently=False,
        )
        messages.success(request, "Check your inbox to verify your email before signing in.")
        return redirect('accounts:login')
    return render(request, 'registration/signup.html', {"form": form})

def activate_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Email verified! You can now login.")
        return redirect('accounts:login')
    else:
        return render(request, 'registration/activation_invalid.html')
