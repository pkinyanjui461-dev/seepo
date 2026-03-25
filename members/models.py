from django.db import models
from groups.models import Group


class Member(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    member_number = models.PositiveIntegerField(null=True, blank=True, help_text="Permanent member number within this group")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    join_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['member_number', 'name']
        unique_together = [['group', 'member_number']]

    def __str__(self):
        num = f"#{self.member_number} " if self.member_number else ""
        return f"{num}{self.name} ({self.group.name})"
