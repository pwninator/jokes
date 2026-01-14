
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto("http://127.0.0.1:5000/admin/jokes")

        # Check if joke card exists
        card = page.locator(".joke-card").first
        if not card.is_visible():
            print("Joke card not visible!")
            print(page.content())
            return

        # Locate the regenerate button
        regenerate_btn = page.locator(".joke-regenerate-button").first
        expect(regenerate_btn).to_be_visible()

        # Click it
        regenerate_btn.click()

        # Check if modal opens
        modal = page.locator("#admin-regenerate-modal")
        expect(modal).to_be_visible()

        # Check if options are populated
        select = page.locator("#admin-regenerate-quality")
        expect(select).to_be_visible()

        # Take screenshot
        page.screenshot(path="verification/regenerate_modal.png")
        print("Verification successful, screenshot saved.")

    except Exception as e:
        print(f"Verification failed: {e}")
        try:
            print("Page content dump:")
            print(page.content())
        except:
            pass
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
