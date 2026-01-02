
from playwright.sync_api import sync_playwright, expect
import time

def verify_joke_search():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the page
        print("Navigating to mock page...")
        page.goto("http://localhost:5000/admin/joke-books/book-123")

        # Wait for search input
        expect(page.locator("#joke-search-input")).to_be_visible()

        # Type search query
        print("Typing search query...")
        page.fill("#joke-search-input", "test query")

        # Intercept the request to verify params
        with page.expect_request(lambda request: "search_jokes" in request.url and "exclude_in_book=true" in request.url) as request_info:
            print("Clicking search button...")
            page.click("#joke-search-btn")

        print("Request verified: exclude_in_book=true present")

        # Wait for results
        expect(page.locator("#search-results")).to_be_visible()

        # Verify results are displayed
        # The mock server returns 'joke-new-1' and 'joke-1'.
        # 'joke-1' is in the book.
        # Since we removed CLIENT-SIDE filtering, ALL results returned by server should show up.
        # The SERVER (mock in this case) returns both.
        # In production, the server would filter 'joke-1' out because we passed exclude_in_book=true.
        # But here we just want to verify the client behaves as expected (shows what server returns).

        # Wait for results to populate
        page.wait_for_selector(".search-result-card")

        cards = page.locator(".search-result-card")
        count = cards.count()
        print(f"Found {count} result cards.")

        # Take screenshot
        page.screenshot(path="verification/verification.png")
        print("Screenshot saved to verification/verification.png")

        browser.close()

if __name__ == "__main__":
    verify_joke_search()
