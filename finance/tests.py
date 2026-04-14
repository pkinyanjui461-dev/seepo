import datetime
import uuid

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from finance.models import MonthlyForm, MemberRecord
from groups.models import Group
from members.models import Member


class MonthlyFormListOfflineUiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='finance_tester',
			phone_number='0700000200',
			email='finance@test.local',
			password='testpass123',
			role='admin',
		)
		self.client.force_login(self.user)

		self.group = Group.objects.create(
			name='Beta Group',
			location='Mombasa',
			date_created=datetime.date(2026, 2, 1),
			officer_name='Officer B',
			banking_type='group',
		)
		MonthlyForm.objects.create(
			group=self.group,
			month=4,
			year=2026,
			status='draft',
			created_by=self.user,
		)

	def test_monthly_form_list_contains_pending_offline_projection_ui(self):
		response = self.client.get(reverse('monthly_form_list', args=[self.group.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="offline-pending-monthly-forms-note"')
		self.assertContains(response, 'id="monthly-form-list-row"')
		self.assertContains(response, 'renderPendingMonthlyForms')
		self.assertContains(response, 'data-offline-form-action')
		self.assertContains(response, '/finance/forms/offline/')

	def test_offline_monthly_form_detail_shell_route_renders(self):
		response = self.client.get(
			reverse('monthly_form_detail_offline'),
			{
				'form_client_uuid': str(uuid.uuid4()),
				'group_client_uuid': str(self.group.client_uuid),
				'group_name': self.group.name,
				'month': '4',
				'year': '2026',
				'status': 'draft',
				'source': 'monthly_form_list',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="offlineFinanceTable"')
		self.assertContains(response, 'offline-monthly-form-detail.js')

	def test_monthly_form_detail_orders_rows_by_member_number_then_name(self):
		mform = MonthlyForm.objects.create(
			group=self.group,
			month=5,
			year=2026,
			status='draft',
			created_by=self.user,
		)

		member_five = Member.objects.create(
			group=self.group,
			member_number=5,
			name='Member Five',
			phone='0700000205',
			join_date=datetime.date(2026, 2, 5),
			is_active=True,
		)
		member_ten = Member.objects.create(
			group=self.group,
			member_number=10,
			name='Member Ten',
			phone='0700000210',
			join_date=datetime.date(2026, 2, 10),
			is_active=True,
		)
		member_two = Member.objects.create(
			group=self.group,
			member_number=2,
			name='Member Two',
			phone='0700000202',
			join_date=datetime.date(2026, 2, 2),
			is_active=True,
		)

		# Persist a deliberately out-of-sequence order value; view should still sort by member number.
		MemberRecord.objects.create(monthly_form=mform, member=member_five, order=0)
		MemberRecord.objects.create(monthly_form=mform, member=member_ten, order=1)
		MemberRecord.objects.create(monthly_form=mform, member=member_two, order=2)

		response = self.client.get(reverse('monthly_form_detail', args=[mform.pk]))
		self.assertEqual(response.status_code, 200)

		content = response.content.decode('utf-8')
		marker_two = 'style="background-color: #f8f9fa;">2</td>'
		marker_five = 'style="background-color: #f8f9fa;">5</td>'
		marker_ten = 'style="background-color: #f8f9fa;">10</td>'

		self.assertIn(marker_two, content)
		self.assertIn(marker_five, content)
		self.assertIn(marker_ten, content)
		self.assertLess(content.index(marker_two), content.index(marker_five))
		self.assertLess(content.index(marker_five), content.index(marker_ten))
