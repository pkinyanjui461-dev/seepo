from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "0700000999"
PASSWORD = "ui-smoke-pass"
GROUP_DETAIL_PATH = "/groups/10/"
GROUP_LIST_PATH = "/groups/"
MONTHLY_FORM_LIST_PATH = "/finance/group/10/forms/"


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


def class_has(locator, class_name: str) -> bool:
    value = locator.get_attribute("class") or ""
    return class_name in value.split()


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

        def record(name: str, status: str, detail: str) -> None:
            results["checks"].append({"name": name, "status": status, "detail": detail})

        try:
            page.goto(BASE_URL + "/accounts/login/", wait_until="domcontentloaded")
            page.fill("#id_username", USERNAME)
            page.fill("#id_password", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("domcontentloaded")

            if "/accounts/login/" in page.url:
                record("login", "fail", "Still on login page after submit")
            else:
                record("login", "pass", "Login succeeded")

            # Online state: offline-only member button should be hidden
            page.goto(BASE_URL + GROUP_DETAIL_PATH, wait_until="domcontentloaded")
            online_hidden = class_has(page.locator("#add-offline-member-btn"), "d-none")
            record(
                "group_detail_online_offline_button_hidden",
                "pass" if online_hidden else "fail",
                f"d-none={online_hidden}",
            )

            # Offline state: button visible and opens modal
            context.set_offline(True)
            page.evaluate("window.dispatchEvent(new Event('offline'))")
            page.wait_for_timeout(600)
            offline_hidden = class_has(page.locator("#add-offline-member-btn"), "d-none")
            record(
                "group_detail_offline_offline_button_visible",
                "pass" if not offline_hidden else "fail",
                f"d-none={offline_hidden}",
            )

            page.click("#add-offline-member-btn")
            page.wait_for_selector("#offline-member-edit-modal.show", timeout=4000)
            record("group_detail_member_modal_open", "pass", "Offline member modal opened")
            page.click("#offline-member-edit-modal [data-bs-dismiss='modal']")
            page.wait_for_selector("#offline-member-edit-modal.show", state="detached", timeout=4000)

            # Snapshot FAB + modal in offline state
            fab_hidden = class_has(page.locator("#workspace-snapshot-fab"), "d-none")
            record(
                "group_detail_snapshot_fab_visible_offline",
                "pass" if not fab_hidden else "fail",
                f"d-none={fab_hidden}",
            )
            page.click("#workspace-snapshot-fab")
            page.wait_for_selector("#offline-workspace-snapshot-modal.show", timeout=4000)
            record("group_detail_snapshot_modal_open", "pass", "Snapshot modal opened")
            page.evaluate(
                """
                () => {
                    const modalEl = document.getElementById('offline-workspace-snapshot-modal');
                    if (!modalEl || !window.bootstrap || !window.bootstrap.Modal) {
                        return;
                    }
                    const instance = window.bootstrap.Modal.getOrCreateInstance(modalEl);
                    instance.hide();
                }
                """
            )
            page.wait_for_selector("#offline-workspace-snapshot-modal.show", state="detached", timeout=4000)

            # Create pending offline group to test workspace modal stacking
            context.set_offline(False)
            page.evaluate("window.dispatchEvent(new Event('online'))")
            page.goto(BASE_URL + GROUP_LIST_PATH, wait_until="domcontentloaded")
            page.evaluate(
                """
                async () => {
                    if (!window.seepoOfflineSync || typeof window.seepoOfflineSync.saveOffline !== 'function') {
                        throw new Error('seepoOfflineSync unavailable');
                    }
                    await window.seepoOfflineSync.saveOffline('group', {
                        name: 'UI Pending Browser Group',
                        location: 'Nairobi',
                        date_created: '2026-04-13',
                        officer_name: 'UI Browser Officer',
                        banking_type: 'office'
                    });
                    if (typeof window.seepoOfflineSync.refreshStatus === 'function') {
                        await window.seepoOfflineSync.refreshStatus();
                    }
                    window.dispatchEvent(new Event('seepo:queue-status'));
                }
                """
            )

            context.set_offline(True)
            page.evaluate("window.dispatchEvent(new Event('offline'))")
            page.evaluate("window.dispatchEvent(new Event('seepo:queue-status'))")
            page.wait_for_selector("button[data-action='open-workspace']", timeout=7000)
            page.evaluate(
                """
                () => {
                    const buttons = Array.from(document.querySelectorAll("button[data-action='open-workspace']"));
                    const target = buttons.find((button) =>
                        String(button.getAttribute('data-group-name') || '').includes('UI Pending Browser Group')
                    ) || buttons[0];
                    if (!target) {
                        throw new Error('No open-workspace button found');
                    }
                    target.click();
                }
                """
            )
            page.wait_for_selector("#offline-workspace-modal.show", timeout=4000)
            record("group_list_workspace_modal_open", "pass", "Workspace modal opened for pending group")

            page.click("#offline-workspace-add-member-btn")
            page.wait_for_selector("#offline-member-modal.show", timeout=4000)
            workspace_still_visible = page.locator("#offline-workspace-modal.show").count() > 0
            record(
                "group_list_modal_stacking_member",
                "pass" if not workspace_still_visible else "fail",
                f"workspace_visible_while_child_open={workspace_still_visible}",
            )
            page.click("#offline-member-modal [data-bs-dismiss='modal']")
            page.wait_for_selector("#offline-workspace-modal.show", timeout=4000)
            record("group_list_workspace_restored_after_member", "pass", "Workspace modal restored")

            page.click("#offline-workspace-add-form-btn")
            page.wait_for_selector("#offline-monthly-form-modal.show", timeout=4000)
            workspace_still_visible_form = page.locator("#offline-workspace-modal.show").count() > 0
            record(
                "group_list_modal_stacking_form",
                "pass" if not workspace_still_visible_form else "fail",
                f"workspace_visible_while_form_open={workspace_still_visible_form}",
            )
            page.click("#offline-monthly-form-modal [data-bs-dismiss='modal']")
            page.wait_for_selector("#offline-workspace-modal.show", timeout=4000)
            page.click("#offline-workspace-modal [data-bs-dismiss='modal']")

            # Monthly form list offline mock sheet open/save
            context.set_offline(False)
            page.evaluate("window.dispatchEvent(new Event('online'))")
            page.goto(BASE_URL + MONTHLY_FORM_LIST_PATH, wait_until="domcontentloaded")
            page.evaluate(
                """
                async () => {
                    const html = document.documentElement.innerHTML;
                    const match = html.match(/const groupClientUuid = '([^']+)'/);
                    const groupClientUuid = match ? match[1] : null;
                    if (!groupClientUuid) {
                        throw new Error('groupClientUuid not found');
                    }
                    if (!window.seepoOfflineSync || typeof window.seepoOfflineSync.saveOffline !== 'function') {
                        throw new Error('seepoOfflineSync unavailable');
                    }
                    await window.seepoOfflineSync.saveOffline('monthly_form', {
                        group_client_uuid: groupClientUuid,
                        month: 4,
                        year: 2026,
                        status: 'draft',
                        notes: 'UI browser pending form'
                    });
                    if (typeof window.seepoOfflineSync.refreshStatus === 'function') {
                        await window.seepoOfflineSync.refreshStatus();
                    }
                    window.dispatchEvent(new Event('seepo:queue-status'));
                }
                """
            )
            context.set_offline(True)
            page.evaluate("window.dispatchEvent(new Event('offline'))")
            page.evaluate("window.dispatchEvent(new Event('seepo:queue-status'))")
            page.wait_for_selector("button[data-offline-form-action='open-sheet']", timeout=7000)
            page.click("button[data-offline-form-action='open-sheet']")
            page.wait_for_selector("#offline-pending-form-sheet-modal.show", timeout=4000)
            page.fill("#offline-sheet-deposits", "1000")
            page.fill("#offline-sheet-fines", "200")
            page.fill("#offline-sheet-expenses", "150")
            page.fill("#offline-sheet-members-expected", "15")
            page.fill("#offline-sheet-members-paid", "12")
            page.click("#offline-sheet-save-btn")
            page.wait_for_selector("#offline-pending-form-sheet-modal.show", state="detached", timeout=4000)
            record("monthly_form_offline_sheet_open_save", "pass", "Mock sheet opened and saved")

        except Exception as exc:
            results["errors"].append(str(exc))
        finally:
            context.close()
            browser.close()

    return results


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, indent=2))
