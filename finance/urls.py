from django.urls import path
from finance import views

urlpatterns = [
    path('group/<int:group_pk>/forms/', views.monthly_form_list, name='monthly_form_list'),
    path('group/<int:group_pk>/forms/create/', views.monthly_form_create, name='monthly_form_create'),
    path('forms/<int:pk>/', views.monthly_form_detail, name='monthly_form_detail'),
    path('forms/<int:pk>/delete/', views.monthly_form_delete, name='monthly_form_delete'),
    path('record/<int:record_pk>/save/', views.save_member_record, name='save_member_record'),
    path('forms/<int:pk>/pdf/', views.monthly_form_pdf, name='monthly_form_pdf'),
    path('forms/<int:mform_pk>/performance/', views.performance_form_view, name='performance_form'),
    path('forms/<int:pk>/performance/pdf/', views.performance_form_pdf, name='performance_form_pdf'),
    path('forms/<int:pk>/full-report/pdf/', views.combined_monthly_report_pdf, name='combined_monthly_report_pdf'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
]
