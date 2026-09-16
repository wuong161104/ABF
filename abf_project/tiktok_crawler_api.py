"""
FastAPI Microservice Cào Dữ Liệu TikTok & Social Media Comments THỰC TẾ (ABF Solution)
CAM KẾT: 100% Cào dữ liệu THỰC TẾ từ URL bài đăng, KHÔNG MOCK, FULL ALL KHÔNG GIỚI HẠN.
"""

import os
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from real_crawler import (
    scrape_real_comments_from_url,
    save_real_comments_to_db,
    discover_channel_video_urls
)

load_dotenv()

app = FastAPI(
    title="ABF Real Social & TikTok Scraper API",
    description="Microservice cào dữ liệu comment THỰC TẾ từ bài đăng TikTok, FB, Zalo & Web (FULL ALL)",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "ABF Real Data Crawler Microservice (FULL UNLIMITED)",
        "mock_data_enabled": False,
        "endpoints": [
            "GET /get-channel-videos?url=https://www.tiktok.com/@baothetindung.abf (Lấy TOÀN BỘ link bài đăng)",
            "GET /crawl-tiktok?url=https://www.tiktok.com/@user/video/123... (Cào FULL 100% comment thực tế)"
        ]
    }

@app.get("/get-channel-videos")
def get_channel_videos(
    url: Optional[str] = Query("https://www.tiktok.com/@baothetindung.abf", description="URL kênh TikTok cần lấy bài đăng"),
    limit: Optional[int] = Query(999999, description="Số lượng video cần lấy (Mac định FULL ALL)")
):
    """
    [BƯỚC 1 & 2]: Lấy TOÀN BỘ (FULL ALL) danh sách các link video bài đăng thực tế từ kênh TikTok.
    """
    target_url = url or "https://www.tiktok.com/@baothetindung.abf"
    video_urls = discover_channel_video_urls(target_url, limit=limit or 999999)
    
    return {
        "status": "success",
        "channel_url": target_url,
        "total_videos_found": len(video_urls),
        "timestamp": datetime.now().isoformat(),
        "video_urls": video_urls
    }

@app.get("/crawl-tiktok")
@app.get("/crawl")
def crawl_endpoint(
    url: Optional[str] = Query(None, description="URL bài đăng TikTok, FB hoặc danh sách URL phân cách bởi dấu phẩy"),
    target: Optional[str] = Query(None, description="Tham số phụ từ n8n (nếu truyền URL qua target)"),
    limit: Optional[int] = Query(999999, description="Số lượng comment tối đa (Mặc định FULL ALL)")
):
    """
    [BƯỚC 3]: Cào FULL 100% comment thực tế từ URL bài đăng/video và lưu vào Supabase DB.
    """
    target_url = url or target or "https://www.tiktok.com/@baothetindung.abf"
    num_limit = limit or 999999
    
    print(f"🚀 [API GET /crawl FULL] Nhận yêu cầu cào FULL THỰC TẾ cho URL: {target_url} (limit: {num_limit})")
    
    crawled_data = scrape_real_comments_from_url(target_url, num_limit)
    saved_count = save_real_comments_to_db(crawled_data)

    return {
        "status": "success",
        "target_url": target_url,
        "is_real_data": True,
        "mock_fallback_used": False,
        "total_crawled": len(crawled_data),
        "total_saved_to_db": saved_count,
        "timestamp": datetime.now().isoformat(),
        "data": crawled_data,
        "message": "Đã cào dữ liệu THỰC TẾ FULL thành công." if len(crawled_data) > 0 else "Không tìm thấy comment thực tế hoặc bài đăng không có bình luận công khai."
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8005))
    print(f"🚀 Đang khởi chạy ABF Real Data Scraper API (FULL UNLIMITED) trên port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
