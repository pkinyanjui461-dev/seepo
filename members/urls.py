from django.urls import path
from members import views

urlpatterns = [
    path('group/<int:group_pk>/', views.member_list, name='member_list'),
    path('group/<int:group_pk>/add/', views.member_create, name='member_create'),
    path('<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('<int:pk>/delete/', views.member_delete, name='member_delete'),
]
