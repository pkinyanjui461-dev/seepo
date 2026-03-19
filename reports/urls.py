from django.urls import path
from reports import views

urlpatterns = [
    path('', views.reports_overview, name='reports_overview'),
    path('entities/', views.entities_report, name='entities_report'),
]
