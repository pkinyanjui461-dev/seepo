from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
    ROLE_CHOICES = [
        ('ict', 'ICT'),
        ('officer', 'Data Entry Officer'),
        ('management', 'Management'),
        ('admin', 'Administrator'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='officer')
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username', 'email']

    def is_admin(self):
        return self.role in ['admin', 'ict']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    url = models.CharField(max_length=255, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"
