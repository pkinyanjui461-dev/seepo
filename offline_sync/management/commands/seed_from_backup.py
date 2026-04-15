from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from groups.models import Group
from members.models import Member
from finance.models import MonthlyForm, MemberRecord

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
            # Create with proper group_client_uuid to match offline schema
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
            # Ensure group_client_uuid is set for offline sync
            if created or not hasattr(member, '_get_group_client_uuid'):
                # Update to ensure it has group reference for offline
                member.save()
            if created:
                members_created += 1

        self.stdout.write(self.style.SUCCESS(f'  Members created: {members_created}'))

        # Create monthly forms for this group
        forms_created = 0
        forms = []
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
            forms.append(form)
            if created:
                forms_created += 1

        self.stdout.write(self.style.SUCCESS(f'  Monthly forms created: {forms_created}'))

        # Create MemberRecords for each form × member combination with sample data
        records_created = 0
        all_members = Member.objects.filter(group=group)
        for form in forms:
            for idx, member in enumerate(all_members, start=1):
                record, created = MemberRecord.objects.get_or_create(
                    monthly_form=form,
                    member=member,
                    defaults={
                        'order': idx,
                        'savings_share_bf': 5000 if idx % 2 == 0 else 3000,
                        'loan_balance_bf': 10000 if idx % 3 == 0 else 8000,
                        'total_repaid': 2000 if idx % 2 == 0 else 1500,
                        'principal': 1000,
                        'shares_this_month': 500 if idx % 2 == 0 else 300,
                        'withdrawals': 200 if idx % 4 == 0 else 0,
                        'fines_charges': 50 if idx % 5 == 0 else 0,
                    }
                )
                if created:
                    # Calculate derived fields
                    record.calculate()
                    record.validate()
                    record.save()
                    records_created += 1

        self.stdout.write(self.style.SUCCESS(f'  Member records created: {records_created}'))
        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
