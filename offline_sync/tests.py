import json
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from finance.models import Expense
from groups.models import Group
from offline_sync.models import SyncLog


@override_settings(DEBUG=True)
class OfflineSyncApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            phone_number="700000001",
            username="sync-tester",
            email="sync@example.com",
            password="StrongPass123!",
            role="ict",
        )
        cls.workspace_group = Group.objects.create(
            name='Workspace Group',
            location='Nairobi',
            date_created=date(2026, 4, 1),
            officer_name='Workspace Officer',
            banking_type='office',
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.push_url = reverse("sync_push")
        self.pull_url = reverse("sync_pull")
        self.ping_url = reverse("sync_ping")
        self.queue_url = reverse("sync_debug_queue")
        self.status_url = reverse("sync_debug_status")
        self.clear_url = reverse("sync_debug_clear")
        self.sw_url = reverse("service_worker")
        self.manifest_url = reverse("web_manifest")
        self.offline_url = reverse("offline_fallback")

    def _push(self, model_name, records):
        return self.client.post(
            self.push_url,
            data=json.dumps({"model": model_name, "records": records}),
            content_type="application/json",
        )

    def _group_payload(self, *, name, client_uuid=None, client_updated_at=None):
        return {
            "client_uuid": client_uuid or str(uuid.uuid4()),
            "client_updated_at": (client_updated_at or timezone.now()).isoformat(),
            "name": name,
            "location": "Nairobi",
            "date_created": "2026-04-01",
            "officer_name": "Officer One",
            "banking_type": "office",
        }

    def _expense_payload(self, *, name, amount="120.50", client_uuid=None, client_updated_at=None):
        return {
            "client_uuid": client_uuid or str(uuid.uuid4()),
            "client_updated_at": (client_updated_at or timezone.now()).isoformat(),
            "date": "2026-04-01",
            "name": name,
            "amount": amount,
            "notes": "mock",
        }

    def test_basic_online_create_and_debug_visibility(self):
        payload = self._group_payload(name="Alpha Group")

        response = self._push("group", [payload])
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["synced"], 1)
        self.assertEqual(body["conflicts"], 0)
        self.assertEqual(body["errors"], [])

        created = Group.objects.get(client_uuid=payload["client_uuid"])
        self.assertEqual(created.name, "Alpha Group")
        self.assertIsNotNone(created.client_uuid)

        queue_response = self.client.get(self.queue_url)
        self.assertEqual(queue_response.status_code, 200)
        self.assertGreaterEqual(queue_response.json()["count"], 1)

        status_response = self.client.get(self.status_url)
        self.assertEqual(status_response.status_code, 200)
        self.assertGreaterEqual(status_response.json()["models"]["group"], 1)

    def test_idempotency_push_same_record_twice_no_duplicate(self):
        client_uuid = str(uuid.uuid4())
        payload = self._expense_payload(name="Fuel", client_uuid=client_uuid)

        first = self._push("expense", [payload])
        second = self._push("expense", [payload])

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Expense.objects.filter(client_uuid=client_uuid).count(), 1)
        self.assertEqual(SyncLog.objects.filter(direction="push", model_name="expense").count(), 2)

    def test_conflict_resolution_rejects_older_accepts_newer(self):
        client_uuid = str(uuid.uuid4())
        now = timezone.now()

        newest = self._expense_payload(
            name="Initial New",
            client_uuid=client_uuid,
            client_updated_at=now,
        )
        old = self._expense_payload(
            name="Stale Old",
            client_uuid=client_uuid,
            client_updated_at=now - timedelta(minutes=5),
        )
        newer = self._expense_payload(
            name="Fresh New",
            client_uuid=client_uuid,
            client_updated_at=now + timedelta(minutes=5),
        )

        first = self._push("expense", [newest]).json()
        second = self._push("expense", [old]).json()
        third = self._push("expense", [newer]).json()

        self.assertEqual(first["synced"], 1)
        self.assertEqual(second["synced"], 0)
        self.assertEqual(second["conflicts"], 1)
        self.assertEqual(third["synced"], 1)
        self.assertEqual(third["conflicts"], 0)

        record = Expense.objects.get(client_uuid=client_uuid)
        self.assertEqual(record.name, "Fresh New")

    def test_pull_since_returns_only_newer_records(self):
        old_group = Group.objects.create(
            name="Old Group",
            location="Kisumu",
            date_created="2026-03-01",
            officer_name="Old Officer",
            banking_type="office",
            client_updated_at=timezone.now() - timedelta(days=2),
        )
        new_group = Group.objects.create(
            name="New Group",
            location="Nakuru",
            date_created="2026-04-01",
            officer_name="New Officer",
            banking_type="group",
            client_updated_at=timezone.now(),
        )

        Group.objects.filter(pk=old_group.pk).update(updated_at=timezone.now() - timedelta(days=2))
        Group.objects.filter(pk=new_group.pk).update(updated_at=timezone.now())

        since_ts = (timezone.now() - timedelta(days=1)).timestamp()
        response = self.client.get(self.pull_url, {"model": "group", "since": since_ts})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["count"], 1)
        record_names = {record["name"] for record in body["records"]}
        self.assertIn("New Group", record_names)

    def test_bulk_push_100_records(self):
        records = [
            self._expense_payload(name=f"Bulk Expense {i}", amount=str(10 + i))
            for i in range(100)
        ]

        response = self._push("expense", records)
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["synced"], 100)
        self.assertEqual(body["conflicts"], 0)
        self.assertEqual(body["errors"], [])
        self.assertEqual(Expense.objects.count(), 100)

        latest_log = SyncLog.objects.filter(direction="push", model_name="expense").first()
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.records_count, 100)

    def test_debug_endpoints_clear_data_and_logs(self):
        self._push("expense", [self._expense_payload(name="To Clear")])
        self.assertEqual(Expense.objects.count(), 1)
        self.assertGreaterEqual(SyncLog.objects.count(), 1)

        response = self.client.post(
            self.clear_url,
            data=json.dumps({"model": "expense"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["cleared_model"], "expense")
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(SyncLog.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_debug_endpoints_blocked_when_debug_false(self):
        self.assertEqual(self.client.get(self.queue_url).status_code, 403)
        self.assertEqual(self.client.get(self.status_url).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.clear_url,
                data=json.dumps({"model": "expense"}),
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_ping_requires_login_and_returns_online(self):
        self.assertEqual(self.client.get(self.ping_url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(self.ping_url).status_code, 302)

    def test_offline_fallback_route_is_available_without_login(self):
        self.client.logout()
        response = self.client.get(self.offline_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="pending-count"')

    def test_service_worker_includes_offline_fallback(self):
        self.client.logout()
        response = self.client.get(self.sw_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/javascript"))
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response["Cache-Control"])

        body = response.content.decode("utf-8")
        self.assertIn("OFFLINE_FALLBACK_URL", body)
        self.assertIn("/offline/", body)

    def test_service_worker_includes_all_route_fallbacks(self):
        self.client.logout()
        response = self.client.get(self.sw_url)

        self.assertEqual(response.status_code, 200)

        body = response.content.decode("utf-8")
        self.assertIn("NAVIGATION_ROUTE_FALLBACKS", body)
        self.assertIn("/accounts/", body)
        self.assertIn("/groups/", body)
        self.assertIn("/members/", body)
        self.assertIn("/finance/", body)
        self.assertIn("/reports/", body)
        self.assertIn("/accounts/users/create/", body)
        self.assertIn("/accounts/notifications/", body)
        self.assertIn("/reports/entities/", body)
        self.assertIn("dev-log-tools.js", body)
        self.assertIn("offline-diary-sync.js", body)

    def test_service_worker_includes_known_group_workspace_urls(self):
        self.client.logout()
        response = self.client.get(self.sw_url)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn(f"/groups/{self.workspace_group.pk}/", body)
        self.assertIn(f"/members/group/{self.workspace_group.pk}/add/", body)
        self.assertIn(f"/finance/group/{self.workspace_group.pk}/forms/", body)

    def test_service_worker_skips_api_requests(self):
        self.client.logout()
        response = self.client.get(self.sw_url)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("requestUrl.pathname.includes('/api/')", body)

    def test_web_manifest_includes_installable_png_icons(self):
        self.client.logout()
        response = self.client.get(self.manifest_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/manifest+json"))
        self.assertIn("no-cache", response["Cache-Control"])

        body = response.json()
        self.assertEqual(body.get("display"), "standalone")

        icon_sources = {icon.get("src") for icon in body.get("icons", [])}
        self.assertIn("/static/img/pwa-icon-192.png", icon_sources)
        self.assertIn("/static/img/pwa-icon-512.png", icon_sources)
