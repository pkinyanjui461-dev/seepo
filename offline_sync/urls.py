from django.urls import path

from . import views

urlpatterns = [
    path('ping/', views.sync_ping, name='sync_ping'),
    path('pull/', views.sync_pull, name='sync_pull'),
    path('push/', views.sync_push, name='sync_push'),
    path('debug/queue/', views.debug_queue, name='sync_debug_queue'),
    path('debug/status/', views.debug_status, name='sync_debug_status'),
    path('debug/clear/', views.debug_clear, name='sync_debug_clear'),
]
