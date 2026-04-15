import json
from django.core.management.base import BaseCommand
from groups.models import Group
from finance.models import MonthlyForm


class Command(BaseCommand):
    help = 'Get seeded test data (group/member/form) as JSON'

    def handle(self, *args, **options):
        """Output seeded data in JSON format for smoke test."""
        try:
            # Get the "AGGRESSIVE SHG" test group
            group = Group.objects.filter(name='AGGRESSIVE SHG').first()
            if not group:
                self.stdout.write(json.dumps({"error": "No AGGRESSIVE SHG group found"}))
                return

            # Get the first monthly form for this group
            form = MonthlyForm.objects.filter(group=group).first()
            if not form:
                self.stdout.write(json.dumps({"error": "No monthly forms for AGGRESSIVE SHG"}))
                return

            # Get the first member using the correct reverse relationship
            from members.models import Member
            member = Member.objects.filter(group=group).first()
            if not member:
                self.stdout.write(json.dumps({"error": "No members for AGGRESSIVE SHG"}))
                return

            data = {
                'group_client_uuid': str(group.client_uuid) if hasattr(group, 'client_uuid') else '',
                'group_name': group.name,
                'form_client_uuid': str(form.client_uuid),
                'member_name': member.name,
            }
            self.stdout.write(json.dumps(data))
        except Exception as e:
            self.stdout.write(json.dumps({"error": str(e)}))
