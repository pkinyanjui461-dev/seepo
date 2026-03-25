import os
import sys

# ── Virtualenv site-packages ──────────────────────────────────────────────────
VENV_DIR      = '/home1/seepocok/virtualenv/public_html/seepo-main/3.13'
PYTHON_VERSION = 'python3.13'
SITE_PACKAGES  = os.path.join(VENV_DIR, 'lib', PYTHON_VERSION, 'site-packages')

if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = '/home1/seepocok/public_html/seepo-main'
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT)

# ── Django settings ───────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seepo_project.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
