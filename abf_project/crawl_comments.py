"""
Module Thu Thập Dữ Liệu Comment Thực Tế (TikTok, Facebook, Zalo, Web) - ABF Solution
NÓI KHÔNG VỚI MOCK DATA.
"""

import sys
import argparse
from real_crawler import scrape_real_comments_from_url, save_real_comments_to_db

def main():
    parser = argparse.ArgumentParser(description="Cào dữ liệu comment thực tế từ URL Social Media")
    parser.add_argument("--url", type=str, default="https://www.tiktok.com/@baothetindung.abf", help="URL bài đăng/kênh cần cào")
    parser.add_argument("--limit", type=int, default=30, help="Số lượng comment tối đa")
    args = parser.parse_args()

    print(f"🚀 [CRAWL COMMENTS] Bắt đầu cào dữ liệu THỰC TẾ từ URL: {args.url}")
    crawled_data = scrape_real_comments_from_url(args.url, args.limit)
    saved_count = save_real_comments_to_db(crawled_data)
    print(f"🎉 Hoàn thành! Đã cào {len(crawled_data)} comment thực tế và lưu {saved_count} bản ghi mới vào Supabase DB.")

if __name__ == "__main__":
    main()
