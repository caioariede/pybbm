import django


if django.VERSION[:2] >= (1, 5):
    from django.contrib.auth import get_user_model
    User = get_user_model()
else:
    from django.contrib.auth.models import User
    User.get_username = lambda u: u.username  # emulate new 1.5 method
