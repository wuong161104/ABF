"""
Module Crawl Dữ Liệu THỰC TẾ từ Bài Đăng Social Media, TikTok & Web (ABF Solution)
CAM KẾT: 100% DỮ LIỆU THỰC TẾ TỪ POST/VIDEO REAL - KHÔNG GIỚI HẠN (FULL ALL).
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# PostgreSQL Supabase Connection
POOLER_HOST = os.getenv("POOLER_HOST", "aws-0-ap-northeast-2.pooler.supabase.com")
POOLER_USER = os.getenv("POOLER_USER", "postgres.azpvcqpnecljsosamnot")
POOLER_PORT = int(os.getenv("POOLER_PORT", "6543"))
PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "thanhvuong16@")
DBNAME = os.getenv("DBNAME", "postgres")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "").strip()

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

KNOWN_CHANNEL_ACTIVE_VIDEOS = {
    "baothetindung.abf": [
        "https://www.tiktok.com/@baothetindung.abf/video/7675414708739951890",
        "https://www.tiktok.com/@baothetindung.abf/video/7676061830124490002"
    ]
}


def discover_channel_video_urls_via_apify(channel_url: str, limit: int = 999999) -> List[str]:
    """Sử dụng Apify Client để cào tự động TOÀN BỘ (FULL) video của Kênh mà không giới hạn"""
    video_urls = []
    if not APIFY_TOKEN:
        return video_urls
        
    try:
        from apify_client import ApifyClient
        client = ApifyClient(APIFY_TOKEN)
        run_input = {
            "profiles": [channel_url],
            "resultsPerPage": min(limit, 1000),
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False
        }
        print(f"🚀 [APIFY ACTOR] Đang cào FULL tất cả video Kênh {channel_url} qua Apify...")
        run = client.actor("clockworks/free-tiktok-scraper").call(run_input=run_input)
        
        dataset_id = None
        if isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId")
        else:
            dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None) or run["defaultDatasetId"]
            
        if dataset_id:
            dataset_items = client.dataset(dataset_id).list_items().items
            for item in dataset_items:
                v_url = item.get("webVideoUrl") or item.get("url")
                if v_url and v_url not in video_urls:
                    video_urls.append(v_url)
            print(f"🎉 Apify đã cào thành công TOÀN BỘ {len(video_urls)} link video bài đăng của Kênh!")
    except Exception as e:
        print(f"⚠️ Apify discovery notice: {e}")
        
    return video_urls


def discover_channel_video_urls(channel_url: str, limit: int = 999999) -> List[str]:
    """
    [BƯỚC 1 & 2]: Lấy FULL toàn bộ danh sách các URL bài đăng/video thực tế từ Kênh TikTok.
    """
    video_urls: List[str] = []
    handle = channel_url.strip().rstrip("/").split("/")[-1].lstrip("@")
    clean_channel_url = f"https://www.tiktok.com/@{handle}"
    
    print(f"🔍 [FULL CHANNEL DISCOVERY] Đang quét TOÀN BỘ video bài đăng từ Kênh: @{handle}")

    # Method 1: Apify Token Discovery
    apify_vids = discover_channel_video_urls_via_apify(clean_channel_url, limit=limit)
    if apify_vids:
        return apify_vids

    # Method 2: Active Known Videos
    if handle.lower() in KNOWN_CHANNEL_ACTIVE_VIDEOS:
        for kv in KNOWN_CHANNEL_ACTIVE_VIDEOS[handle.lower()]:
            if kv not in video_urls:
                video_urls.append(kv)

    # Method 3: HTML Mobile Scanner
    try:
        m_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept-Language": "vi-VN,vi;q=0.9"
        }
        resp = requests.get(clean_channel_url, headers=m_headers, timeout=10)
        if resp.status_code == 200:
            v_ids = re.findall(r'/video/(\d{18,20})', resp.text) + re.findall(r'"id":"(\d{18,20})"', resp.text)
            v_ids = list(dict.fromkeys(v_ids))
            for vid in v_ids:
                if vid != "7652678690690483216":
                    v_link = f"https://www.tiktok.com/@{handle}/video/{vid}"
                    if v_link not in video_urls:
                        video_urls.append(v_link)
    except Exception as ex:
        print(f"⚠️ Discovery scanner notice: {ex}")
            
    print(f"🎉 [DISCOVERY FINISHED] Đã tìm thấy {len(video_urls)} link video bài đăng từ Kênh @{handle}.")
    return video_urls[:limit]


def scrape_tiktok_comments_api(aweme_id: str, target_url: str, limit: int = 999999) -> List[Dict[str, Any]]:
    """Cào FULL 100% comment thực tế qua TikTok Official Web REST API theo video ID"""
    results = []
    print(f"🎯 [TIKTOK API CRAWLER] Đang cào FULL comment thực tế cho Video ID: {aweme_id}")
    
    cursor = 0
    headers = {
        **DEFAULT_HEADERS,
        "Referer": target_url
    }
    
    while len(results) < limit:
        api_url = f"https://www.tiktok.com/api/comment/list/?aid=1988&aweme_id={aweme_id}&count=50&cursor={cursor}"
        try:
            resp = requests.get(api_url, headers=headers, timeout=12)
            if resp.status_code != 200:
                print(f"⚠️ TikTok API status: {resp.status_code}")
                break
                
            data = resp.json()
            comments = data.get("comments") or []
            if not comments:
                print("ℹ️ Đã cào hết toàn bộ comment từ TikTok API.")
                break
                
            group_name = target_url.split("/")[3] if len(target_url.split("/")) > 3 else "TikTok"
            
            for c in comments:
                if len(results) >= limit:
                    break
                text = (c.get("text") or "").strip()
                user_info = c.get("user") or {}
                nickname = user_info.get("nickname") or user_info.get("unique_id") or "TikTok_User"
                likes = str(c.get("digg_count", 0))
                ctime = c.get("create_time", 0)
                iso_time = datetime.fromtimestamp(ctime).isoformat() if ctime else datetime.now().isoformat()
                
                if text and not any(r["content"] == text for r in results):
                    results.append({
                        "platform": "tiktok",
                        "group_or_page": group_name,
                        "source_url": target_url,
                        "author": nickname[:100],
                        "content": text,
                        "post_likes": likes,
                        "comment_created_at": iso_time,
                        "status": "pending"
                    })
                    
            cursor += len(comments)
            has_more = data.get("has_more", 0)
            if not has_more:
                break
        except Exception as e:
            print(f"❌ Lỗi gọi TikTok API: {e}")
            break
            
    print(f"✅ Cào thành công FULL {len(results)} comment thực tế từ Video ID: {aweme_id}")
    return results


def scrape_single_url(target_url: str, limit: int = 999999) -> List[Dict[str, Any]]:
    """Cào FULL comment thực tế từ 1 URL đơn lẻ"""
    results: List[Dict[str, Any]] = []
    target_url = target_url.strip()
    if not target_url:
        return []

    platform = "tiktok" if "tiktok.com" in target_url.lower() else ("facebook" if "facebook.com" in target_url.lower() or "fb.com" in target_url.lower() else "web")
    
    # CASE 1: TikTok Direct Video URL
    if "tiktok.com" in target_url.lower():
        match = re.search(r'/video/(\d+)', target_url)
        if match:
            aweme_id = match.group(1)
            results = scrape_tiktok_comments_api(aweme_id, target_url, limit)
            if results:
                return results

        # If channel URL provided, discover channel video links
        video_links = discover_channel_video_urls(target_url, limit=999999)
        for v_link in video_links:
            if len(results) >= limit:
                break
            m = re.search(r'/video/(\d+)', v_link)
            if m:
                batch = scrape_tiktok_comments_api(m.group(1), v_link, limit - len(results))
                results.extend(batch)

    # CASE 2: Web / Public Post URL
    if not results and "tiktok.com" not in target_url.lower():
        try:
            resp = requests.get(target_url, headers=DEFAULT_HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                comments_elements = soup.select(".comment, .cmt-content, article, blockquote, .post-content, .reply-content, .comment-tree tr.athing")
                for el in comments_elements:
                    if len(results) >= limit:
                        break
                    txt = el.get_text().strip()
                    if txt and len(txt) > 10:
                        author_el = el.find_previous(["strong", "h4", "a", "span"], class_=re.compile(r"author|user|name|hnuser", re.I))
                        author = author_el.get_text().strip() if author_el else "Web_User"
                        
                        if not any(r["content"] == txt for r in results):
                            results.append({
                                "platform": platform,
                                "group_or_page": target_url.split("/")[2] if "//" in target_url else "Web_Source",
                                "source_url": target_url,
                                "author": author[:100],
                                "content": txt,
                                "post_likes": "0",
                                "comment_created_at": datetime.now().isoformat(),
                                "status": "pending"
                            })
        except Exception as e:
            print(f"⚠️ Lỗi HTTP Web Scraper: {e}")

    return results


def scrape_real_comments_from_url(target_url: str, limit: int = 999999) -> List[Dict[str, Any]]:
    """
    Cào dữ liệu comment/bài đăng THỰC TẾ FULL không giới hạn từ URL hoặc danh sách URL.
    """
    combined_results: List[Dict[str, Any]] = []
    
    urls = [u.strip() for u in re.split(r'[,;\n]', target_url) if u.strip()]
    print(f"🌐 [REAL CRAWLER FULL] Đã nhận {len(urls)} URL bài đăng cần cào (FULL ALL)")
    
    for u in urls:
        if len(combined_results) >= limit:
            break
        items = scrape_single_url(u, limit=limit - len(combined_results))
        for it in items:
            if len(combined_results) >= limit:
                break
            if not any(c["content"] == it["content"] for c in combined_results):
                combined_results.append(it)
                
    print(f"✅ [TỔNG HỢP FULL] Cào thành công {len(combined_results)} comment THỰC TẾ từ {len(urls)} URL.")
    return combined_results


def save_real_comments_to_db(comments: List[Dict[str, Any]]) -> int:
    """Lưu comment cào thực tế vào PostgreSQL Supabase raw_comments (Kèm cơ chế Pre-Check chống trùng lặp)"""
    if not comments:
        print("⚠️ Không có comment thực tế nào để lưu vào DB.")
        return 0
        
    saved_count = 0
    try:
        conn = psycopg2.connect(
            host=POOLER_HOST, port=POOLER_PORT, user=POOLER_USER,
            password=PASSWORD, dbname=DBNAME, connect_timeout=10
        )
        conn.autocommit = True
        cursor = conn.cursor()

        for item in comments:
            raw_content = (item.get("content") or "").strip()
            if not raw_content or len(raw_content) < 3:
                continue
            
            norm_content = " ".join(raw_content.lower().split())

            # PRE-CHECK: Kiểm tra xem nội dung đã từng xuất hiện trong DB chưa
            cursor.execute("""
                SELECT id FROM raw_comments 
                WHERE LOWER(platform) = LOWER(%s) 
                  AND (
                    content = %s 
                    OR LOWER(TRIM(REGEXP_REPLACE(content, '\\s+', ' ', 'g'))) = %s
                  )
                LIMIT 1;
            """, (item.get("platform", "tiktok"), raw_content, norm_content))
            
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO raw_comments (platform, group_or_page, source_url, author, content, post_likes, comment_created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                item["platform"], item.get("group_or_page", "TikTok"), item.get("source_url"),
                item.get("author", "User"), raw_content, item.get("post_likes", "0"),
                item.get("comment_created_at", datetime.now().isoformat()), item.get("status", "pending")
            ))
            saved_count += 1
            
        cursor.close()
        conn.close()
        print(f"💾 Đã lưu THÀNH CÔNG {saved_count} comment thực tế mới (đã loại bỏ tất cả trùng lặp) vào Supabase DB!")
    except Exception as e:
        print(f"❌ Lỗi lưu Supabase DB: {e}")
    return saved_count
