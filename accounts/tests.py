from django.test import TestCase
from django.urls import reverse


class LoginPwaInstallUiTests(TestCase):
	def test_login_page_contains_pwa_install_hooks(self):
		response = self.client.get(reverse('login'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="pwa-install-btn"')
		self.assertContains(response, 'id="offline-host-ready-badge"')
		self.assertContains(response, 'sw-register.js?v=24')
