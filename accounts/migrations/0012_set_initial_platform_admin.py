# Generated migration to set initial platform admin
from django.db import migrations


def set_initial_platform_admin(apps, schema_editor):
    """Set the 'adenc' user as a platform admin."""
    User = apps.get_model('accounts', 'User')
    try:
        user = User.objects.get(username='adenc')
        user.is_platform_admin = True
        user.save()
    except User.DoesNotExist:
        # User doesn't exist yet, skip
        pass


def reverse_set_initial_platform_admin(apps, schema_editor):
    """Reverse: remove platform admin from 'adenc' user."""
    User = apps.get_model('accounts', 'User')
    try:
        user = User.objects.get(username='adenc')
        user.is_platform_admin = False
        user.save()
    except User.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_is_platform_admin'),
    ]

    operations = [
        migrations.RunPython(set_initial_platform_admin, reverse_set_initial_platform_admin),
    ]
