from playwright.sync_api import sync_playwright
import time
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.vpbank.com.vn/', wait_until='networkidle', timeout=30000)
    time.sleep(2)
    
    # 1. Inspect all <a>
    all_a = page.query_selector_all('a[href]')
    print(f"Total <a> tags: {len(all_a)}")
    for a in all_a:
        print(f"  <a> href={a.get_attribute('href')} | text={a.inner_text().strip()}")
        
    # 2. Check next data or scripts
    scripts = page.query_selector_all('script#__NEXT_DATA__')
    if scripts:
        print("Found __NEXT_DATA__!")
        try:
            data = json.loads(scripts[0].inner_text())
            print(f"Next data keys: {list(data.keys())}")
            # check pageProps
            props = data.get('props', {}).get('pageProps', {})
            print(f"pageProps keys: {list(props.keys())}")
        except Exception as e:
            print("Error parsing next data:", e)
            
    # 3. Check what happens if we hover or click on menu items like 'Cá nhân' (/ca-nhan)
    ca_nhan_btn = page.query_selector("a[href='/ca-nhan'], a:has-text('Cá nhân')")
    if ca_nhan_btn:
        print("Found Ca Nhan button/link, hovering...")
        ca_nhan_btn.hover()
        time.sleep(1)
        all_a_after = page.query_selector_all('a[href]')
        print(f"Total <a> tags after hover: {len(all_a_after)}")
        
    browser.close()
