from django.core.management.base import BaseCommand
from accounts.models import User
from groups.models import Group
from members.models import Member
from finance.models import MonthlyForm, MemberRecord, GroupPerformanceForm, PerformanceEntry
import datetime
import random
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed database with initial data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')

        # 1. Users
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin', role='admin')
        if not User.objects.filter(username='officer').exists():
            User.objects.create_user('officer', 'officer@example.com', 'officer', role='officer')

        # 2. Groups
        group1, _ = Group.objects.get_or_create(
            name='Nairobi Traders Chama',
            location='Nairobi CBD',
            date_created=datetime.date(2023, 1, 15),
            officer_name='Jane Doe'
        )
        group2, _ = Group.objects.get_or_create(
            name='Ushindi Savings Group',
            location='Nakuru Town',
            date_created=datetime.date(2023, 6, 20),
            officer_name='John Smith'
        )

        # 3. Members
        members_data = [
            ('Alice Mumbi', '0711122334', group1),
            ('Bob Kihika', '0722334455', group1),
            ('Charlie Ndegwa', '0733445566', group1),
            ('Diana Wanjiku', '0744556677', group1),
            ('Eve Mutuku', '0755667788', group2),
            ('Frank Otieno', '0766778899', group2),
            ('Grace Achieng', '0777889900', group2),
        ]
        
        for name, phone, grp in members_data:
            Member.objects.get_or_create(
                name=name, phone=phone, group=grp,
                defaults={'join_date': grp.date_created}
            )

        # 4. Finance Data (Nairobi Traders - Jan 2024)
        mform_jan, created_jan = MonthlyForm.objects.get_or_create(
            group=group1, month=1, year=2024,
            defaults={'status': 'approved'}
        )
        
        if created_jan:
            for i, member in enumerate(group1.member_set.all()):
                record = MemberRecord.objects.create(
                    monthly_form=mform_jan,
                    member=member,
                    order=i,
                    savings_share_bf=Decimal(random.randint(10, 50) * 1000),
                    loan_balance_bf=Decimal(random.randint(0, 30) * 1000),
                    total_repaid=Decimal(random.randint(0, 5) * 1000),
                    principal=Decimal(random.randint(0, 5) * 1000),
                    shares_this_month=Decimal(2000),
                    fines_charges=Decimal(0)
                )
                record.calculate()
                record.save()

            # Performance Form
            perf_form = GroupPerformanceForm.objects.create(monthly_form=mform_jan)
            PerformanceEntry.objects.create(performance_form=perf_form, section='C', description='Total Shares', amount=Decimal(8000), order=0)
            PerformanceEntry.objects.create(performance_form=perf_form, section='D', description='Loans Repaid', amount=Decimal(5000), order=0)

        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))
