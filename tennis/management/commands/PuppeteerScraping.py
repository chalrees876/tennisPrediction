from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.tennisabstract.com/cgi-bin/player-more.cgi?p=207989/Carlos-Alcaraz&table=pbp-stats")

    # Wait for specific element or content to load
    page.wait_for_selector("pbp_stats")  # or
    page.wait_for_function("window.yourData !== undefined")

    # Get the rendered HTML
    html = page.content()
    print(html)
    browser.close()