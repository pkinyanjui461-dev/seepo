#!/usr/bin/env python3
"""
fix_xhtml2pdf_v2.py
===================
Installs xhtml2pdf 0.2.15 correctly on cPanel shared hosting.

Root cause of previous error:
  svglib >= 1.6.0 depends on rlpycairo → pycairo → needs 'meson' build tool
  cPanel shared hosting does NOT have meson → PermissionError

Fix: pin svglib==1.5.1 (no rlpycairo dependency) + install xhtml2pdf==0.2.15

Run from your project root in cPanel Terminal:
    python fix_xhtml2pdf_v2.py
"""

import os
import sys
import subprocess

# ── CONFIG ────────────────────────────────────────────────────────────────────
VENV_DIR = '/home1/seepocok/virtualenv/public_html/seepo-main/3.13'
# ─────────────────────────────────────────────────────────────────────────────

RESET  = '\033[0m'
BOLD   = '\033[1m'
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
CYAN   = '\033[96m'

def ok(msg):    print(f"{GREEN}{BOLD}✔  {RESET}{GREEN}{msg}{RESET}")
def warn(msg):  print(f"{YELLOW}{BOLD}⚠  {RESET}{YELLOW}{msg}{RESET}")
def err(msg):   print(f"{RED}{BOLD}✘  {RESET}{RED}{msg}{RESET}")
def info(msg):  print(f"{CYAN}{BOLD}→  {RESET}{CYAN}{msg}{RESET}")
def section(t):
    print(f"\n{BOLD}{CYAN}{'─'*57}{RESET}")
    print(f"{BOLD}{CYAN}  {t}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*57}{RESET}")

def run(cmd, show=True):
    if show:
        print(f"  {YELLOW}$ {cmd}{RESET}")
    result = subprocess.run(cmd, shell=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.stdout.strip():
        # Show only last few relevant lines
        lines = result.stdout.strip().splitlines()
        for line in lines:
            if any(k in line for k in ['Successfully', 'already', 'error', 'ERROR', 'WARNING']):
                print(f"    {line}")
    return result.returncode, result.stdout, result.stderr

# ── Locate binaries ───────────────────────────────────────────────────────────
pip    = os.path.join(VENV_DIR, 'bin', 'pip')
python = os.path.join(VENV_DIR, 'bin', 'python')

if not os.path.isfile(pip):
    pip = 'pip3'
if not os.path.isfile(python):
    python = sys.executable

section("STEP 1 · Uninstall conflicting packages")
info("Removing svglib >= 1.6.0 and rlpycairo (they require meson/pycairo)")
info("Also removing xhtml2pdf if present so we can do a clean install ...")

for pkg in ['svglib', 'rlpycairo', 'pycairo', 'xhtml2pdf']:
    code, out, stderr = run(f"{pip} uninstall -y {pkg}")
    if 'Successfully uninstalled' in out:
        ok(f"Removed: {pkg}")
    else:
        warn(f"Not installed (ok): {pkg}")

section("STEP 2 · Install pinned safe versions of dependencies")

# These are the exact safe versions — no meson, no C build tools needed
SAFE_DEPS = [
    ('pillow',         'pillow>=11.0.0'),
    ('html5lib',       'html5lib==1.1'),
    ('pypdf',          'pypdf>=3.1.0'),
    ('arabic-reshaper','arabic-reshaper>=3.0.0'),
    ('python-bidi',    'python-bidi>=0.4.2'),
    ('cssselect2',     'cssselect2>=0.2.0'),
    ('tinycss2',       'tinycss2>=0.6.0'),
    ('lxml',           'lxml>=4.9.0'),
    # svglib 1.5.1 — does NOT depend on rlpycairo/pycairo/meson
    ('svglib',         'svglib==1.5.1'),
    # reportlab <4.1 is what xhtml2pdf 0.2.15 needs
    ('reportlab',      'reportlab>=4.0.4,<4.1'),
]

for name, spec in SAFE_DEPS:
    info(f"Installing {spec} ...")
    code, out, stderr = run(f"{pip} install \"{spec}\"")
    if code == 0:
        ok(f"{name} → OK")
    else:
        err(f"{name} failed")
        print(f"  {RED}{stderr[-300:]}{RESET}")

section("STEP 3 · Install xhtml2pdf 0.2.15 (no-deps to prevent svglib upgrade)")

info("Installing xhtml2pdf==0.2.15 with --no-deps to keep our pinned svglib ...")
code, out, stderr = run(f"{pip} install xhtml2pdf==0.2.15 --no-deps")
if code == 0:
    ok("xhtml2pdf==0.2.15 installed")
else:
    err("xhtml2pdf install failed")
    print(f"  {RED}{stderr}{RESET}")
    sys.exit(1)

# Install remaining xhtml2pdf deps that aren't pinned above
info("Installing pyHanko and certvalidator (PDF signing deps) ...")
code, _, stderr = run(f"{pip} install pyHanko pyhanko-certvalidator")
if code == 0:
    ok("pyHanko installed")
else:
    warn(f"pyHanko had issues: {stderr[-200:]}")

section("STEP 4 · Verify import")

verify = (
    "import xhtml2pdf; "
    "print('xhtml2pdf', xhtml2pdf.__version__); "
    "from xhtml2pdf import pisa; "
    "print('pisa OK')"
)
code, out, stderr = run(f'{python} -c "{verify}"', show=False)
if code == 0:
    for line in out.strip().splitlines():
        ok(line)
else:
    err("Import verification failed:")
    print(f"  {RED}{(out + stderr).strip()}{RESET}")
    sys.exit(1)

section("STEP 5 · Installed package summary")

code, out, _ = run(f"{pip} list", show=False)
relevant = ['xhtml2pdf','pillow','reportlab','html5lib','pypdf',
            'svglib','arabic','bidi','lxml','pyhanko','setuptools']
for line in out.splitlines():
    if any(r in line.lower() for r in relevant):
        print(f"  {GREEN}  {line}{RESET}")

section("STEP 6 · Restart Passenger")

project_root = os.path.dirname(os.path.abspath(__file__))
wsgi = os.path.join(project_root, 'passenger_wsgi.py')
tmp  = os.path.join(project_root, 'tmp', 'restart.txt')

if os.path.isfile(wsgi):
    os.utime(wsgi, None)
    ok(f"Touched: {wsgi}")
else:
    warn(f"passenger_wsgi.py not found at {wsgi} — touch it manually")

os.makedirs(os.path.dirname(tmp), exist_ok=True)
with open(tmp, 'a'):
    os.utime(tmp, None)
ok(f"Touched: {tmp}")

print(f"\n{BOLD}{CYAN}{'═'*57}{RESET}")
print(f"{GREEN}{BOLD}  ✔  xhtml2pdf 0.2.15 is ready!{RESET}")
print(f"{BOLD}{CYAN}{'═'*57}{RESET}\n")

info("Key fix applied: svglib pinned to 1.5.1 (no pycairo/meson required)")
info("If PDF generation fails in Django, the issue is in your view code, not install.")
print()