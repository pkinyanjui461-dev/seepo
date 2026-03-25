from django.urls import path
from groups import views

urlpatterns = [
    path('', views.group_list, name='group_list'),
    path('diary/', views.diary_list, name='diary_list'),
    path('api/diary/<int:pk>/update/', views.api_diary_update, name='api_diary_update'),
    path('create/', views.group_create, name='group_create'),
    path('<int:pk>/', views.group_detail, name='group_detail'),
    path('<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('<int:pk>/delete/', views.group_delete, name='group_delete'),
]
