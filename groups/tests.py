import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from finance.models import MonthlyForm
from groups.models import Group
from members.models import Member


class GroupWorkspaceOfflineUiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='groups_tester',
			phone_number='0700000100',
			email='groups@test.local',
			password='testpass123',
			role='admin',
		)
		self.client.force_login(self.user)

		self.group = Group.objects.create(
			name='Alpha Group',
			location='Nairobi',
			date_created=datetime.date(2026, 1, 1),
			officer_name='Officer A',
			banking_type='office',
		)
		Member.objects.create(
			group=self.group,
			member_number=1,
			name='Member One',
			phone='0700000111',
			join_date=datetime.date(2026, 1, 2),
			is_active=True,
		)
		MonthlyForm.objects.create(
			group=self.group,
			month=4,
			year=2026,
			status='draft',
			created_by=self.user,
		)

	def test_group_detail_contains_offline_member_management_controls(self):
		response = self.client.get(reverse('group_detail', args=[self.group.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="add-offline-member-btn"')
		self.assertContains(response, 'data-offline-member-action="manage"')
		self.assertContains(response, 'id="offline-pending-members-note"')

	def test_group_detail_contains_pending_monthly_form_projection_hooks(self):
		response = self.client.get(reverse('group_detail', args=[self.group.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="offline-pending-forms-note"')
		self.assertContains(response, 'id="group-monthly-forms-row"')
		self.assertContains(response, 'renderPendingMonthlyForms')
