import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from groups.models import Group


class ReportsOfflineProjectionUiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='reports_tester',
			phone_number='0700000300',
			email='reports@test.local',
			password='testpass123',
			role='admin',
		)
		self.client.force_login(self.user)

		Group.objects.create(
			name='Gamma Group',
			location='Kisumu',
			date_created=datetime.date(2026, 3, 1),
			officer_name='Officer C',
			banking_type='office',
		)

	def test_reports_overview_contains_offline_projection_hooks(self):
		response = self.client.get(reverse('reports_overview'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'getPendingProjection')
		self.assertContains(response, 'pending member record')
		self.assertContains(response, 'pending monthly form')

	def test_entities_report_contains_offline_projection_hooks(self):
		response = self.client.get(reverse('entities_report'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'getPendingProjection')
		self.assertContains(response, 'pending member record')
		self.assertContains(response, 'pending monthly form')
