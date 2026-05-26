from django.contrib.auth.models import AbstractUser  # Fixes "AbstractUser is not defined"
from django.db import models                         # Fixes "models is not defined"

class User(AbstractUser):
    email = models.EmailField(unique=True)
    force_migration = models.BooleanField(default=False) # ADD THIS
    base_currency = models.CharField(max_length=3, default="USD")
