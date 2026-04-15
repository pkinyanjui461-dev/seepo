from playwright.sync_api import sync_playwright

BASE_URL = 'http://127.0.0.1:8000/accounts/login/'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(BASE_URL, wait_until='domcontentloaded')
    page.evaluate("window.sessionStorage.setItem('seepoSwRefreshedToastV1', String(Date.now()));")
    page.reload(wait_until='domcontentloaded')

    page.wait_for_selector('#sw-refresh-toast', timeout=4000)
    text = page.locator('#sw-refresh-toast').inner_text().strip()
    print('toast_visible', True)
    print('toast_text', text)

    # Verify one-time behavior: next reload should consume and remove flag.
    page.reload(wait_until='domcontentloaded')
    toast_count = page.locator('#sw-refresh-toast').count()
    print('toast_after_second_reload', toast_count)

    context.close()
    browser.close()
