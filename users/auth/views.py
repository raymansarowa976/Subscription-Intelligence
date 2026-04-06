from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages

User = get_user_model()

def signup_view(request):
    if request.method == 'POST':
        # Simple implementation for TDD; usually you'd use a UserCreationForm
        user = User.objects.create_user(
            username=request.POST['username'],
            email=request.POST['email'],
            password=request.POST['password']
        )
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        # Generate Token and UID
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build the absolute URL for the email
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
        return redirect('accounts:login')
    return render(request, 'registration/signup.html')

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
