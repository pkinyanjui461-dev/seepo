import os
import sys
import mimetypes

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
django_app = get_wsgi_application()

# ── Static file bypass middleware ──────────────────────────────────────────────
# Serve static/media files directly without Django to avoid MIME type issues
class StaticFilesMiddleware:
    def __init__(self, application):
        self.application = application
        self.static_root = os.path.join(PROJECT_ROOT, 'staticfiles')
        self.media_root = os.path.join(PROJECT_ROOT, 'media')

        # Ensure MIME types are properly configured
        mimetypes.add_type('text/css', '.css')
        mimetypes.add_type('application/javascript', '.js')
        mimetypes.add_type('application/json', '.json')
        mimetypes.add_type('image/svg+xml', '.svg')

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')

        # Check if it's a static file request
        if path.startswith('/static/') or path.startswith('/staticfiles/'):
            return self._serve_static(path, environ, start_response)

        # Check if it's a media file request
        if path.startswith('/media/'):
            return self._serve_media(path, environ, start_response)

        # Otherwise, use Django
        return self.application(environ, start_response)

    def _serve_static(self, path, environ, start_response):
        # Remove leading /static/ or /staticfiles/
        file_path = path.replace('/static/', '').replace('/staticfiles/', '')
        file_system_path = os.path.join(self.static_root, file_path)
        return self._send_file(file_system_path, start_response)

    def _serve_media(self, path, environ, start_response):
        # Remove leading /media/
        file_path = path.replace('/media/', '')
        file_system_path = os.path.join(self.media_root, file_path)
        return self._send_file(file_system_path, start_response)

    def _send_file(self, file_system_path, start_response):
        # Prevent directory traversal attacks
        if '..' in file_system_path or file_system_path.startswith('/'):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']

        if not os.path.exists(file_system_path) or not os.path.isfile(file_system_path):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']

        # Get proper MIME type
        mime_type, _ = mimetypes.guess_type(file_system_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        try:
            with open(file_system_path, 'rb') as f:
                content = f.read()

            headers = [
                ('Content-Type', mime_type),
                ('Content-Length', str(len(content))),
                ('Cache-Control', 'max-age=31536000, public'),
            ]
            start_response('200 OK', headers)
            return [content]
        except Exception:
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']

# ── Apply middleware ──────────────────────────────────────────────────────────
application = StaticFilesMiddleware(django_app)
