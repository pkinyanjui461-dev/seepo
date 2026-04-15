from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from groups.models import Group
from members.models import Member
from finance.models import MonthlyForm

class Command(BaseCommand):
    help = 'Seed database with realistic test data (like backup data)'

    def handle(self, *args, **options):
        """Create realistic test groups, members, and forms."""
        self.stdout.write('Seeding test database with realistic data...')

        # Create a realistic test group
        group, group_created = Group.objects.get_or_create(
            name='AGGRESSIVE SHG',
            defaults={
                'location': 'Nairobi',
                'date_created': date(2026, 1, 15),
                'officer_name': 'John Doe',
                'banking_type': 'office',
            }
        )
        if group_created:
            self.stdout.write(self.style.SUCCESS('  Created group: AGGRESSIVE SHG'))

        # Create multiple members
        members_created = 0
        member_names = [
            'Alice Kipchoge', 'Bob Mwangi', 'Catherine Koech', 'David Cheruiyot',
            'Eve Njoroge', 'Frank Kariuki', 'Grace Omondi', 'Henry Kumwenda',
            'Iris Kamau', 'James Kiplagat'
        ]

        for idx, name in enumerate(member_names, start=1):
            member, created = Member.objects.get_or_create(
                group=group,
                member_number=idx,
                defaults={
                    'name': name,
                    'phone': f'0700{100000 + idx:06d}',
                    'join_date': date(2025, 6, 15),
                    'is_active': True,
                }
            )
            if created:
                members_created += 1

        self.stdout.write(self.style.SUCCESS(f'  Members created: {members_created}'))

        # Create monthly forms for this group
        forms_created = 0
        for month in [1, 2, 3]:
            form, created = MonthlyForm.objects.get_or_create(
                group=group,
                month=month,
                year=2026,
                defaults={
                    'status': 'draft' if month == 3 else 'approved',
                    'notes': f'Monthly form for {month}/2026',
                }
            )
            if created:
                forms_created += 1

        self.stdout.write(self.style.SUCCESS(f'  Monthly forms created: {forms_created}'))
        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
