#!/usr/bin/env python3
"""
fix_site.py
===========
Diagnoses and fixes the 404 / settings issues found by deploy_check.py.

Fixes:
  1. Creates missing /static directory
  2. Validates and rewrites passenger_wsgi.py
  3. Checks settings.py for common misconfigs
  4. Generates a secure SECRET_KEY if needed
  5. Verifies Django URL routing (why / and /admin/ return 404)
  6. Restarts Passenger

Run from project root:
    python fix_site.py
"""

import os
import sys
import subprocess
import secrets
import string

# ── CONFIG ─────────────────────────────────────────────────────────────────
VENV_DIR        = '/home1/seepocok/virtualenv/public_html/seepo-main/3.13'
PROJECT_ROOT    = '/home1/seepocok/public_html/seepo-main'
DJANGO_SETTINGS = 'seepo_project.settings'
PYTHON_VERSION  = 'python3.13'
# ───────────────────────────────────────────────────────────────────────────

RESET  = '\033[0m'; BOLD = '\033[1m'
GREEN  = '\033[92m'; YELLOW = '\033[93m'
RED    = '\033[91m'; CYAN   = '\033[96m'

def ok(msg):    print(f"{GREEN}{BOLD}✔  {RESET}{GREEN}{msg}{RESET}")
def warn(msg):  print(f"{YELLOW}{BOLD}⚠  {RESET}{YELLOW}{msg}{RESET}")
def err(msg):   print(f"{RED}{BOLD}✘  {RESET}{RED}{msg}{RESET}")
def info(msg):  print(f"{CYAN}{BOLD}→  {RESET}{CYAN}{msg}{RESET}")
def section(t):
    print(f"\n{BOLD}{CYAN}{'─'*57}{RESET}")
    print(f"{BOLD}{CYAN}  {t}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*57}{RESET}")

def run(cmd):
    result = subprocess.run(cmd, shell=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

python = os.path.join(VENV_DIR, 'bin', 'python')
pip    = os.path.join(VENV_DIR, 'bin', 'pip')

# ── Bootstrap Django ────────────────────────────────────────────────────────
site_packages = os.path.join(VENV_DIR, 'lib', PYTHON_VERSION, 'site-packages')
sys.path.insert(0, site_packages)
sys.path.insert(1, PROJECT_ROOT)
os.environ['DJANGO_SETTINGS_MODULE'] = DJANGO_SETTINGS


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1 — Create missing /static directory
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 1 · Create missing /static directory")

static_dir      = os.path.join(PROJECT_ROOT, 'static')
staticfiles_dir = os.path.join(PROJECT_ROOT, 'staticfiles')

for d in [static_dir, staticfiles_dir]:
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
        ok(f"Created: {d}")
    else:
        ok(f"Already exists: {d}")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 — Validate & rewrite passenger_wsgi.py
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 2 · Validate passenger_wsgi.py")

wsgi_path = os.path.join(PROJECT_ROOT, 'passenger_wsgi.py')

CORRECT_WSGI = f"""import os
import sys

# ── Virtualenv site-packages ──────────────────────────────────────────────────
VENV_DIR      = '{VENV_DIR}'
PYTHON_VERSION = '{PYTHON_VERSION}'
SITE_PACKAGES  = os.path.join(VENV_DIR, 'lib', PYTHON_VERSION, 'site-packages')

if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = '{PROJECT_ROOT}'
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT)

# ── Django settings ───────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{DJANGO_SETTINGS}')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
"""

# Read current wsgi
if os.path.isfile(wsgi_path):
    with open(wsgi_path) as f:
        current = f.read()

    issues = []
    if VENV_DIR not in current:
        issues.append("VENV_DIR path is wrong or missing")
    if PYTHON_VERSION not in current:
        issues.append(f"PYTHON_VERSION '{PYTHON_VERSION}' not found")
    if PROJECT_ROOT not in current:
        issues.append("PROJECT_ROOT not in sys.path")
    if 'get_wsgi_application' not in current:
        issues.append("get_wsgi_application not imported")

    if issues:
        warn("Issues found in current passenger_wsgi.py:")
        for i in issues:
            print(f"  {YELLOW}  - {i}{RESET}")

        # Backup and rewrite
        backup = wsgi_path + '.bak'
        with open(backup, 'w') as f:
            f.write(current)
        ok(f"Backed up to: {backup}")

        with open(wsgi_path, 'w') as f:
            f.write(CORRECT_WSGI)
        ok(f"Rewrote: {wsgi_path}")
    else:
        ok("passenger_wsgi.py looks correct")

    # Print current file
    print(f"\n  {CYAN}── Current passenger_wsgi.py ──{RESET}")
    with open(wsgi_path) as f:
        for i, line in enumerate(f, 1):
            print(f"  {i:3}  {line}", end='')
    print()
else:
    warn(f"passenger_wsgi.py not found at {wsgi_path} — creating it ...")
    with open(wsgi_path, 'w') as f:
        f.write(CORRECT_WSGI)
    ok(f"Created: {wsgi_path}")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3 — Check settings.py for common issues
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 3 · Scan settings.py")

# Find settings file
settings_candidates = [
    os.path.join(PROJECT_ROOT, 'seepo_project', 'settings.py'),
    os.path.join(PROJECT_ROOT, 'settings.py'),
]
settings_file = None
for c in settings_candidates:
    if os.path.isfile(c):
        settings_file = c
        break

if not settings_file:
    err("settings.py not found — check DJANGO_SETTINGS_MODULE")
else:
    ok(f"Found: {settings_file}")
    with open(settings_file) as f:
        settings_src = f.read()

    checks = {
        'DEBUG = True':                   ("DEBUG is True — set to False for production", False),
        'django-insecure-':               ("SECRET_KEY uses insecure default — regenerate it!", True),
        'ALLOWED_HOSTS = []':             ("ALLOWED_HOSTS is empty — add your domain", True),
        'STATIC_ROOT':                    ("STATIC_ROOT is set", False),
        'STATICFILES_DIRS':               ("STATICFILES_DIRS is set", False),
        'seepo.co.ke':                    ("seepo.co.ke found in ALLOWED_HOSTS", False),
    }

    for needle, (label, is_problem) in checks.items():
        found = needle in settings_src
        if is_problem and found:
            err(label)
        elif not is_problem and found:
            ok(label)
        elif is_problem and not found:
            ok(f"OK: {label.replace('— ', '').replace('!','')}")
        else:
            warn(f"Not found: {needle} — {label}")

    # Check ALLOWED_HOSTS specifically
    import re
    ah_match = re.search(r"ALLOWED_HOSTS\s*=\s*\[([^\]]*)\]", settings_src)
    if ah_match:
        hosts = ah_match.group(1).strip()
        if hosts:
            ok(f"ALLOWED_HOSTS = [{hosts}]")
        else:
            err("ALLOWED_HOSTS = [] — site will refuse all requests in production!")
            warn("Add this to settings.py:")
            print(f"  {YELLOW}  ALLOWED_HOSTS = ['seepo.co.ke', 'www.seepo.co.ke']{RESET}")

    # Check DATABASE setting
    if 'sqlite' in settings_src.lower():
        warn("Using SQLite — fine for small sites but consider MySQL for production on cPanel")
    if 'mysql' in settings_src.lower() or 'postgresql' in settings_src.lower():
        ok("Using a production-grade database")

    # Check STATIC_ROOT path
    sr_match = re.search(r"STATIC_ROOT\s*=\s*['\"]([^'\"]+)['\"]", settings_src)
    if sr_match:
        sr = sr_match.group(1)
        info(f"STATIC_ROOT = {sr}")
        if not os.path.isabs(sr):
            warn("STATIC_ROOT should be an absolute path on cPanel")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 4 — Generate secure SECRET_KEY if needed
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 4 · SECRET_KEY check")

if settings_file and 'django-insecure-' in settings_src:
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    new_key = ''.join(secrets.choice(alphabet) for _ in range(64))
    warn("Your SECRET_KEY is insecure. Replace it in settings.py with:")
    print(f"\n  {GREEN}SECRET_KEY = '{new_key}'{RESET}\n")
    warn("Do NOT commit this key to git. Use environment variables in production.")
else:
    ok("SECRET_KEY appears to be custom")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 5 — Diagnose 404: check URL routing
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 5 · Diagnose 404 — URL routing check")

# Try to load Django and inspect URLs
try:
    import django
    django.setup()

    from django.urls import reverse, NoReverseMatch
    from django.test import RequestFactory
    from django.conf import settings as django_settings

    ok(f"Django {django.__version__} loaded")

    # Check ROOT_URLCONF
    urlconf = getattr(django_settings, 'ROOT_URLCONF', None)
    if urlconf:
        ok(f"ROOT_URLCONF = {urlconf}")
    else:
        err("ROOT_URLCONF not set in settings.py!")

    # Check if admin is included
    try:
        admin_url = reverse('admin:index')
        ok(f"admin:index resolves → {admin_url}")
    except NoReverseMatch:
        err("admin:index could not be reversed — is admin included in urls.py?")
        warn("Make sure urls.py has: path('admin/', admin.site.urls)")
    except Exception as ex:
        warn(f"admin URL check: {ex}")

    # Try to list all URL patterns
    from django.urls import get_resolver
    resolver = get_resolver()
    patterns = []
    def collect(r, prefix=''):
        for p in r.url_patterns:
            try:
                full = prefix + str(p.pattern)
                patterns.append(full)
                if hasattr(p, 'url_patterns'):
                    collect(p, full)
            except Exception:
                pass
    collect(resolver)

    if patterns:
        ok(f"Found {len(patterns)} URL patterns. Top-level routes:")
        for p in patterns[:20]:
            print(f"  {CYAN}  {p}{RESET}")
        if len(patterns) > 20:
            info(f"  ... and {len(patterns)-20} more")
    else:
        err("No URL patterns found — urls.py may be empty or broken")

except Exception as e:
    err(f"Could not load Django: {e}")
    import traceback
    traceback.print_exc()

# Check .htaccess for Passenger config
section("FIX 6 · Check .htaccess for Passenger")

htaccess_path = os.path.join(PROJECT_ROOT, '.htaccess')
if os.path.isfile(htaccess_path):
    with open(htaccess_path) as f:
        ht = f.read()
    ok(f"Found .htaccess")
    print(f"\n{CYAN}── .htaccess contents ──{RESET}")
    print(ht)

    if 'PassengerEnabled' not in ht and 'passenger' not in ht.lower():
        warn("Passenger directives not found in .htaccess")
        warn("cPanel may handle this automatically, but if 404s persist add:")
        print(f"""
  {YELLOW}  PassengerEnabled On
  PassengerAppRoot {PROJECT_ROOT}
  PassengerBaseURI /
  PassengerPython {python}{RESET}
""")
else:
    warn(f".htaccess not found at {htaccess_path}")
    warn("cPanel Python App should auto-create this. Check your Python App config in cPanel.")
    info("Correct .htaccess for Passenger:")
    print(f"""
  {YELLOW}  PassengerEnabled On
  PassengerAppRoot {PROJECT_ROOT}
  PassengerBaseURI /
  PassengerPython {python}{RESET}
""")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 7 — Restart Passenger
# ══════════════════════════════════════════════════════════════════════════════
section("FIX 7 · Restart Passenger")

wsgi_touch = os.path.join(PROJECT_ROOT, 'passenger_wsgi.py')
tmp_restart = os.path.join(PROJECT_ROOT, 'tmp', 'restart.txt')

os.makedirs(os.path.dirname(tmp_restart), exist_ok=True)
for f in [wsgi_touch, tmp_restart]:
    if os.path.isfile(f):
        os.utime(f, None)
    else:
        open(f, 'a').close()
    ok(f"Touched: {f}")


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{CYAN}{'═'*57}{RESET}")
print(f"{BOLD}{CYAN}  NEXT STEPS TO FIX 404{RESET}")
print(f"{BOLD}{CYAN}{'═'*57}{RESET}")
print(f"""
{CYAN}1.{RESET} Fix {YELLOW}ALLOWED_HOSTS{RESET} in settings.py:
     ALLOWED_HOSTS = ['seepo.co.ke', 'www.seepo.co.ke']

{CYAN}2.{RESET} Fix {YELLOW}SECRET_KEY{RESET} — use the generated key above

{CYAN}3.{RESET} Fix {YELLOW}STATICFILES_DIRS{RESET} — remove or update the missing path:
     STATICFILES_DIRS = []  # or point to the correct folder

{CYAN}4.{RESET} In {YELLOW}cPanel → Python App{RESET}, confirm:
     • Application root = public_html/seepo-main
     • Application URL  = /   (or your subdomain)
     • Application startup file = passenger_wsgi.py
     • Application entry point  = application
     Then click {GREEN}Restart{RESET} in cPanel.

{CYAN}5.{RESET} Set {YELLOW}DEBUG = False{RESET} and re-run deploy_check.py to confirm all green.
""")