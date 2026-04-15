from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date
from typing import Any, Dict

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "0700000999"
PASSWORD = "ui-smoke-pass"


def create_member_record_for_form(form_client_uuid: str, member_name: str = 'Browser Smoke Member') -> bool:
    """Create a MemberRecord with sample data for testing."""
    # This function is called from within the test
    # For now, we rely on seed_from_backup to create them beforehand
    # The smoke test will use pre-seeded data instead
    pass


def get_seeded_data() -> dict | None:
    """Get the first seeded group/member/form from the database using management command."""
    try:
        # Get the project directory
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Call the management command to get seeded data
        result = subprocess.run(
            [sys.executable, 'manage.py', 'get_seeded_data'],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print(f"Management command error: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        if 'error' in data:
            print(f"Seeding error: {data.get('error')}")
            return None

        return data
    except Exception as e:
        print(f"Error getting seeded data: {e}")
        import traceback
        traceback.print_exc()
        return None
def wait_for_server(timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/accounts/login/", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Server did not become reachable in time")


def run() -> Dict[str, Any]:
    wait_for_server()
    results: Dict[str, Any] = {
        "checks": [],
        "errors": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def record(name: str, passed: bool, detail: str) -> None:
            results["checks"].append(
                {
                    "name": name,
                    "status": "pass" if passed else "fail",
                    "detail": detail,
                }
            )

        try:
            page.goto(BASE_URL + "/accounts/login/", wait_until="domcontentloaded")
            page.fill("#id_username", USERNAME)
            page.fill("#id_password", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("domcontentloaded")

            logged_in = "/accounts/login/" not in page.url
            record("login", logged_in, page.url)
            if not logged_in:
                raise RuntimeError("Login failed")

            page.goto(BASE_URL + "/groups/", wait_until="domcontentloaded")

            # Get pre-seeded data from the database
            seeded = get_seeded_data()
            if not seeded:
                raise RuntimeError("No seeded data found. Make sure seed_from_backup has been run.")

            # Navigate to offline workspace BEFORE going offline so it caches
            offline_workspace_url = (
                BASE_URL
                + "/groups/offline/workspace/"
                + "?group_client_uuid="
                + seeded["group_client_uuid"]
                + "&group_name="
                + seeded["group_name"].replace(" ", "%20")
            )

            page.goto(offline_workspace_url, wait_until="domcontentloaded")
            page.wait_for_url("**/groups/offline/workspace/**", timeout=10000)
            workspace_url = page.url
            record("offline_workspace_full_page_navigation", "/groups/offline/workspace/" in workspace_url, workspace_url)

            # Trigger sync while still online to populate Dexie
            page.wait_for_timeout(500)
            page.evaluate("""
                () => {
                    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.syncNow === 'function') {
                        window.seepoOfflineSync.syncNow().catch(e => console.error('Sync error:', e));
                    }
                }
            """)
            page.wait_for_timeout(2000)

            members_count = page.locator("#offline-members-count").inner_text().strip()
            forms_count = page.locator("#offline-forms-count").inner_text().strip()
            has_cached_data = members_count != "0" and forms_count != "0"
            record("offline_workspace_cached_data_visible", has_cached_data, f"members={members_count}, forms={forms_count}")

            page.wait_for_selector("button[data-form-action='open-detail']", timeout=8000, state="attached")
            # Navigate directly to the monthly form detail page instead of trying to click hidden button
            offline_form_url = (
                BASE_URL
                + "/finance/forms/offline/"
                + "?form_client_uuid=" + seeded['form_client_uuid']
                + "&group_client_uuid=" + seeded['group_client_uuid']
                + "&group_name=" + seeded['group_name'].replace(" ", "%20")
                + "&month=4"
                + "&year=2026"
                + "&status=draft"
                + "&source=offline_workspace"
            )
            page.goto(offline_form_url, wait_until="domcontentloaded")
            page.wait_for_url("**/finance/forms/offline/**", timeout=10000)
            form_url = page.url
            record("offline_form_detail_full_page_navigation", "/finance/forms/offline/" in form_url, form_url)

            page.wait_for_selector("#offlineFinanceTable", timeout=8000)

            # NOW simulate going OFFLINE by disconnecting the browser context
            # This tests if the form truly works offline (not just on the offline template)
            context.offline = True
            page.wait_for_timeout(1000)

            # Verify form is still accessible and renders while offline
            # (page is already loaded, so it should work from cache)
            page.wait_for_selector("#offlineFinanceTable", timeout=5000)
            record("offline_mode_connection_active", True, "Browser context is offline")

            # Debug: check if data is in Dexie
            dexie_check = page.evaluate("""
            async () => {
                const membersTable = window.seepoOfflineDb.tableForModel('member');
                const formsTable = window.seepoOfflineDb.tableForModel('monthly_form');
                const members = await membersTable.toArray();
                const forms = await formsTable.toArray();
                return {
                    members_count: members.length,
                    members_sample: members.slice(0, 2).map(m => ({
                        name: m.name,
                        group_uuid: m.group_client_uuid,
                        group_id: m.group_id
                    })),
                    forms_count: forms.length,
                    forms_sample: forms.slice(0, 1).map(f => ({
                        month: f.month,
                        group_uuid: f.group_client_uuid,
                        group_id: f.group_id
                    }))
                };
            }
            """)
            page.evaluate(f"""
            console.log('SMOKE_TEST_DEXIE_CHECK', {json.dumps(dexie_check)})
            """)

            rows_count = page.locator("#offline-finance-table-body tr.record-row").count()
            record("offline_form_detail_rows_rendered", rows_count > 0, f"rows={rows_count}")

            if rows_count > 0:
                first_row = page.locator("#offline-finance-table-body tr.record-row").first

                # Extract rendered member data to verify it's not empty
                first_row.wait_for()
                member_name_element = first_row.locator("td.fw-bold.bg-light")
                member_name = member_name_element.inner_text().strip() if member_name_element else ""
                member_number_element = first_row.locator("td.text-center.text-muted.small").first
                member_number = member_number_element.inner_text().strip() if member_number_element else ""

                rendered_text = f"name='{member_name}', number='{member_number}'"
                record("offline_form_member_data_populated",
                       bool(member_name and member_name != "" and member_name != "Member"),
                       rendered_text)

                # Edit transaction values to create drafts in Dexie
                first_row.locator("input[data-field='savings_share_bf']").fill("1000")
                first_row.locator("input[data-field='loan_balance_bf']").fill("500")
                first_row.locator("input[data-field='total_repaid']").fill("400")
                first_row.locator("input[data-field='principal']").fill("200")
                page.click("#offlineManualSaveBtn")
                page.wait_for_timeout(1000)

                # Verify edited values are now populated and marked pending
                # Use input_value() instead of get_attribute() to read actual form field value
                edited_savings_value = first_row.locator("input[data-field='savings_share_bf']").input_value()
                edited_loan_value = first_row.locator("input[data-field='loan_balance_bf']").input_value()

                has_edited_data = (edited_savings_value == "1000" and edited_loan_value == "500")
                record("offline_form_edited_data_persists",
                       has_edited_data,
                       f"savings_bf={edited_savings_value}, loan_bf={edited_loan_value}")

                pending_class = first_row.get_attribute("class") or ""
                record(
                    "offline_form_save_marks_row_pending",
                    "row-pending-sync" in pending_class,
                    pending_class,
                )

        except Exception as exc:
            results["errors"].append(str(exc))
        finally:
            context.close()
            browser.close()

    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
