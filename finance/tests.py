import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from finance.models import MonthlyForm
from groups.models import Group


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
