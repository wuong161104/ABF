"""
Script Python cào Comment TikTok THỰC TẾ (Không dữ liệu mẫu)
Được thiết kế để n8n node 'Execute Command' gọi trực tiếp qua CLI.
Cú pháp chạy: python crawl_tiktok_n8n.py --target "https://www.tiktok.com/@baothetindung.abf" --limit 30
"""

import sys
import json
import argparse
from datetime import datetime
from real_crawler import scrape_real_comments_from_url, save_real_comments_to_db

def main():
    parser = argparse.ArgumentParser(description="Real TikTok/Social Comment Scraper for n8n")
    parser.add_argument("--target", "--url", type=str, default="https://www.tiktok.com/@baothetindung.abf", help="URL bài đăng hoặc Kênh TikTok cần cào")
    parser.add_argument("--limit", type=int, default=30, help="Số lượng comment thực tế muốn cào")
    args = parser.parse_args()

    target_url = args.target
    if not target_url.startswith("http"):
        target_url = f"https://www.tiktok.com/@{target_url.lstrip('@')}"

    # 1. Tiến hành cào THỰC TẾ
    crawled_data = scrape_real_comments_from_url(target_url, args.limit)
    
    # 2. Lưu DB Supabase
    saved_count = save_real_comments_to_db(crawled_data)

    # 3. Xuất JSON ra STDOUT cho n8n đọc
    output = {
        "status": "success",
        "target_url": target_url,
        "is_real_data": True,
        "total_crawled": len(crawled_data),
        "total_saved_to_db": saved_count,
        "timestamp": datetime.now().isoformat(),
        "data": crawled_data
    }
    
    # In ra STDOUT để n8n node Execute Command nhận được JSON
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
