from __future__ import annotations

import json
import time
import urllib.request
from datetime import date
from typing import Any, Dict

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "0700000999"
PASSWORD = "ui-smoke-pass"


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

            seed_name = "UI Offline Flow " + str(int(time.time()))
            seed_date = date.today().isoformat()
            page.evaluate(
                """
                async (payload) => {
                    if (!window.seepoOfflineSync || typeof window.seepoOfflineSync.saveOffline !== 'function') {
                        throw new Error('seepoOfflineSync unavailable');
                    }

                    const group = await window.seepoOfflineSync.saveOffline('group', {
                        name: payload.name,
                        location: 'Nairobi',
                        date_created: payload.date,
                        officer_name: 'Browser Smoke Officer',
                        banking_type: 'office'
                    });

                    await window.seepoOfflineSync.saveOffline('member', {
                        group_client_uuid: group.client_uuid,
                        member_number: 1,
                        name: 'Browser Smoke Member',
                        phone: '0700000123',
                        join_date: payload.date,
                        is_active: true
                    });

                    await window.seepoOfflineSync.saveOffline('monthly_form', {
                        group_client_uuid: group.client_uuid,
                        month: 4,
                        year: 2026,
                        status: 'draft',
                        notes: 'Browser smoke pending form'
                    });

                    if (typeof window.seepoOfflineSync.refreshStatus === 'function') {
                        await window.seepoOfflineSync.refreshStatus();
                    }

                    window.dispatchEvent(new Event('seepo:queue-status'));
                }
                """,
                {"name": seed_name, "date": seed_date},
            )

            context.set_offline(True)
            page.evaluate("window.dispatchEvent(new Event('offline'))")
            page.evaluate("window.dispatchEvent(new Event('seepo:queue-status'))")
            page.wait_for_timeout(700)

            page.evaluate(
                """
                (targetName) => {
                    const buttons = Array.from(document.querySelectorAll("button[data-action='open-workspace']"));
                    const target = buttons.find((button) =>
                        String(button.getAttribute('data-group-name') || '').includes(targetName)
                    );

                    if (!target) {
                        throw new Error('Pending group workspace button not found');
                    }

                    target.click();
                }
                """,
                seed_name,
            )

            page.wait_for_url("**/groups/offline/workspace/**", timeout=10000)
            workspace_url = page.url
            record("offline_workspace_full_page_navigation", "/groups/offline/workspace/" in workspace_url, workspace_url)

            page.wait_for_timeout(700)
            members_count = page.locator("#offline-members-count").inner_text().strip()
            forms_count = page.locator("#offline-forms-count").inner_text().strip()
            has_cached_data = members_count != "0" and forms_count != "0"
            record("offline_workspace_cached_data_visible", has_cached_data, f"members={members_count}, forms={forms_count}")

            page.wait_for_selector("button[data-form-action='open-detail']", timeout=8000)
            page.click("button[data-form-action='open-detail']")
            page.wait_for_url("**/finance/forms/offline/**", timeout=10000)
            form_url = page.url
            record("offline_form_detail_full_page_navigation", "/finance/forms/offline/" in form_url, form_url)

            page.wait_for_selector("#offlineFinanceTable", timeout=8000)
            rows_count = page.locator("#offline-finance-table-body tr.record-row").count()
            record("offline_form_detail_rows_rendered", rows_count > 0, f"rows={rows_count}")

            if rows_count > 0:
                first_row = page.locator("#offline-finance-table-body tr.record-row").first
                first_row.locator("input[data-field='savings_share_bf']").fill("1000")
                first_row.locator("input[data-field='loan_balance_bf']").fill("500")
                first_row.locator("input[data-field='total_repaid']").fill("400")
                first_row.locator("input[data-field='principal']").fill("200")
                page.click("#offlineManualSaveBtn")
                page.wait_for_timeout(700)

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
