from django.contrib import admin
from django.urls import path, include
from django.views.decorators.cache import cache_page
from django.views.static import serve
from django.conf import settings
from pathlib import Path
from seepo_project.dashboard import dashboard
from offline_sync import views as offline_sync_views

BASE_DIR = Path(__file__).resolve().parent.parent

def favicon_view(request):
    from django.http import FileResponse
    return FileResponse(open(BASE_DIR / 'static' / 'favicon.ico', 'rb'), content_type='image/x-icon')

def robots_view(request):
    from django.http import FileResponse
    return FileResponse(open(BASE_DIR / 'static' / 'robots.txt', 'rb'), content_type='text/plain')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('api/sync/', include('offline_sync.urls')),
    path('accounts/', include('accounts.urls')),
    path('groups/', include('groups.urls')),
    path('members/', include('members.urls')),
    path('finance/', include('finance.urls')),
    path('reports/', include('reports.urls')),
    path('sw.js', offline_sync_views.service_worker, name='service_worker'),
    path('manifest.webmanifest', offline_sync_views.web_manifest, name='web_manifest'),
    path('favicon.ico', cache_page(60 * 60 * 24)(favicon_view)),
    path('robots.txt', cache_page(60 * 60 * 24)(robots_view)),
]
