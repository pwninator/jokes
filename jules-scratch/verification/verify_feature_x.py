
from playwright.sync_api import sync_playwright, expect
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:36999")
    time.sleep(10)
    expect(page.get_by_text("Daily Jokes")).to_be_visible(timeout=30000)
    page.screenshot(path="jules-scratch/verification/verification.png")
    browser.close()
