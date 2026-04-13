from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any, Dict

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
PHONE = "0700000999"
PASSWORD = "ui-smoke-pass"


RED_RGB = "rgb(220, 53, 69)"
WHITE_RGB = "rgb(255, 255, 255)"
MUTED_RGB = "rgb(128, 129, 145)"


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
    raise RuntimeError("Server not reachable on /accounts/login/")


def run() -> Dict[str, Any]:
    wait_for_server()
    results: Dict[str, Any] = {"checks": [], "errors": []}

    def record(name: str, passed: bool, detail: str) -> None:
        results["checks"].append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(BASE_URL + "/accounts/login/", wait_until="domcontentloaded")

            # Install button must stay hidden unless beforeinstallprompt is available.
            install_hidden = page.locator("#pwa-install-btn").is_hidden()
            record(
                "login_install_button_hidden_by_default",
                install_hidden,
                f"hidden={install_hidden}",
            )

            page.fill("#id_username", PHONE)
            page.fill("#id_password", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("domcontentloaded")
            logged_in = "/accounts/login/" not in page.url
            record("login_success", logged_in, f"url={page.url}")

            if not logged_in:
                raise RuntimeError("Login failed; cannot continue UI checks")

            page.goto(BASE_URL + "/groups/", wait_until="domcontentloaded")
            page.wait_for_selector("a.workspace-action-btn", timeout=10000)
            workspace_href = page.locator("a.workspace-action-btn").first.get_attribute("href") or ""
            if not workspace_href:
                raise RuntimeError("Could not find workspace link on groups page")

            if not workspace_href.startswith("http"):
                workspace_url = BASE_URL + workspace_href
            else:
                workspace_url = workspace_href

            if not re.search(r"/groups/\d+/", workspace_url):
                raise RuntimeError(f"Unexpected workspace URL format: {workspace_url}")

            page.goto(workspace_url, wait_until="domcontentloaded")
            page.wait_for_selector("#members-tab", timeout=10000)
            page.wait_for_selector("#forms-tab", timeout=10000)

            # Click Monthly Forms and validate active/inactive styling.
            page.click("#forms-tab")
            page.wait_for_timeout(300)

            forms_bg = page.eval_on_selector("#forms-tab", "el => getComputedStyle(el).backgroundColor")
            forms_color = page.eval_on_selector("#forms-tab", "el => getComputedStyle(el).color")
            members_bg_when_forms = page.eval_on_selector("#members-tab", "el => getComputedStyle(el).backgroundColor")
            members_color_when_forms = page.eval_on_selector("#members-tab", "el => getComputedStyle(el).color")

            record(
                "monthly_tab_active_red",
                forms_bg == RED_RGB and forms_color == WHITE_RGB,
                f"forms_bg={forms_bg}, forms_color={forms_color}",
            )
            record(
                "members_tab_inactive_when_monthly_active",
                members_color_when_forms == MUTED_RGB and members_bg_when_forms in ("rgba(0, 0, 0, 0)", "transparent"),
                f"members_bg={members_bg_when_forms}, members_color={members_color_when_forms}",
            )

            # Click Members and verify it now matches the same active style.
            page.click("#members-tab")
            page.wait_for_timeout(300)

            members_bg = page.eval_on_selector("#members-tab", "el => getComputedStyle(el).backgroundColor")
            members_color = page.eval_on_selector("#members-tab", "el => getComputedStyle(el).color")
            forms_bg_when_members = page.eval_on_selector("#forms-tab", "el => getComputedStyle(el).backgroundColor")
            forms_color_when_members = page.eval_on_selector("#forms-tab", "el => getComputedStyle(el).color")

            record(
                "members_tab_active_same_style_as_monthly",
                members_bg == RED_RGB and members_color == WHITE_RGB,
                f"members_bg={members_bg}, members_color={members_color}",
            )
            record(
                "monthly_tab_inactive_when_members_active",
                forms_color_when_members == MUTED_RGB and forms_bg_when_members in ("rgba(0, 0, 0, 0)", "transparent"),
                f"forms_bg={forms_bg_when_members}, forms_color={forms_color_when_members}",
            )

        except Exception as exc:
            results["errors"].append(str(exc))
        finally:
            context.close()
            browser.close()

    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
