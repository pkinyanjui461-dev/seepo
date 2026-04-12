import uuid

from django.db import models
from django.utils import timezone


class Group(models.Model):
    BANKING_CHOICES = [
        ('office', 'Office Account'),
        ('group', 'Group Account'),
    ]
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    date_created = models.DateField()
    officer_name = models.CharField(max_length=200)
    banking_type = models.CharField(max_length=20, choices=BANKING_CHOICES, default='office')
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def member_count(self):
        return self.member_set.count()

class DiaryEntry(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='diary')
    venue = models.CharField(max_length=200, blank=True, null=True)
    time = models.CharField(max_length=100, blank=True, null=True)
    
    # Meeting dates for each month (stored as string like "21ST", "15", "15TH-")
    january = models.CharField(max_length=50, blank=True, null=True)
    february = models.CharField(max_length=50, blank=True, null=True)
    march = models.CharField(max_length=50, blank=True, null=True)
    april = models.CharField(max_length=50, blank=True, null=True)
    may = models.CharField(max_length=50, blank=True, null=True)
    june = models.CharField(max_length=50, blank=True, null=True)
    july = models.CharField(max_length=50, blank=True, null=True)
    august = models.CharField(max_length=50, blank=True, null=True)
    september = models.CharField(max_length=50, blank=True, null=True)
    october = models.CharField(max_length=50, blank=True, null=True)
    november = models.CharField(max_length=50, blank=True, null=True)
    december = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.group.name} Diary"
