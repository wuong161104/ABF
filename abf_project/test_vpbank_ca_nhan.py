from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.vpbank.com.vn/', wait_until='networkidle', timeout=30000)
    time.sleep(2)
    
    # Check what happens if we navigate to /ca-nhan
    print("Navigating to https://www.vpbank.com.vn/ca-nhan ...")
    page.goto('https://www.vpbank.com.vn/ca-nhan', wait_until='networkidle', timeout=30000)
    time.sleep(2)
    
    all_a = page.query_selector_all('a[href]')
    print(f"Total <a> tags on /ca-nhan: {len(all_a)}")
    for i, a in enumerate(all_a[:30]):
        href = a.get_attribute('href')
        txt = a.inner_text().strip().replace('\n', ' ')
        print(f"  [{i}] {href} -> {txt}")
        
    # Check sitemap
    browser.close()
