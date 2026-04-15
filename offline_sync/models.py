from django.db import models


class SyncLog(models.Model):
    DIRECTION_CHOICES = [
        ('push', 'Push'),
        ('pull', 'Pull'),
    ]

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    model_name = models.CharField(max_length=64)
    records_count = models.PositiveIntegerField(default=0)
    conflicts_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.direction}:{self.model_name} ({self.records_count})"
