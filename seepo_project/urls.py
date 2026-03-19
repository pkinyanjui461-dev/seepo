from django.contrib import admin
from django.urls import path, include
from seepo_project.dashboard import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('accounts/', include('accounts.urls')),
    path('groups/', include('groups.urls')),
    path('members/', include('members.urls')),
    path('finance/', include('finance.urls')),
    path('reports/', include('reports.urls')),
]
