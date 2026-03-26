import os
import sys

# ── Auto-detect environment based on path ────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if 'staging_seepo' in SCRIPT_DIR:
    # Staging environment
    VENV_DIR = '/home1/seepocok/virtualenv/staging_seepo/seepo-main/3.13'
    PROJECT_ROOT = '/home1/seepocok/staging_seepo/seepo-main'
else:
    # Production environment
    VENV_DIR = '/home1/seepocok/virtualenv/public_html/seepo-main/3.13'
    PROJECT_ROOT = '/home1/seepocok/public_html/seepo-main'

# ── Virtualenv site-packages ──────────────────────────────────────────────────
PYTHON_VERSION = 'python3.13'
SITE_PACKAGES = os.path.join(VENV_DIR, 'lib', PYTHON_VERSION, 'site-packages')

if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

# ── Project root ──────────────────────────────────────────────────────────────
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT)

# ── Django settings ───────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seepo_project.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

