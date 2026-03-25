import os
import sys

VENV_DIR     = '/home1/seepocok/virtualenv/public_html/seepo-main/3.13'
PROJECT_ROOT = '/home1/seepocok/public_html/seepo-main'

sys.path.insert(0, os.path.join(VENV_DIR, 'lib', 'python3.13', 'site-packages'))
sys.path.insert(1, PROJECT_ROOT)
os.environ['DJANGO_SETTINGS_MODULE'] = 'seepo_project.settings'

import django
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    u = User.objects.get(username='admin')

    # Show all fields available on the user model
    print("Available fields:", [f.name for f in User._meta.get_fields()])

    # Set phone_number if it exists
    if hasattr(u, 'phone_number'):
        u.phone_number = 'admin'
        u.save()
        print(f"✔ phone_number set to 'admin' for user '{u.username}'")
    else:
        print("✘ phone_number field not found on User model")
        print("  Check the field name in the Available fields list above")

except User.DoesNotExist:
    print("✘ User 'admin' not found")