from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    """
    Standard AbstractUser for now. 
    We use this so we can add 'tier' or 'profile_pic' 
    later without breaking the database.
    """
    pass