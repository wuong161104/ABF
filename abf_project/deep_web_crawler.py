# -*- coding: utf-8 -*-
"""
=============================================================================
ABF UNIVERSAL 2-PHASE DEEP WEB CRAWLER & SUPABASE HUB
-----------------------------------------------------------------------------
PHASE 1: QUÉT VÉT CẠN TOÀN BỘ 100% CÁC THẺ <a> TRÊN MENU & TOÀN BỘ TRANG WEB.
         - Quét tất cả thẻ <a> trên thanh Menu, Header, Footer, Danh mục.
         - Vào từng trang menu, cuộn trang (smooth scroll) để quét vét cạn 
           toàn bộ các link <a> bài viết, thẻ tín dụng, sản phẩm.
         - Chỉ cào nội bộ website mục tiêu (loại trừ Facebook, Zalo, TikTok, YouTube...).

PHASE 2: BÓC TÁCH NỘI DUNG & THẺ HEADING (h1, h2, h3, h4, h5, h6).
         - Mở từng URL đã khám phá ở Phase 1.
         - Tự động cuộn trang & bung accordion/tabs.
         - Bóc tách đầy đủ 100% các thẻ Heading (h1-h6), văn bản, bảng biểu, ảnh.
         - Xuất ra file Markdown (.md), JSON và đồng bộ trực tiếp vào Supabase DB.
=============================================================================
"""

import os
import re
import sys
import json
import time
import csv
import io
import argparse
import hashlib
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, BrowserContext
import gc
import ctypes

try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None

load_dotenv()

def enable_anti_sleep():
    """Giữ máy tính Windows luôn thức (ngăn tự động Sleep / ngắt mạng khi cào lâu)"""
    try:
        if os.name == "nt":
            # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass

def disable_anti_sleep():
    """Khôi phục lại chế độ quản lý nguồn mặc định của Windows"""
    try:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception:
        pass


# Danh sách phần mở rộng tệp tài liệu được hỗ trợ cào và bóc tách
DOC_EXTENSIONS = ('.pdf', '.docx', '.doc', '.docm', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.csv')

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
POOLER_HOST = os.getenv("POOLER_HOST", "aws-0-ap-northeast-2.pooler.supabase.com")
POOLER_USER = os.getenv("POOLER_USER", "postgres.azpvcqpnecljsosamnot")
POOLER_PORT = int(os.getenv("POOLER_PORT", "6543"))
PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "thanhvuong16@")
DBNAME = os.getenv("DBNAME", "postgres")

# External Social Media & Noise Domains to Exclude
EXCLUDED_EXTERNAL_DOMAINS = [
    "facebook.com", "fb.com", "m.facebook.com", "tiktok.com", "zalo.me", "chat.zalo.me",
    "youtube.com", "youtu.be", "instagram.com", "twitter.com", "x.com", "threads.net",
    "linkedin.com", "pinterest.com", "telegram.org", "t.me", "google.com", "apple.com"
]

# Excluded URL fragments (Auth / Noise / Redirects only)
EXCLUDED_URL_PATTERNS = [
    "/login", "/dang-nhap", "/register", "/cart", "/checkout", "/my-account", "/wp-admin",
    "oauth", "redirect_to", "wp-login", "google_oauth", "logout",
    "#", "javascript:", "mailto:", "tel:"
]

# Excluded Click Actions / Form Buttons
EXCLUDE_CLICK_KEYWORDS = [
    "đăng ký", "dang ky", "mở thẻ ngay", "mo the ngay", "đăng ký ngay", "dang ky ngay",
    "apply now", "register", "đăng nhập", "dang nhap", "login", "tra cứu đơn",
    "tải myvib", "góp ý", "tìm kiếm", "tim kiem", "search", "submit", "áp dụng", "ap dung",
    "bộ lọc", "filter", "xoá", "xoa", "huỷ", "huy", "đóng", "dong", "close"
]


class DeepWebCrawler:
    def __init__(
        self, 
        base_url: str = "https://rcgv.vn/", 
        output_dir: str = "crawled_data",
        headless: bool = False,
        max_subpages: int = 50,
        save_to_supabase: bool = True
    ):
        self.base_url = base_url.strip()
        self.output_dir = output_dir
        self.headless = headless
        self.max_subpages = max_subpages  # 0 or negative means unlimited/crawl all
        self.save_to_supabase = save_to_supabase
        
        parsed = urlparse(self.base_url)
        self.base_domain = parsed.netloc.lower().replace("www.", "")
        
        # Trích xuất root domain (ví dụ: vib.com.vn, vpbank.com.vn, techcombank.com.vn, shopee.vn) để hỗ trợ đa subdomain
        domain_parts = self.base_domain.split('.')
        if len(domain_parts) >= 3 and domain_parts[-1] == 'vn' and domain_parts[-2] in ['com', 'edu', 'gov', 'org', 'net']:
            self.root_domain = '.'.join(domain_parts[-3:])
        elif len(domain_parts) >= 2:
            self.root_domain = '.'.join(domain_parts[-2:])
        else:
            self.root_domain = self.base_domain

        # Thư mục lưu trữ chuyên biệt theo domain (pages, pdfs, pdf_texts, word_docs, word_texts)
        domain_folder = re.sub(r'[^a-zA-Z0-9._-]', '_', self.base_domain or "universal_site")
        self.domain_dir = os.path.join(self.output_dir, domain_folder)
        self.pages_dir = os.path.join(self.domain_dir, "pages")
        self.pdfs_dir = os.path.join(self.domain_dir, "pdfs")
        self.pdf_texts_dir = os.path.join(self.domain_dir, "pdf_texts")
        self.word_docs_dir = os.path.join(self.domain_dir, "word_docs")
        self.word_texts_dir = os.path.join(self.domain_dir, "word_texts")
        self.summary_csv_path = os.path.join(self.domain_dir, "summary.csv")

        for d in [self.output_dir, self.domain_dir, self.pages_dir, self.pdfs_dir, self.pdf_texts_dir, self.word_docs_dir, self.word_texts_dir]:
            os.makedirs(d, exist_ok=True)

        self.registry_path = os.path.join(self.domain_dir, "content_registry.json")
        self.content_registry = self._load_content_registry()
        self._init_summary_csv()

    def _load_content_registry(self) -> Dict[str, Any]:
        """Tải cơ sở dữ liệu hash nội dung từ content_registry.json để kiểm tra trùng lặp"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        
        # Tự động lập chỉ mục ban đầu từ các file đã crawl trước đó (nếu có)
        registry = {}
        try:
            if os.path.exists(self.pages_dir):
                for fname in os.listdir(self.pages_dir):
                    if fname.endswith(".md"):
                        fpath = os.path.join(self.pages_dir, fname)
                        with open(fpath, "r", encoding="utf-8") as f:
                            c = f.read()
                        m = re.search(r'\*\*URL:\*\*\s*(https?://[^\s\n]+)', c)
                        url_key = m.group(1) if m else fname
                        h = hashlib.sha256(re.sub(r'\s+', ' ', c.strip()).encode("utf-8")).hexdigest()
                        registry[url_key] = {"hash": h, "path": fpath, "type": "page"}
            if os.path.exists(self.pdfs_dir):
                for fname in os.listdir(self.pdfs_dir):
                    fpath = os.path.join(self.pdfs_dir, fname)
                    try:
                        with open(fpath, "rb") as f:
                            data = f.read()
                        h = hashlib.sha256(data).hexdigest()
                        registry[fname] = {"hash": h, "path": fpath, "type": "pdf"}
                    except Exception:
                        pass
            if os.path.exists(self.word_docs_dir):
                for fname in os.listdir(self.word_docs_dir):
                    fpath = os.path.join(self.word_docs_dir, fname)
                    try:
                        with open(fpath, "rb") as f:
                            data = f.read()
                        h = hashlib.sha256(data).hexdigest()
                        registry[fname] = {"hash": h, "path": fpath, "type": "word"}
                    except Exception:
                        pass
        except Exception:
            pass
        return registry

    def _save_content_registry(self):
        """Lưu lại bảng hash content_registry.json"""
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.content_registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"Lỗi khi lưu content_registry.json: {e}", "WARNING")

    def _init_summary_csv(self):
        """Khởi tạo file summary.csv với tiêu đề cột nếu chưa tồn tại"""
        if not os.path.exists(self.summary_csv_path):
            try:
                with open(self.summary_csv_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "STT", "Loại tài nguyên", "Tiêu đề", "URL nguồn", 
                        "Dung lượng (Bytes)", "Số ký tự", "Số đề mục / Trang", 
                        "Đường dẫn file gốc", "Đường dẫn file Text/MD", "Trạng thái"
                    ])
                    f.flush()
            except Exception as e:
                self.log(f"Lỗi khởi tạo summary.csv: {e}", "WARNING")

    def append_summary_csv_realtime(self, r: Dict[str, Any], idx: int):
        """Ghi nối và flush tức thì 1 bản ghi vào summary.csv để không bao giờ mất dữ liệu"""
        try:
            self._init_summary_csv()
            with open(self.summary_csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    idx,
                    r.get("type", "Web HTML"),
                    r.get("title", ""),
                    r.get("url", ""),
                    r.get("file_size", 0),
                    r.get("char_count", 0),
                    r.get("num_items", 0),
                    r.get("file_path", ""),
                    r.get("text_path", ""),
                    r.get("status", "SUCCESS")
                ])
                f.flush()
        except Exception as e:
            self.log(f"Lỗi ghi realtime summary.csv: {e}", "WARNING")

    def save_item_realtime(
        self,
        summary_record: Dict[str, Any],
        summary_records: List[Dict[str, Any]],
        db_record: Optional[Dict[str, Any]] = None,
        db_records_to_save: Optional[List[Dict[str, Any]]] = None,
        results: Optional[Dict[str, Any]] = None
    ):
        """
        LƯU TRỮ REALTIME ĐA TẦNG (STREAMING PERSISTENCE):
        1. Ghi nối ngay lập tức vào summary.csv trên máy tính (flush đĩa cứng).
        2. Nếu có bản ghi DB, đẩy ngay lên Supabase DB (Table: crawled_web_data).
        3. Cập nhật và lưu lại content_registry.json để checkpoint chống mất dữ liệu khi sập máy.
        """
        summary_records.append(summary_record)
        current_idx = len(summary_records)
        self.append_summary_csv_realtime(summary_record, current_idx)

        if db_record is not None:
            if db_records_to_save is not None:
                db_records_to_save.append(db_record)
            if self.save_to_supabase:
                saved = self.save_records_to_supabase([db_record])
                if results is not None:
                    results["supabase_records_saved"] += saved

        self._save_content_registry()


    def check_crawl_history(self) -> Dict[str, Any]:
        """
        [1] KIỂM TRA TRƯỚC KHI CÀO:
        Kiểm tra xem trang web / domain này đã từng được cào lần nào chưa.
        Nếu rồi, hiển thị thời điểm gần nhất và thống kê số lượng dữ liệu hiện có.
        """
        history_info = {
            "crawled_before": False,
            "last_crawled_at": None,
            "time_ago_str": "",
            "total_pages": 0,
            "total_docs": 0,
            "source": "None"
        }

        # 1. Kiểm tra báo cáo cục bộ (Local crawl_report.json)
        local_report_path = os.path.join(self.domain_dir, "crawl_report.json")
        if os.path.exists(local_report_path):
            try:
                with open(local_report_path, "r", encoding="utf-8") as f:
                    old_rep = json.load(f)
                    raw_time = old_rep.get("crawled_at")
                    if raw_time:
                        history_info["crawled_before"] = True
                        history_info["last_crawled_at"] = raw_time
                        history_info["total_pages"] = old_rep.get("total_subpages_crawled", 0) + (1 if old_rep.get("main_page") else 0)
                        history_info["total_docs"] = len(os.listdir(self.pdfs_dir)) + len(os.listdir(self.word_docs_dir)) if os.path.exists(self.pdfs_dir) else 0
                        history_info["source"] = "Bộ nhớ máy cục bộ (Local Report)"
            except Exception:
                pass

        # 2. Kiểm tra trên Supabase DB (nếu bật lưu DB và chưa có kết quả local)
        if self.save_to_supabase and not history_info["crawled_before"]:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=POOLER_HOST, port=POOLER_PORT, user=POOLER_USER,
                    password=PASSWORD, dbname=DBNAME, connect_timeout=6
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT count(*), max(crawled_at) FROM public.crawled_web_data WHERE source_url LIKE %s",
                    (f"%{self.base_domain}%",)
                )
                cnt, max_date = cur.fetchone()
                cur.close()
                conn.close()
                if cnt and cnt > 0 and max_date:
                    history_info["crawled_before"] = True
                    history_info["last_crawled_at"] = max_date.isoformat()
                    history_info["total_pages"] = cnt
                    history_info["source"] = "Cơ sở dữ liệu Supabase"
            except Exception:
                pass

        # Định dạng thời gian tương đối
        if history_info["last_crawled_at"]:
            try:
                clean_time_str = history_info["last_crawled_at"].replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(clean_time_str)
                if parsed_dt.tzinfo:
                    parsed_dt = parsed_dt.astimezone().replace(tzinfo=None)
                diff = datetime.now() - parsed_dt
                secs = int(diff.total_seconds())
                if secs < 60:
                    history_info["time_ago_str"] = f"{secs} giây trước"
                elif secs < 3600:
                    history_info["time_ago_str"] = f"{secs // 60} phút trước"
                elif secs < 86400:
                    history_info["time_ago_str"] = f"{secs // 3600} giờ trước"
                else:
                    history_info["time_ago_str"] = f"{secs // 86400} ngày trước"
                
                formatted_date = parsed_dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                formatted_date = str(history_info["last_crawled_at"])
                history_info["time_ago_str"] = "Trước đây"
        else:
            formatted_date = "Chưa có"

        # Hiển thị bảng thông báo trạng thái tiền cào dữ liệu
        print("\n" + "="*78, flush=True)
        if history_info["crawled_before"]:
            print(f"🕒 [KIỂM TRA LỊCH SỬ CÀO] PHÁT HIỆN DỮ LIỆU ĐÃ TỪNG CÀO TRƯỚC ĐÂY!", flush=True)
            print("="*78, flush=True)
            print(f" - URL / Domain mục tiêu:  {self.base_url}", flush=True)
            print(f" - Lần cào gần nhất:       {formatted_date} ({history_info['time_ago_str']})", flush=True)
            print(f" - Dữ liệu đã lưu:         {history_info['total_pages']} trang bài viết | {history_info['total_docs']} tài liệu đính kèm", flush=True)
            print(f" - Nguồn xác thực:         {history_info['source']}", flush=True)
            print(f" - Cơ chế kiểm tra trùng:  BẬT (So sánh SHA-256: Chỉ lưu nội dung MỚI / CẬP NHẬT; Bỏ qua nội dung trùng)", flush=True)
        else:
            print(f"✨ [KIỂM TRA LỊCH SỬ CÀO] ĐÂY LÀ LẦN CÀO ĐẦU TIÊN CỦA WEBSITE NÀY!", flush=True)
            print("="*78, flush=True)
            print(f" - URL / Domain mục tiêu:  {self.base_url}", flush=True)
            print(f" - Trạng thái:             Chưa có dữ liệu lịch sử trước đây", flush=True)
            print(f" - Hành động:              Hệ thống sẽ cào & lưu toàn bộ dữ liệu lần đầu", flush=True)
        print("="*78 + "\n", flush=True)

        return history_info

    def check_duplicate(self, url: str, text_content: str = "", binary_content: bytes = None) -> Tuple[bool, str, str]:
        """
        [2] SO SÁNH NỘI DUNG VỪA CÀO ĐỂ CHỐNG TRÙNG LẶP:
        - Tính mã SHA-256 hash của nội dung mới.
        - So sánh với hash của bản ghi trước đó.
        - Trả về: (is_duplicate: bool, change_type: 'UNCHANGED' | 'UPDATED' | 'NEW', content_hash: str)
        """
        if binary_content:
            content_hash = hashlib.sha256(binary_content).hexdigest()
        else:
            cleaned = re.sub(r'\s+', ' ', text_content.strip())
            content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

        url_key = url.strip()
        filename_key = os.path.basename(urlparse(url).path)

        existing_entry = self.content_registry.get(url_key) or self.content_registry.get(filename_key)

        if existing_entry:
            old_hash = existing_entry.get("hash")
            if old_hash == content_hash:
                return True, "UNCHANGED", content_hash
            else:
                return False, "UPDATED", content_hash
        else:
            return False, "NEW", content_hash

    def log(self, msg: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️ [INFO]",
            "SUCCESS": "✅ [SUCCESS]",
            "WARNING": "⚠️ [WARN]",
            "ERROR": "❌ [ERROR]",
            "PROGRESS": "🚀 [CRAWL]",
            "DISCOVERY": "🔍 [QUÉT LINK]",
            "DB": "💾 [SUPABASE]"
        }.get(level, "[LOG]")
        print(f"{prefix} {msg}", flush=True)

    def _normalize_url(self, raw_url: str, current_page_url: str) -> str:
        if not raw_url:
            return ""
        # Strip anchors
        clean_url, _ = urldefrag(raw_url.strip())
        if not clean_url or clean_url.startswith("javascript:") or clean_url.startswith("mailto:") or clean_url.startswith("tel:"):
            return ""
        full_url = urljoin(current_page_url, clean_url)
        # Ensure trailing slash normalization
        parsed = urlparse(full_url)
        non_slash_exts = ('.html', '.htm', '.php', '.png', '.jpg', '.jpeg', '.webp') + DOC_EXTENSIONS
        if not any(parsed.path.lower().endswith(ext) for ext in non_slash_exts) and not parsed.path.endswith('/'):
            full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}/{('?' + parsed.query) if parsed.query else ''}"
        return full_url

    def _is_doc_url(self, url: str) -> bool:
        if not url:
            return False
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in DOC_EXTENSIONS)

    def _classify_url_type(self, url: str) -> str:
        if not url:
            return "page"
        path = urlparse(url).path.lower()
        if path.endswith(".pdf"):
            return "pdf"
        if any(path.endswith(ext) for ext in [".docx", ".doc", ".docm"]):
            return "word"
        if any(path.endswith(ext) for ext in [".xlsx", ".xls"]):
            return "excel"
        u = url.lower()
        if any(x in u for x in ["/article/", "/post/", "/tin-tuc/", "/the-tin-dung/", "/chi-tiet/", "/bieu-mau/", "/khach-hang-ca-nhan/", "/san-pham/"]):
            return "article"
        return "page"

    def _is_valid_internal_url(self, url: str) -> bool:
        """Kiểm tra URL có thuộc domain của website mục tiêu và không phải mạng xã hội/auth không"""
        if not url:
            return False
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().replace("www.", "")
        path_lower = parsed.path.lower()
        
        # 1. Nếu là file tài liệu (PDF, Word, Excel...) thì luôn chấp nhận nếu cùng root domain hoặc link tương đối
        if any(path_lower.endswith(ext) for ext in DOC_EXTENSIONS):
            if not netloc or self.root_domain in netloc or netloc in self.root_domain:
                return True
                
        # 2. Phải cùng root domain (hoặc subdomain con ví dụ: media.vpbank.com.vn, api.vib.com.vn...)
        if self.root_domain not in netloc and netloc not in self.root_domain:
            return False
            
        # 3. Loại trừ các mạng xã hội ngoài
        if any(d in url.lower() for d in EXCLUDED_EXTERNAL_DOMAINS):
            return False

        # 4. Loại trừ URL auth / đăng ký / rác
        if any(pat in url.lower() for pat in EXCLUDED_URL_PATTERNS):
            return False
            
        return True

    def smooth_scroll_full_page(self, page: Page):
        """Cuộn từ từ toàn trang để kích hoạt Lazy Loading và tải đầy đủ các thẻ a / hình ảnh"""
        try:
            scroll_height = page.evaluate("() => document.body.scrollHeight")
            step = 600
            current = 0
            while current < scroll_height:
                page.evaluate(f"window.scrollTo(0, {current});")
                current += step
                time.sleep(0.2)
                new_height = page.evaluate("() => document.body.scrollHeight")
                if new_height > scroll_height:
                    scroll_height = new_height
                    
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            page.evaluate("window.scrollTo(0, 0);")
            time.sleep(0.2)
        except Exception:
            pass

    def _title_from_url(self, url: str) -> str:
        """Tạo tiêu đề dễ đọc từ đường dẫn URL khi thẻ <a> không có text"""
        path = urlparse(url).path.strip('/')
        if not path:
            return "Trang chủ"
        parts = [p for p in path.split('/') if p]
        if parts:
            last = parts[-1]
            last = re.sub(r'[-_]', ' ', last).strip().title()
            return last or "Chi tiết"
        return url

    def _fetch_sitemap_urls(self, context: Optional[BrowserContext] = None) -> List[str]:
        """
        Tự động tìm kiếm sitemap.xml / robots.txt để lấy toàn bộ danh sách URL sạch
        chuẩn SEO được công bố bởi website.
        """
        urls_found: List[str] = []
        visited_sitemaps: Set[str] = set()
        
        parsed = urlparse(self.base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        
        sitemap_candidates = [
            urljoin(origin, "/sitemap.xml"),
            urljoin(origin, "/sitemap_index.xml"),
            urljoin(origin, "/sitemap-index.xml"),
            urljoin(origin, "/sitemap/sitemap.xml"),
        ]

        # 1. Kiểm tra robots.txt để tìm sitemap links chính thức
        try:
            robots_url = urljoin(origin, "/robots.txt")
            res = requests.get(robots_url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if res.status_code == 200:
                for line in res.text.splitlines():
                    if line.strip().lower().startswith("sitemap:"):
                        sm_url = line.split(":", 1)[1].strip()
                        if sm_url and sm_url not in sitemap_candidates:
                            sitemap_candidates.insert(0, sm_url)
        except Exception:
            pass

        # 2. Duyệt qua hàng đợi sitemap (hỗ trợ cả sitemap lồng nhau sitemapindex)
        queue = list(sitemap_candidates)
        max_sitemaps_to_crawl = 20

        while queue and len(visited_sitemaps) < max_sitemaps_to_crawl:
            sm_url = queue.pop(0)
            if sm_url in visited_sitemaps:
                continue
            visited_sitemaps.add(sm_url)

            xml_text = ""
            # Thử bằng requests trước
            try:
                r = requests.get(sm_url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
                if r.status_code == 200 and r.text.strip():
                    xml_text = r.text
            except Exception:
                pass

            # Nếu requests bị chặn (403/Cloudflare), thử qua Playwright context request nếu có
            if not xml_text and context is not None:
                try:
                    pw_resp = context.request.get(sm_url, timeout=12000)
                    if pw_resp.status == 200:
                        xml_text = pw_resp.text()
                except Exception:
                    pass

            if not xml_text:
                continue

            # Bóc tách thẻ <loc>
            locs = re.findall(r"<loc>(.*?)</loc>", xml_text, flags=re.IGNORECASE)
            if not locs:
                continue

            self.log(f"  -> Đọc thành công Sitemap '{sm_url}': phát hiện {len(locs)} liên kết / mục con.", "DISCOVERY")

            for loc in locs:
                clean_loc = loc.strip()
                if not clean_loc:
                    continue
                # Nếu là sitemap con
                if clean_loc.endswith(".xml") or ("sitemap" in clean_loc.lower() and not clean_loc.endswith((".html", ".htm", ".php"))):
                    if clean_loc not in visited_sitemaps and clean_loc not in queue:
                        queue.append(clean_loc)
                else:
                    norm = self._normalize_url(clean_loc, self.base_url)
                    if self._is_valid_internal_url(norm):
                        urls_found.append(norm)

        unique_urls = list(dict.fromkeys(urls_found))
        if unique_urls:
            self.log(f"✨ Tìm thấy tổng cộng {len(unique_urls)} URL từ Sitemap chính thức của website!", "SUCCESS")
        return unique_urls

    def discover_all_site_links(self, context: BrowserContext) -> List[Dict[str, str]]:
        """
        PHASE 1: QUÉT VÉT CẠN 100% CÁC THẺ <a> TRÊN MENU, SITEMAP VÀ TOÀN BỘ WEBSITE.
        Kết hợp: Sitemap XML chính thức + Quét động qua Playwright (Menu, Landing cards, Cuộn trang).
        """
        if self.max_subpages == 1:
            return [{"url": self.base_url, "title": "Trang chính đích", "type": "main_page"}]

        self.log(f"Bắt đầu Phase 1: Quét vét cạn toàn bộ liên kết (Sitemap + DOM Menu + Landing)...", "DISCOVERY")
        
        discovered_targets = []  # List of dict: {"url": str, "title": str, "type": str}
        self.seen_urls = set()

        # Thêm trang chủ vào danh sách đầu tiên
        self.seen_urls.add(self.base_url)
        discovered_targets.append({"url": self.base_url, "title": "Trang chính tổng quan", "type": "main_page"})

        # 1. Tự động kiểm tra và nạp toàn bộ URL từ Sitemap XML (nếu website hỗ trợ)
        sitemap_urls = self._fetch_sitemap_urls(context)
        for s_url in sitemap_urls:
            if s_url not in self.seen_urls:
                self.seen_urls.add(s_url)
                item_type = self._classify_url_type(s_url)
                title = self._title_from_url(s_url)
                discovered_targets.append({"url": s_url, "title": title, "type": item_type})

        # 2. Quét thực tế trên trình duyệt Playwright để lấy menu động, text thật và accordion
        page = context.new_page()
        category_scan_candidates = []
        try:
            self.log(f"Đang mở trang gốc để quét tương tác DOM: {self.base_url}", "DISCOVERY")
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
            self.smooth_scroll_full_page(page)

            # Quét toàn bộ thẻ <a> trên trang chủ (bao gồm cả nav, header, main, cards)
            all_a_elements = page.query_selector_all("a[href]")
            dom_found_count = 0

            for el in all_a_elements:
                try:
                    href = el.get_attribute("href") or ""
                    text = (el.inner_text() or "").strip()
                    full_url = self._normalize_url(href, self.base_url)
                    if self._is_valid_internal_url(full_url):
                        if full_url not in self.seen_urls:
                            self.seen_urls.add(full_url)
                            item_type = self._classify_url_type(full_url)
                            discovered_targets.append({
                                "url": full_url,
                                "title": text or self._title_from_url(full_url),
                                "type": item_type
                            })
                            dom_found_count += 1
                        else:
                            # Cập nhật lại title thực tế từ DOM nếu trước đó chỉ có title tạm
                            if text:
                                for t in discovered_targets:
                                    if t["url"] == full_url and (t["title"].startswith("Link ") or t["title"] == self._title_from_url(full_url)):
                                        t["title"] = text
                                        break
                                        
                        # Đánh giá các link làm cổng danh mục để quét sâu tiếp
                        path_segments = [p for p in urlparse(full_url).path.strip('/').split('/') if p]
                        if 1 <= len(path_segments) <= 2 and not any(full_url.lower().endswith(ext) for ext in DOC_EXTENSIONS):
                            if full_url not in category_scan_candidates and full_url != self.base_url:
                                category_scan_candidates.append(full_url)
                except Exception:
                    pass

            self.log(f"Quét DOM trang chủ: thu thập thêm {dom_found_count} link mới!", "DISCOVERY")
            page.close()

            # 3. Duyệt qua các cổng danh mục chính để bung menu con và quét sâu tiếp
            max_category_depth = 15  # Số trang cổng danh mục quét sâu ở Phase 1
            scanned_cats = 0
            while category_scan_candidates and scanned_cats < max_category_depth:
                cat_url = category_scan_candidates.pop(0)
                scanned_cats += 1
                self.log(f"[Phase 1 - Quét sâu Danh mục {scanned_cats}/{min(len(category_scan_candidates) + scanned_cats, max_category_depth)}]: {cat_url}", "DISCOVERY")
                try:
                    cat_page = context.new_page()
                    cat_page.goto(cat_url, wait_until="domcontentloaded", timeout=35000)
                    time.sleep(1.5)
                    self.smooth_scroll_full_page(cat_page)

                    sub_a_elements = cat_page.query_selector_all("a[href]")
                    new_in_cat = 0
                    for el in sub_a_elements:
                        try:
                            href = el.get_attribute("href") or ""
                            text = (el.inner_text() or "").strip()
                            full_url = self._normalize_url(href, cat_url)
                            if self._is_valid_internal_url(full_url):
                                if full_url not in self.seen_urls:
                                    self.seen_urls.add(full_url)
                                    item_type = self._classify_url_type(full_url)
                                    discovered_targets.append({
                                        "url": full_url,
                                        "title": text or self._title_from_url(full_url),
                                        "type": item_type
                                    })
                                    new_in_cat += 1
                                elif text:
                                    for t in discovered_targets:
                                        if t["url"] == full_url and (t["title"].startswith("Link ") or t["title"] == self._title_from_url(full_url)):
                                            t["title"] = text
                                            break
                        except Exception:
                            pass
                    cat_page.close()
                    if new_in_cat > 0:
                        self.log(f"  -> Phát hiện thêm {new_in_cat} link con mới! (Tổng: {len(discovered_targets)})", "SUCCESS")
                except Exception as cat_err:
                    self.log(f"  -> Bỏ qua danh mục {cat_url}: {cat_err}", "WARNING")
                    try:
                        cat_page.close()
                    except Exception:
                        pass

        except Exception as e:
            self.log(f"Lỗi khi quét tương tác DOM Phase 1: {e}", "ERROR")

        # 4. Sắp xếp thông minh theo mức độ ưu tiên tài liệu và nghiệp vụ sản phẩm
        base_path = urlparse(self.base_url).path.lower().rstrip('/')

        def sort_priority(item):
            url = item["url"].lower()
            path = urlparse(url).path.lower()

            # URL gốc đích lên đầu tiên
            if item["url"] == self.base_url:
                return -10

            # File tài liệu (PDF, Word, Excel) được ưu tiên tối đa để không bỏ sót biểu mẫu/hợp đồng
            if path.endswith(".pdf") or any(path.endswith(ext) for ext in [".docx", ".doc", ".xlsx"]):
                return 0

            # Kiểm tra nếu là subpath của URL người dùng yêu cầu
            is_subpath = bool(base_path and base_path in path)

            # Các từ khóa sản phẩm tài chính & nghiệp vụ ngân hàng trọng điểm
            is_core_product = any(x in path for x in [
                "/the-tin-dung", "/the-ghi-no", "/dich-vu-the", "-the-", "/the/",
                "/vay", "/tiet-kiem", "/tai-khoan", "/bao-hiem", "/bieu-phi",
                "/lai-suat", "/dieu-khoan", "/san-pham", "/ca-nhan",
                "/doanh-nghiep-vua-va-nho", "/doanh-nghiep-lon", "/ho-kinh-doanh",
                "/article/", "/chi-tiet/", "/detail/", "/post/"
            ])

            if is_subpath and is_core_product:
                return 1
            if is_core_product:
                return 2
            if is_subpath:
                return 3
            if any(x in path for x in ["/uu-dai", "/ve-chung-toi", "/quan-he-nha-dau-tu"]):
                return 4
            if any(x in path for x in ["/tin-tuc/", "/bi-kip-va-chia-se/"]):
                return 5
            return 6

        discovered_targets.sort(key=sort_priority)

        self.log(f"🎉 HOÀN THÀNH PHASE 1: Đã phát hiện tổng cộng {len(discovered_targets)} liên kết duy nhất trong toàn bộ website!", "SUCCESS")
        return discovered_targets

    @staticmethod
    def repair_vietnamese_pdf_text(text: str) -> str:
        """
        Khắc phục lỗi font chữ tiếng Việt bị phân mảnh (CID font encoding artifacts)
        thường gặp trong các văn bản PDF ngân hàng (VPBank, VIB, Vietcombank...).
        """
        if not text:
            return ""
        char_map = {
            'Diさu': 'Điều ', 'diさu': 'điều ', 'DIЁU': 'ĐIỀU', 'diёu': 'điều ', 'Diёu': 'Điều ',
            'chthg': 'chứng', 'ch品g': 'chứng', 'ch価g': 'chứng', 'ch面g': 'chứng', 'chさng': 'chứng',
            'chiti': 'chi ti', 'tiさn': 'tiền', 'tiёn': 'tiền', 'tiさ': 'tiền',
            'g面': 'gửi', 'g伍': 'gửi', 'g逝': 'gửi', 'gti': 'gửi', 'GlrI': 'GỬI',
            'Khtth': 'Khách', 'Khich': 'Khách', 'Khたh': 'Khách', 'khtth': 'khách', 'khich': 'khách', 'khたh': 'khách',
            'httg': 'hàng', 'hmg': 'hàng', 'hhg': 'hàng',
            'Ngねhmg': 'Ngân hàng', 'ngねhmg': 'ngân hàng', 'Ngtt httg': 'Ngân hàng', 'Ngね hmg': 'Ngân hàng',
            'phtt': 'phát', 'pMt': 'phát', 'Th6ng': 'Thông', 'th6ng': 'thông',
            'Th61e': 'Thể lệ', 'Thele': 'Thể lệ', 'Thd': 'Thời', 'thd': 'thời', 'thd`': 'thời',
            'dlrOc': 'được', 'ducc': 'được', 'dwc': 'được',
            'H\"dさng': 'Hợp đồng', 'H\"d6ng': 'Hợp đồng', 'Hop dOng': 'Hợp đồng', 'H9pdさng': 'Hợp đồng',
            'quyさn': 'quyền', 's6 hm': 'sở hữu', 's6 httu': 'sở hữu', 's6htu': 'sở hữu', 's6 htu': 'sở hữu', 's6hm': 'sở hữu',
            'Chi s6': 'Chủ sở', 'chi s6': 'chủ sở',
            'thanh toin': 'thanh toán', 'thanhtom': 'thanh toán', 'thanh toan': 'thanh toán', 'thanhtoan': 'thanh toán',
            'la sttt': 'lãi suất', 'Lai sua': 'Lãi suất', 'lai sua': 'lãi suất', 'Lai su乱': 'Lãi suất',
            'vietNam': 'Việt Nam', 'Viet Nam': 'Việt Nam', 'Thinh Vttg': 'Thịnh Vượng',
            'vpsonk': 'VPBank', 'vpeonk': 'VPBank', 'VPBonk': 'VPBank', 'VPBcnk': 'VPBank', 'VPBtt': 'VPBank'
        }
        res = text
        for k, v in char_map.items():
            res = res.replace(k, v)
        # Loại bỏ ký tự rác tượng hình CJK do lỗi map glyph trong PDF tiếng Việt
        res = re.sub(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef■食響]+', ' ', res)
        res = re.sub(r'[ ]{2,}', ' ', res)
        return res

    def extract_pdf_content(self, pdf_url: str) -> Dict[str, Any]:
        """
        Tải file PDF từ URL, lưu file gốc vào pdfs/, bóc tách toàn bộ nội dung từng trang,
        các đề mục (Điều, Khoản, Tiêu đề), bảng số liệu và lưu Markdown vào pdf_texts/.
        """
        try:
            import pypdf
            import io
            from urllib.parse import unquote
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            }
            resp = requests.get(pdf_url, headers=headers, timeout=45)
            if resp.status_code != 200:
                return {
                    "markdown": "", "full_text": "", "headings": [], "paragraphs": [],
                    "total_pages": 0, "status": "FAILED", "error": f"HTTP {resp.status_code}",
                    "file_size": 0, "file_path": "", "text_path": ""
                }
                
            raw_filename = unquote(os.path.basename(urlparse(pdf_url).path)) or "Tai-lieu-PDF.pdf"
            raw_filename = raw_filename.replace("+", " ")
            safe_name = re.sub(r'[\\/*?:"<>|]', '_', raw_filename).strip()
            if not safe_name.lower().endswith(".pdf"):
                safe_name += ".pdf"

            pdf_file_path = os.path.join(self.pdfs_dir, safe_name)
            txt_filename = safe_name.replace(".pdf", "") + ".md"
            text_path = os.path.join(self.pdf_texts_dir, txt_filename)
            file_size = len(resp.content)
            file_title = safe_name.replace(".pdf", "").replace("-", " ").replace("_", " ").title()

            # [SO SÁNH TRÙNG LẶP] Kiểm tra mã hash nội dung file PDF vừa cào
            is_dup, change_type, f_hash = self.check_duplicate(pdf_url, binary_content=resp.content)
            if is_dup and os.path.exists(pdf_file_path) and os.path.exists(text_path):
                self.log(f"  ⏭️ [TRÙNG LẶP] Tệp PDF '{safe_name}' không đổi so với lần cào trước -> BỎ QUA KHÔNG LƯU!", "INFO")
                try:
                    with open(text_path, "r", encoding="utf-8") as f:
                        cached_md = f.read()
                except Exception:
                    cached_md = ""
                return {
                    "markdown": cached_md,
                    "full_text": cached_md,
                    "headings": [],
                    "paragraphs": [],
                    "table_cells": [],
                    "italics": [],
                    "tables": [],
                    "total_pages": 0,
                    "file_title": file_title,
                    "file_size": file_size,
                    "file_path": pdf_file_path,
                    "text_path": text_path,
                    "status": "UNCHANGED",
                    "change_type": "TRÙNG LẶP"
                }

            # NẾU LÀ TÀI LIỆU MỚI HOẶC CÓ CẬP NHẬT -> TIẾN HÀNH LƯU VÀ BÓC TÁCH:
            self.log(f"  💾 [{'MỚI' if change_type == 'NEW' else 'CẬP NHẬT'}] Lưu file & bóc tách PDF '{safe_name}' ({round(file_size/1024, 1)} KB)...", "PROGRESS")
            with open(pdf_file_path, "wb") as f:
                f.write(resp.content)

            pdf_file = io.BytesIO(resp.content)
            reader = pypdf.PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            page_texts = []
            all_headings = []
            all_paragraphs = []
            
            md_content = f"# 📄 {file_title}\n\n"
            md_content += f"- **Nguồn tài liệu PDF:** [{raw_filename}]({pdf_url})\n"
            md_content += f"- **Tổng số trang:** {total_pages} trang\n"
            md_content += f"- **Dung lượng file:** {round(file_size / 1024, 1)} KB\n\n---\n\n"
            
            for page_idx, page in enumerate(reader.pages, 1):
                raw_text = ""
                try:
                    raw_text = page.extract_text(extraction_mode="layout") or ""
                except Exception:
                    raw_text = page.extract_text() or ""
                
                # Sửa lỗi font chữ tiếng Việt bị nhòe / ký tự rác
                repaired_text = self.repair_vietnamese_pdf_text(raw_text)
                cleaned_page_text = "\n".join([line.strip() for line in repaired_text.split("\n") if line.strip()])
                
                if cleaned_page_text:
                    md_content += f"## 📄 Trang {page_idx}/{total_pages}\n\n"
                    md_content += f"{cleaned_page_text}\n\n---\n\n"
                    page_texts.append(cleaned_page_text)
                    
                    for line in cleaned_page_text.split("\n"):
                        line_str = line.strip()
                        if re.match(r'^(Điều\s+\d+|Khoản\s+\d+|Mục\s+\d+|Phần\s+[IVXLCDM\d]+|[0-9]+\.[0-9]+)', line_str, re.IGNORECASE):
                            all_headings.append({
                                "tag": "h3",
                                "level": 3,
                                "text": line_str[:120]
                            })
                        elif len(line_str) > 20:
                            all_paragraphs.append(line_str)
                            
            # Lưu file text Markdown vào pdf_texts/
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Cập nhật registry
            self.content_registry[pdf_url] = {
                "hash": f_hash,
                "file_path": pdf_file_path,
                "text_path": text_path,
                "type": "pdf",
                "title": file_title,
                "updated_at": datetime.now().isoformat()
            }
            self.content_registry[safe_name] = self.content_registry[pdf_url]

            return {
                "markdown": md_content.strip(),
                "full_text": "\n\n".join(page_texts),
                "headings": all_headings,
                "paragraphs": all_paragraphs,
                "table_cells": [],
                "italics": [],
                "tables": [],
                "total_pages": total_pages,
                "file_title": file_title,
                "file_size": file_size,
                "file_path": pdf_file_path,
                "text_path": text_path,
                "status": "SUCCESS",
                "change_type": change_type
            }
        except Exception as e:
            self.log(f"Lỗi khi trích xuất PDF {pdf_url}: {e}", "ERROR")
            return {
                "markdown": "", "full_text": "", "headings": [], "paragraphs": [],
                "total_pages": 0, "status": "ERROR", "error": str(e),
                "file_size": 0, "file_path": "", "text_path": ""
            }

    def extract_word_content(self, doc_url: str) -> Dict[str, Any]:
        """
        Tải file Word (.docx, .doc) từ URL, lưu file gốc vào word_docs/,
        bóc tách toàn bộ tiêu đề, đoạn văn bản, bảng biểu và lưu Markdown vào word_texts/.
        """
        try:
            import io
            import docx
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            }
            resp = requests.get(doc_url, headers=headers, timeout=35)
            if resp.status_code != 200:
                return {
                    "status": "FAILED", "error": f"HTTP {resp.status_code}",
                    "markdown": "", "full_text": "", "headings": [], "paragraphs": [],
                    "tables": [], "file_size": 0, "file_path": "", "text_path": ""
                }
                
            from urllib.parse import unquote
            raw_name = unquote(os.path.basename(urlparse(doc_url).path)) or "document.docx"
            raw_name = raw_name.replace("+", " ")
            safe_name = re.sub(r'[\\/*?:"<>|]', '_', raw_name).strip()
            if not any(safe_name.lower().endswith(ext) for ext in [".docx", ".doc", ".docm"]):
                safe_name += ".docx"

            file_path = os.path.join(self.word_docs_dir, safe_name)
            txt_filename = safe_name.rsplit(".", 1)[0] + ".md"
            text_path = os.path.join(self.word_texts_dir, txt_filename)
            file_size = len(resp.content)
            file_title = safe_name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()

            # [SO SÁNH TRÙNG LẶP] Kiểm tra mã hash nội dung file Word vừa cào
            is_dup, change_type, f_hash = self.check_duplicate(doc_url, binary_content=resp.content)
            if is_dup and os.path.exists(file_path) and os.path.exists(text_path):
                self.log(f"  ⏭️ [TRÙNG LẶP] Tệp Word '{safe_name}' không đổi so với lần cào trước -> BỎ QUA KHÔNG LƯU!", "INFO")
                try:
                    with open(text_path, "r", encoding="utf-8") as f:
                        cached_md = f.read()
                except Exception:
                    cached_md = ""
                return {
                    "status": "UNCHANGED",
                    "change_type": "TRÙNG LẶP",
                    "file_title": file_title,
                    "markdown": cached_md,
                    "full_text": cached_md,
                    "headings": [],
                    "paragraphs": [],
                    "tables": [],
                    "file_size": file_size,
                    "file_path": file_path,
                    "text_path": text_path
                }

            self.log(f"  💾 [{'MỚI' if change_type == 'NEW' else 'CẬP NHẬT'}] Lưu file & bóc tách Word '{safe_name}' ({round(file_size/1024, 1)} KB)...", "PROGRESS")
            with open(file_path, "wb") as f:
                f.write(resp.content)

            md_content = f"# 📄 {file_title}\n\n"
            md_content += f"- **Nguồn tài liệu Word:** [{raw_name}]({doc_url})\n"
            md_content += f"- **Dung lượng file:** {round(file_size / 1024, 1)} KB\n\n---\n\n"

            all_headings = []
            all_paragraphs = []
            all_tables = []
            page_texts = []

            if safe_name.lower().endswith(".docx"):
                doc_stream = io.BytesIO(resp.content)
                doc = docx.Document(doc_stream)
                
                for p in doc.paragraphs:
                    txt = p.text.strip()
                    if not txt:
                        continue
                    style_name = p.style.name.lower() if p.style else ""
                    if "heading 1" in style_name or "title" in style_name:
                        md_content += f"## {txt}\n\n"
                        all_headings.append({"tag": "h1", "level": 1, "text": txt[:120]})
                    elif "heading 2" in style_name:
                        md_content += f"### {txt}\n\n"
                        all_headings.append({"tag": "h2", "level": 2, "text": txt[:120]})
                    elif "heading 3" in style_name:
                        md_content += f"#### {txt}\n\n"
                        all_headings.append({"tag": "h3", "level": 3, "text": txt[:120]})
                    elif re.match(r'^(Điều\s+\d+|Khoản\s+\d+|Mục\s+\d+|Phần\s+[IVXLCDM\d]+|[0-9]+\.[0-9]+)', txt, re.IGNORECASE):
                        md_content += f"### {txt}\n\n"
                        all_headings.append({"tag": "h2", "level": 2, "text": txt[:120]})
                    else:
                        md_content += f"{txt}\n\n"
                        all_paragraphs.append(txt)
                    page_texts.append(txt)

                for tbl_idx, tbl in enumerate(doc.tables, 1):
                    tbl_rows = []
                    md_content += f"#### Bảng {tbl_idx}:\n\n"
                    for row in tbl.rows:
                        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells if cell.text.strip()]
                        if cells:
                            tbl_rows.append(cells)
                            md_content += "| " + " | ".join(cells) + " |\n"
                    md_content += "\n"
                    if tbl_rows:
                        all_tables.append(tbl_rows)
            else:
                # File .doc nhị phân
                raw_strings = re.findall(rb'[\x20-\x7E\x80-\xFF]{4,}', resp.content)
                extracted_doc_text = ""
                for s in raw_strings:
                    try:
                        decoded = s.decode("utf-8", errors="ignore").strip()
                        if len(decoded) > 10:
                            extracted_doc_text += decoded + "\n\n"
                    except:
                        pass
                md_content += extracted_doc_text
                all_paragraphs.append(extracted_doc_text[:500])

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Cập nhật registry
            self.content_registry[doc_url] = {
                "hash": f_hash,
                "file_path": file_path,
                "text_path": text_path,
                "type": "word",
                "title": file_title,
                "updated_at": datetime.now().isoformat()
            }
            self.content_registry[safe_name] = self.content_registry[doc_url]

            return {
                "status": "SUCCESS",
                "change_type": change_type,
                "file_title": file_title,
                "markdown": md_content.strip(),
                "full_text": "\n\n".join(page_texts) if page_texts else md_content.strip(),
                "headings": all_headings,
                "paragraphs": all_paragraphs,
                "tables": all_tables,
                "file_path": file_path,
                "text_path": text_path,
                "file_size": file_size
            }
        except Exception as e:
            self.log(f"Lỗi khi trích xuất Word {doc_url}: {e}", "ERROR")
            return {
                "status": "ERROR", "error": str(e),
                "markdown": "", "full_text": "",
                "headings": [], "paragraphs": [], "tables": [],
                "file_size": 0, "file_path": "", "text_path": ""
            }

    def extract_images_from_page(self, page: Page, current_url: str) -> List[Dict[str, str]]:
        images = []
        seen = set()
        img_elements = page.query_selector_all("img, [data-src], [data-lazy]")
        for img in img_elements:
            src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-lazy") or ""
            alt = (img.get_attribute("alt") or "").strip()
            title = (img.get_attribute("title") or "").strip()
            
            full_url = self._normalize_url(src, current_url)
            if full_url and full_url not in seen and not full_url.endswith('.svg'):
                seen.add(full_url)
                images.append({
                    "url": full_url,
                    "alt": alt,
                    "title": title
                })
        return images

    def extract_clean_text_and_tables(self, html_content: str) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ dữ liệu bài viết sang cấu trúc Markdown chuẩn,
        bảo toàn 100% các thẻ Heading (h1, h2, h3, h4, h5, h6),
        Bảng biểu, Danh sách (ul, ol, li), Trích dẫn (blockquote), Định dạng (b, strong, em).
        """
        if not html_content:
            return {
                "markdown": "",
                "full_text": "",
                "headings": [],
                "sections": [],
                "tables": []
            }

        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Loại bỏ các comment HTML (ví dụ comment IBM WebSphere Z7_... của VIB)
        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. Loại bỏ các thẻ rác, modal lọc, script, header/footer boilerplate
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "button", "input", "form", "select", "nav", "footer", "meta", "link", "template"]):
            tag.decompose()

        for sel in [".modal", ".search-modal", ".popup", "#search-modal", ".menu-mobile", ".site-header", ".site-footer", "header", "footer", "nav", ".widget-area", ".sidebar", ".filter-box", ".search-box", ".fl-builder-pagination", ".toast-message-container", "[id*='Deferred']", ".hidden_pc"]:
            for el in soup.select(sel):
                el.decompose()

        # 2. Tự động nhận diện vùng chứa nội dung cốt lõi của bài viết (nếu có)
        main_container = None
        for selector in ["article.entry-content", ".entry-content", "article", ".post-content", ".article-content", ".main-content", "main", "#content", ".content-area"]:
            found = soup.select_one(selector)
            if found and len(found.get_text(strip=True)) > 150:
                main_container = found
                break
        
        target_root = main_container if main_container else soup

        # 3. Trích xuất danh sách tất cả headings h1-h6 từ vùng nội dung chính
        headings = []
        for h_tag in target_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            h_text = h_tag.get_text(separator=" ", strip=True)
            if h_text:
                headings.append({
                    "tag": h_tag.name.lower(),
                    "level": int(h_tag.name[1]),
                    "text": h_text
                })

        # 4. Trích xuất danh sách tất cả đoạn văn <p>
        paragraphs = []
        for p_tag in target_root.find_all("p"):
            p_text = p_tag.get_text(separator=" ", strip=True)
            if p_text and len(p_text) > 1:
                paragraphs.append(p_text)

        # 5. Trích xuất danh sách tất cả chữ nghiêng / ghi chú <i> / <em> / <cite>
        italics = []
        for i_tag in target_root.find_all(["i", "em", "cite", "dfn"]):
            i_text = i_tag.get_text(separator=" ", strip=True)
            if i_text and len(i_text) > 1:
                italics.append(i_text)

        # 6. Trích xuất danh sách tất cả ô bảng <td> / <th>
        table_cells = []
        for td_tag in target_root.find_all(["td", "th"]):
            td_text = td_tag.get_text(separator=" ", strip=True)
            if td_text:
                table_cells.append(td_text)

        # 7. Trích xuất các bảng dữ liệu <table> hoàn chỉnh
        tables_data = []
        for table in target_root.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(separator=" ", strip=True).replace("\n", " ") for td in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if rows:
                tables_data.append(rows)

        # 8. Trích xuất sections tổng hợp (heading, p, li, td)
        sections = []
        for tag in target_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
            txt = tag.get_text(separator=" ", strip=True)
            if txt and len(txt) > 2:
                sections.append({
                    "tag": tag.name.lower(),
                    "text": txt
                })

        # 9. Chuyển đổi DOM sang Markdown có cấu trúc đầy đủ
        def process_node(node) -> str:
            if isinstance(node, NavigableString):
                return str(node)
            if not isinstance(node, Tag):
                return ""

            tag_name = node.name.lower()

            # Headings: bảo toàn cấp độ #, ##, ###, ####, #####, ######
            if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                level = int(tag_name[1])
                text = "".join(process_node(child) for child in node.children).strip()
                if text:
                    return f"\n\n{'#' * level} {text}\n\n"
                return ""

            # Table sang Markdown table (giữ nguyên in nghiêng i, in đậm b, link a bên trong từng ô td)
            if tag_name == "table":
                rows = []
                for tr in node.find_all("tr"):
                    cells = []
                    for cell in tr.find_all(["th", "td"]):
                        cell_md = "".join(process_node(c) for c in cell.children).strip()
                        cell_md = cell_md.replace("\n", " ").strip()
                        cells.append(cell_md)
                    if any(cells):
                        rows.append(cells)
                if not rows:
                    return ""
                md_table = "\n\n"
                header = rows[0]
                md_table += "| " + " | ".join(header) + " |\n"
                md_table += "| " + " | ".join(["---"] * len(header)) + " |\n"
                for r in rows[1:]:
                    while len(r) < len(header):
                        r.append("")
                    md_table += "| " + " | ".join(r[:len(header)]) + " |\n"
                return md_table + "\n\n"

            # Standalone td / th
            if tag_name in ["td", "th"]:
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" {inner} " if inner else ""

            # Paragraph <p>
            if tag_name == "p":
                inner = "".join(process_node(child) for child in node.children).strip()
                return f"\n\n{inner}\n\n" if inner else ""

            # Chữ in nghiêng <i> / <em> / <cite> / <dfn>
            if tag_name in ["em", "i", "cite", "dfn"]:
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" *{inner}* " if inner else ""

            # Chữ in đậm <strong> / <b>
            if tag_name in ["strong", "b"]:
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" **{inner}** " if inner else ""

            # List items <li>
            if tag_name == "li":
                inner = "".join(process_node(child) for child in node.children).strip()
                return f"\n- {inner}" if inner else ""

            if tag_name in ["ul", "ol"]:
                inner = "".join(process_node(child) for child in node.children).strip()
                return f"\n\n{inner}\n\n" if inner else ""

            # Blockquote <blockquote>
            if tag_name == "blockquote":
                inner = "".join(process_node(child) for child in node.children).strip()
                quoted = "\n".join(f"> {line.strip()}" for line in inner.split("\n") if line.strip())
                return f"\n\n{quoted}\n\n" if quoted else ""

            # Code <code> / <pre>
            if tag_name == "code":
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" `{inner}` " if inner else ""

            if tag_name == "pre":
                inner = "".join(process_node(child) for child in node.children)
                return f"\n\n```\n{inner}\n```\n\n" if inner else ""

            # Gạch ngang <del> / <s> / <strike>
            if tag_name in ["del", "s", "strike"]:
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" ~~{inner}~~ " if inner else ""

            # Highlight <mark>
            if tag_name == "mark":
                inner = "".join(process_node(child) for child in node.children).strip()
                return f" =={inner}== " if inner else ""

            # Link <a>
            if tag_name == "a":
                text = "".join(process_node(child) for child in node.children).strip()
                href = node.get("href", "")
                if text and href and not href.startswith("javascript:") and not href.startswith("#"):
                    return f" [{text}]({href}) "
                return f" {text} " if text else ""

            if tag_name == "br":
                return "\n"

            if tag_name == "hr":
                return "\n\n---\n\n"

            is_block = tag_name in ["div", "section", "article", "main", "header", "figure", "figcaption"]
            inner = "".join(process_node(child) for child in node.children)
            if is_block:
                return f"\n{inner}\n"
            return inner

        raw_md = process_node(target_root)
        raw_md = re.sub(r'Z7_[A-Za-z0-9_]+', '', raw_md)
        raw_md = re.sub(r'^\s*\{\}\s*$', '', raw_md, flags=re.MULTILINE)

        # Làm sạch dòng trống thừa
        lines = [line.rstrip() for line in raw_md.split("\n")]
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed == "{}" or re.match(r'^Z7_[A-Za-z0-9_]+$', trimmed):
                if not prev_empty:
                    cleaned_lines.append("")
                    prev_empty = True
            else:
                cleaned_lines.append(trimmed)
                prev_empty = False

        markdown_result = "\n".join(cleaned_lines).strip()

        return {
            "markdown": markdown_result,
            "full_text": markdown_result,
            "headings": headings,
            "paragraphs": paragraphs,
            "italics": italics,
            "table_cells": table_cells,
            "sections": sections,
            "tables": tables_data
        }

    def save_records_to_supabase(self, records: List[Dict[str, Any]]) -> int:
        """Lưu toàn bộ danh sách bản ghi cào được vào bảng public.crawled_web_data"""
        if not self.save_to_supabase or not records:
            return 0
            
        self.log(f"Đang đồng bộ {len(records)} bản ghi vào Supabase table 'crawled_web_data'...", "DB")
        saved_count = 0
        
        # Method 1: PostgreSQL Pooler
        try:
            import psycopg2
            from psycopg2.extras import execute_values
            
            conn = psycopg2.connect(
                host=POOLER_HOST,
                port=POOLER_PORT,
                user=POOLER_USER,
                password=PASSWORD,
                dbname=DBNAME,
                connect_timeout=10
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            insert_query = """
            INSERT INTO public.crawled_web_data 
            (source_url, page_title, content_type, section_title, full_text, tables_json, images_json, raw_metadata, status)
            VALUES %s
            """
            
            values = []
            for r in records:
                values.append((
                    r["source_url"],
                    r.get("page_title", ""),
                    r.get("content_type", "main_page"),
                    r.get("section_title", ""),
                    r.get("full_text", ""),
                    json.dumps(r.get("tables_json", []), ensure_ascii=False),
                    json.dumps(r.get("images_json", []), ensure_ascii=False),
                    json.dumps(r.get("raw_metadata", {}), ensure_ascii=False),
                    r.get("status", "SUCCESS")
                ))
                
            execute_values(cursor, insert_query, values)
            saved_count = len(values)
            cursor.close()
            conn.close()
            self.log(f"Đã lưu thành công {saved_count} bản ghi qua PostgreSQL Pooler!", "SUCCESS")
            return saved_count
        except Exception as e1:
            self.log(f"PostgreSQL sync notice ({e1}), thử REST API fallback...", "WARNING")

        # Method 2: REST API Fallback
        try:
            rest_url = f"{SUPABASE_URL}/rest/v1/crawled_web_data"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            resp = requests.post(rest_url, headers=headers, json=records, timeout=15)
            if resp.status_code in [200, 201]:
                saved_count = len(records)
                self.log(f"Đã lưu thành công {saved_count} bản ghi qua Supabase REST API!", "SUCCESS")
            else:
                self.log(f"REST API Response {resp.status_code}: {resp.text}", "WARNING")
        except Exception as e2:
            self.log(f"Lỗi khi lưu Supabase qua REST API: {e2}", "ERROR")

        return saved_count

    def run(self) -> Dict[str, Any]:
        enable_anti_sleep()
        start_time = datetime.now()

        # =========================================================================
        # BƯỚC 0: KIỂM TRA LỊCH SỬ CÀO CỦA WEBSITE TRƯỚC KHI BẮT ĐẦU
        # =========================================================================
        crawl_history = self.check_crawl_history()

        self.log(f"Khởi động tiến trình cào dữ liệu 2 Phase: {self.base_url}", "PROGRESS")
        
        results = {
            "status": "FAILED",
            "target_url": self.base_url,
            "crawled_at": start_time.isoformat(),
            "duration_seconds": 0,
            "main_page": {},
            "subpages_crawled": [],
            "all_images": [],
            "total_images_found": 0,
            "total_subpages_crawled": 0,
            "supabase_records_saved": 0,
            "crawl_history": crawl_history,
            "error_message": None
        }

        db_records_to_save = []

        try:
            with sync_playwright() as p:
                self.log(f"Khởi động Trình duyệt {'(Chế độ ngầm)' if self.headless else '(Mở cửa sổ Chrome)'}...", "INFO")
                try:
                    browser = p.chromium.launch(headless=self.headless, channel="chrome")
                except Exception:
                    browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    viewport={"width": 1600, "height": 1000},
                    locale="vi-VN"
                )

                # =========================================================================
                # PHASE 1: QUÉT VÉT CẠN TOÀN BỘ CÁC THẺ <a> TRÊN TOÀN BỘ WEBSITE & MENU
                # =========================================================================
                targets_to_scrape = self.discover_all_site_links(context)
                
                total_initial = len(targets_to_scrape)
                display_target = self.max_subpages if (self.max_subpages > 0 and self.max_subpages < total_initial) else total_initial
                self.log(f"Bắt đầu Phase 2: Bóc tách nội dung & thẻ Heading h1-h6 (Mục tiêu: {display_target} trang/tài liệu)...", "PROGRESS")

                # =========================================================================
                # PHASE 2: BÓC TÁCH CHI TIẾT TỪNG TRANG & THẺ HEADING (h1, h2, h3, h4...)
                # =========================================================================
                subpages_data = []
                all_images_collector = []
                summary_records = []
                processed_doc_urls = set()
                crawled_count = 0
                queue_idx = 0

                while queue_idx < len(targets_to_scrape):
                    if self.max_subpages > 0 and crawled_count >= self.max_subpages:
                        self.log(f"Đã đạt giới hạn tối đa {self.max_subpages} trang/tài liệu được chỉ định!", "INFO")
                        break

                    target = targets_to_scrape[queue_idx]
                    queue_idx += 1
                    url = target["url"]
                    title = target["title"]
                    content_type = target["type"]

                    # Bỏ qua nếu là tài liệu đã xử lý đính kèm
                    if url in processed_doc_urls and content_type in ["pdf", "word", "excel"]:
                        continue

                    is_first_page = (crawled_count == 0)
                    total_display = self.max_subpages if (self.max_subpages > 0 and self.max_subpages < len(targets_to_scrape)) else len(targets_to_scrape)
                    self.log(f"[{crawled_count + 1}/{total_display}] Đang cào sâu & bóc thẻ H: '{title}' -> {url}", "PROGRESS")

                    # 1. XỬ LÝ ĐẶC BIỆT KHI GẶP LINK TÀI LIỆU PDF
                    if content_type == "pdf" or self._classify_url_type(url) == "pdf":
                        processed_doc_urls.add(url)
                        pdf_data = self.extract_pdf_content(url)
                        page_title = pdf_data.get("file_title") or title
                        total_pages = pdf_data.get("total_pages", 0)

                        if pdf_data["status"] == "UNCHANGED":
                            self.save_item_realtime(
                                summary_record={
                                    "type": "Tài liệu PDF",
                                    "title": page_title,
                                    "url": url,
                                    "file_size": pdf_data.get("file_size", 0),
                                    "char_count": len(pdf_data.get("full_text", "")),
                                    "num_items": total_pages,
                                    "file_path": pdf_data.get("file_path", ""),
                                    "text_path": pdf_data.get("text_path", ""),
                                    "status": "TRÙNG LẶP (Không lưu)"
                                },
                                summary_records=summary_records
                            )
                            crawled_count += 1
                            continue

                        if pdf_data["status"] == "SUCCESS":
                            headings_found = len(pdf_data.get("headings", []))
                            paragraphs_found = len(pdf_data.get("paragraphs", []))

                            summary_item = {
                                "type": "Tài liệu PDF",
                                "title": page_title,
                                "url": url,
                                "file_size": pdf_data.get("file_size", 0),
                                "char_count": len(pdf_data.get("full_text", "")),
                                "num_items": total_pages,
                                "file_path": pdf_data.get("file_path", ""),
                                "text_path": pdf_data.get("text_path", ""),
                                "status": f"{pdf_data.get('change_type', 'MỚI')} (Đã lưu)"
                            }

                            if is_first_page:
                                results["main_page"] = {
                                    "url": url,
                                    "title": page_title,
                                    "headings": pdf_data.get("headings", []),
                                    "paragraphs_count": paragraphs_found,
                                    "italics_count": 0,
                                    "table_cells_count": 0,
                                    "sections_count": len(pdf_data["headings"]),
                                    "tables_count": 0,
                                    "markdown": pdf_data["markdown"],
                                    "raw_text": pdf_data["full_text"],
                                    "tables": [],
                                    "images": []
                                }
                            else:
                                subpages_data.append({
                                    "button_text": title,
                                    "url": url,
                                    "page_title": page_title,
                                    "status": 200,
                                    "headings": pdf_data.get("headings", []),
                                    "paragraphs_count": paragraphs_found,
                                    "italics_count": 0,
                                    "table_cells_count": 0,
                                    "tables_count": 0,
                                    "tables": [],
                                    "markdown": pdf_data["markdown"],
                                    "raw_text": pdf_data["full_text"],
                                    "images": []
                                })

                            db_item = {
                                "source_url": url,
                                "page_title": page_title,
                                "content_type": "pdf",
                                "section_title": title,
                                "full_text": pdf_data["markdown"],
                                "tables_json": [],
                                "images_json": [],
                                "raw_metadata": {
                                    "total_pages": total_pages,
                                    "headings": pdf_data.get("headings", []),
                                    "total_headings": headings_found,
                                    "total_paragraphs": paragraphs_found,
                                    "total_tables": 0,
                                    "total_images": 0,
                                    "change_type": pdf_data.get("change_type", "NEW")
                                },
                                "status": "SUCCESS"
                            }
                            self.save_item_realtime(
                                summary_record=summary_item,
                                summary_records=summary_records,
                                db_record=db_item,
                                db_records_to_save=db_records_to_save,
                                results=results
                            )
                            crawled_count += 1
                            self.log(f"  -> ✅ Bóc thành công File PDF ({total_pages} trang): {headings_found} đề mục, {paragraphs_found} đoạn văn", "SUCCESS")
                            continue

                    # 2. XỬ LÝ ĐẶC BIỆT KHI GẶP LINK TÀI LIỆU WORD (.DOCX / .DOC)
                    elif content_type == "word" or self._classify_url_type(url) == "word":
                        processed_doc_urls.add(url)
                        word_data = self.extract_word_content(url)
                        page_title = word_data.get("file_title") or title

                        if word_data["status"] == "UNCHANGED":
                            self.save_item_realtime(
                                summary_record={
                                    "type": "Tài liệu Word",
                                    "title": page_title,
                                    "url": url,
                                    "file_size": word_data.get("file_size", 0),
                                    "char_count": len(word_data.get("full_text", "")),
                                    "num_items": 0,
                                    "file_path": word_data.get("file_path", ""),
                                    "text_path": word_data.get("text_path", ""),
                                    "status": "TRÙNG LẶP (Không lưu)"
                                },
                                summary_records=summary_records
                            )
                            crawled_count += 1
                            continue

                        if word_data["status"] == "SUCCESS":
                            headings_found = len(word_data.get("headings", []))
                            paragraphs_found = len(word_data.get("paragraphs", []))
                            tables_found = len(word_data.get("tables", []))

                            summary_item = {
                                "type": "Tài liệu Word",
                                "title": page_title,
                                "url": url,
                                "file_size": word_data.get("file_size", 0),
                                "char_count": len(word_data.get("full_text", "")),
                                "num_items": headings_found,
                                "file_path": word_data.get("file_path", ""),
                                "text_path": word_data.get("text_path", ""),
                                "status": f"{word_data.get('change_type', 'MỚI')} (Đã lưu)"
                            }

                            if is_first_page:
                                results["main_page"] = {
                                    "url": url,
                                    "title": page_title,
                                    "headings": word_data.get("headings", []),
                                    "paragraphs_count": paragraphs_found,
                                    "italics_count": 0,
                                    "table_cells_count": 0,
                                    "sections_count": headings_found,
                                    "tables_count": tables_found,
                                    "markdown": word_data["markdown"],
                                    "raw_text": word_data["full_text"],
                                    "tables": word_data["tables"],
                                    "images": []
                                }
                            else:
                                subpages_data.append({
                                    "button_text": title,
                                    "url": url,
                                    "page_title": page_title,
                                    "status": 200,
                                    "headings": word_data.get("headings", []),
                                    "paragraphs_count": paragraphs_found,
                                    "italics_count": 0,
                                    "table_cells_count": 0,
                                    "tables_count": tables_found,
                                    "tables": word_data["tables"],
                                    "markdown": word_data["markdown"],
                                    "raw_text": word_data["full_text"],
                                    "images": []
                                })

                            db_item = {
                                "source_url": url,
                                "page_title": page_title,
                                "content_type": "word",
                                "section_title": title,
                                "full_text": word_data["markdown"],
                                "tables_json": word_data["tables"],
                                "images_json": [],
                                "raw_metadata": {
                                    "headings": word_data.get("headings", []),
                                    "total_headings": headings_found,
                                    "total_paragraphs": paragraphs_found,
                                    "total_tables": tables_found,
                                    "total_images": 0,
                                    "change_type": word_data.get("change_type", "NEW")
                                },
                                "status": "SUCCESS"
                            }
                            self.save_item_realtime(
                                summary_record=summary_item,
                                summary_records=summary_records,
                                db_record=db_item,
                                db_records_to_save=db_records_to_save,
                                results=results
                            )
                            crawled_count += 1
                            self.log(f"  -> ✅ Bóc thành công File Word: {headings_found} đề mục, {paragraphs_found} đoạn văn, {tables_found} bảng", "SUCCESS")
                            continue

                    try:
                        sub_page = context.new_page()
                        response = sub_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(1.5)

                        status_code = response.status if response else 200
                        if status_code >= 400:
                            self.log(f"  -> Lỗi HTTP {status_code}: {url}", "WARNING")
                            sub_page.close()
                            continue

                        # Smooth scroll
                        self.smooth_scroll_full_page(sub_page)

                        # Auto-click collapses/tabs/accordions
                        accordions = sub_page.query_selector_all(".accordion, .collapse, [data-toggle='collapse'], .tab-header, .tab, [role='tab'], .faq-header, .show-more")
                        for acc in accordions[:10]:
                            try:
                                acc_txt = (acc.inner_text() or "").strip()
                                if not any(ex in acc_txt.lower() for ex in EXCLUDE_CLICK_KEYWORDS):
                                    acc.click(timeout=500)
                                    time.sleep(0.1)
                            except Exception:
                                pass

                        # Extract Structured Data
                        html_content = sub_page.content()
                        parsed_data = self.extract_clean_text_and_tables(html_content)
                        images = self.extract_images_from_page(sub_page, url)
                        page_title = sub_page.title()

                        # TỰ ĐỘNG QUÉT & TẢI XUỐNG TOÀN BỘ FILE TÀI LIỆU VÀ ĐƯỜNG LINK CON MỚI TRONG TRANG NÀY
                        attached_docs_in_page = []
                        for a_tag in sub_page.query_selector_all("a[href]"):
                            try:
                                href = a_tag.get_attribute("href") or ""
                                full_link_url = self._normalize_url(href, url)
                                if not full_link_url:
                                    continue

                                # 1. Nếu là tệp tài liệu (PDF, Word, Excel...)
                                if self._is_doc_url(full_link_url) and full_link_url not in processed_doc_urls:
                                    processed_doc_urls.add(full_link_url)
                                    doc_title = (a_tag.inner_text() or "").strip() or os.path.basename(urlparse(full_link_url).path)
                                    doc_type = self._classify_url_type(full_link_url)
                                    attached_docs_in_page.append({"url": full_link_url, "title": doc_title, "type": doc_type})

                                # 2. Khám phá liên tục link nội bộ mới đưa vào hàng đợi cào tiếp
                                elif self._is_valid_internal_url(full_link_url) and full_link_url not in self.seen_urls:
                                    self.seen_urls.add(full_link_url)
                                    link_title = (a_tag.inner_text() or "").strip()
                                    if self.max_subpages == 0 or len(targets_to_scrape) < self.max_subpages * 4:
                                        targets_to_scrape.append({
                                            "url": full_link_url,
                                            "title": link_title or self._title_from_url(full_link_url),
                                            "type": self._classify_url_type(full_link_url)
                                        })
                            except Exception:
                                pass

                        downloaded_attachments_md = ""
                        for doc in attached_docs_in_page:
                            doc_url = doc["url"]
                            doc_title = doc["title"]
                            doc_type = doc["type"]
                            self.log(f"  📎 Phát hiện tệp đính kèm trong trang: '{doc_title}' -> {doc_url}", "PROGRESS")
                            
                            if doc_type == "pdf":
                                doc_data = self.extract_pdf_content(doc_url)
                                p_title = doc_data.get("file_title") or doc_title
                                total_p = doc_data.get("total_pages", 0)

                                if doc_data["status"] == "UNCHANGED":
                                    self.save_item_realtime(
                                        summary_record={
                                            "type": "Tài liệu PDF",
                                            "title": p_title,
                                            "url": doc_url,
                                            "file_size": doc_data.get("file_size", 0),
                                            "char_count": len(doc_data.get("full_text", "")),
                                            "num_items": total_p,
                                            "file_path": doc_data.get("file_path", ""),
                                            "text_path": doc_data.get("text_path", ""),
                                            "status": "TRÙNG LẶP (Không lưu)"
                                        },
                                        summary_records=summary_records
                                    )
                                elif doc_data["status"] == "SUCCESS":
                                    summary_item = {
                                        "type": "Tài liệu PDF",
                                        "title": p_title,
                                        "url": doc_url,
                                        "file_size": doc_data.get("file_size", 0),
                                        "char_count": len(doc_data.get("full_text", "")),
                                        "num_items": total_p,
                                        "file_path": doc_data.get("file_path", ""),
                                        "text_path": doc_data.get("text_path", ""),
                                        "status": f"{doc_data.get('change_type', 'MỚI')} (Đã lưu)"
                                    }
                                    db_item = {
                                        "source_url": doc_url,
                                        "page_title": p_title,
                                        "content_type": "pdf",
                                        "section_title": f"Tài liệu đính kèm từ: {page_title}",
                                        "full_text": doc_data["markdown"],
                                        "tables_json": [],
                                        "images_json": [],
                                        "raw_metadata": {
                                            "total_pages": total_p,
                                            "parent_page": url,
                                            "parent_title": page_title,
                                            "change_type": doc_data.get("change_type", "NEW")
                                        },
                                        "status": "SUCCESS"
                                    }
                                    self.save_item_realtime(
                                        summary_record=summary_item,
                                        summary_records=summary_records,
                                        db_record=db_item,
                                        db_records_to_save=db_records_to_save,
                                        results=results
                                    )
                                    downloaded_attachments_md += f"- [📄 {p_title} ({os.path.basename(doc_data['file_path'])})]({doc_url}) — Đã tải file gốc & bóc tách {total_p} trang -> File Markdown: `{doc_data.get('text_path', '')}`\n"
                                    self.log(f"    -> ✅ Bóc tách thành công PDF '{p_title}' ({total_p} trang)", "SUCCESS")
                                    # Đưa tài liệu PDF vào subpages_data để hiển thị đầy đủ trên Web UI & báo cáo
                                    subpages_data.append({
                                        "button_text": f"Tài liệu PDF: {p_title}",
                                        "url": doc_url,
                                        "page_title": p_title,
                                        "status": 200,
                                        "headings": doc_data.get("headings", []),
                                        "paragraphs_count": len(doc_data.get("paragraphs", [])),
                                        "italics_count": 0,
                                        "table_cells_count": 0,
                                        "tables_count": 0,
                                        "tables": [],
                                        "markdown": doc_data["markdown"],
                                        "raw_text": doc_data["full_text"],
                                        "images": []
                                    })
                            
                            elif doc_type == "word":
                                doc_data = self.extract_word_content(doc_url)
                                p_title = doc_data.get("file_title") or doc_title

                                if doc_data["status"] == "UNCHANGED":
                                    self.save_item_realtime(
                                        summary_record={
                                            "type": "Tài liệu Word",
                                            "title": p_title,
                                            "url": doc_url,
                                            "file_size": doc_data.get("file_size", 0),
                                            "char_count": len(doc_data.get("full_text", "")),
                                            "num_items": 0,
                                            "file_path": doc_data.get("file_path", ""),
                                            "text_path": doc_data.get("text_path", ""),
                                            "status": "TRÙNG LẶP (Không lưu)"
                                        },
                                        summary_records=summary_records
                                    )
                                elif doc_data["status"] == "SUCCESS":
                                    summary_item = {
                                        "type": "Tài liệu Word",
                                        "title": p_title,
                                        "url": doc_url,
                                        "file_size": doc_data.get("file_size", 0),
                                        "char_count": len(doc_data.get("full_text", "")),
                                        "num_items": len(doc_data.get("headings", [])),
                                        "file_path": doc_data.get("file_path", ""),
                                        "text_path": doc_data.get("text_path", ""),
                                        "status": f"{doc_data.get('change_type', 'MỚI')} (Đã lưu)"
                                    }
                                    db_item = {
                                        "source_url": doc_url,
                                        "page_title": p_title,
                                        "content_type": "word",
                                        "section_title": f"Tài liệu đính kèm từ: {page_title}",
                                        "full_text": doc_data["markdown"],
                                        "tables_json": doc_data.get("tables", []),
                                        "images_json": [],
                                        "raw_metadata": {
                                            "headings": doc_data.get("headings", []),
                                            "parent_page": url,
                                            "parent_title": page_title,
                                            "change_type": doc_data.get("change_type", "NEW")
                                        },
                                        "status": "SUCCESS"
                                    }
                                    self.save_item_realtime(
                                        summary_record=summary_item,
                                        summary_records=summary_records,
                                        db_record=db_item,
                                        db_records_to_save=db_records_to_save,
                                        results=results
                                    )
                                    downloaded_attachments_md += f"- [📄 {p_title} ({os.path.basename(doc_data['file_path'])})]({doc_url}) — Đã tải file gốc & bóc tách -> File Markdown: `{doc_data.get('text_path', '')}`\n"
                                    self.log(f"    -> ✅ Bóc tách thành công Word '{p_title}'", "SUCCESS")
                                    # Đưa tài liệu Word vào subpages_data để hiển thị trên Web UI & báo cáo
                                    subpages_data.append({
                                        "button_text": f"Tài liệu Word: {p_title}",
                                        "url": doc_url,
                                        "page_title": p_title,
                                        "status": 200,
                                        "headings": doc_data.get("headings", []),
                                        "paragraphs_count": len(doc_data.get("paragraphs", [])),
                                        "italics_count": 0,
                                        "table_cells_count": 0,
                                        "tables_count": len(doc_data.get("tables", [])),
                                        "tables": doc_data.get("tables", []),
                                        "markdown": doc_data["markdown"],
                                        "raw_text": doc_data["full_text"],
                                        "images": []
                                    })

                        if downloaded_attachments_md:
                            parsed_data["markdown"] += f"\n\n---\n\n### 📎 TÀI LIỆU ĐÍNH KÈM ĐÃ TỰ ĐỘNG TẢI XUỐNG & BÓC TÁCH:\n{downloaded_attachments_md}\n"

                        for img in images:
                            if img["url"] not in [x["url"] for x in all_images_collector]:
                                all_images_collector.append(img)

                        headings_found = len(parsed_data.get("headings", []))
                        paragraphs_found = len(parsed_data.get("paragraphs", []))
                        italics_found = len(parsed_data.get("italics", []))
                        cells_found = len(parsed_data.get("table_cells", []))

                        if is_first_page:
                            results["main_page"] = {
                                "url": url,
                                "title": page_title,
                                "headings": parsed_data.get("headings", []),
                                "paragraphs_count": paragraphs_found,
                                "italics_count": italics_found,
                                "table_cells_count": cells_found,
                                "sections_count": len(parsed_data["sections"]),
                                "tables_count": len(parsed_data["tables"]),
                                "markdown": parsed_data["markdown"],
                                "raw_text": parsed_data["full_text"],
                                "tables": parsed_data["tables"],
                                "images": images
                            }
                        else:
                            subpages_data.append({
                                "button_text": title,
                                "url": url,
                                "page_title": page_title,
                                "status": status_code,
                                "headings": parsed_data.get("headings", []),
                                "paragraphs_count": paragraphs_found,
                                "italics_count": italics_found,
                                "table_cells_count": cells_found,
                                "tables_count": len(parsed_data["tables"]),
                                "tables": parsed_data["tables"],
                                "markdown": parsed_data["markdown"],
                                "raw_text": parsed_data["full_text"],
                                "images": images
                            })

                        # ---------------------------------------------------------
                        # [SO SÁNH TRÙNG LẶP] Kiểm tra mã hash nội dung trang Web (dựa trên văn bản thuần bóc tách)
                        # ---------------------------------------------------------
                        is_dup_page, page_change_type, page_hash = self.check_duplicate(url, text_content=parsed_data["full_text"])
                        page_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', urlparse(url).path.strip('/') or 'index')[:60]
                        page_md_path = os.path.join(self.pages_dir, f"{page_slug}_{crawled_count + 1}.md")

                        if is_dup_page and os.path.exists(page_md_path):
                            self.log(f"  ⏭️ [TRÙNG LẶP] Trang '{page_title}' không có thay đổi nội dung -> BỎ QUA KHÔNG LƯU ĐÈ!", "INFO")
                            self.save_item_realtime(
                                summary_record={
                                    "type": "Web HTML",
                                    "title": page_title,
                                    "url": url,
                                    "file_size": len(html_content.encode("utf-8", errors="ignore")),
                                    "char_count": len(parsed_data["full_text"]),
                                    "num_items": headings_found,
                                    "file_path": "",
                                    "text_path": page_md_path,
                                    "status": "TRÙNG LẶP (Không lưu)"
                                },
                                summary_records=summary_records
                            )
                        else:
                            self.log(f"  💾 [{'MỚI' if page_change_type == 'NEW' else 'CẬP NHẬT'}] Lưu dữ liệu trang '{page_title}'...", "SUCCESS")
                            try:
                                with open(page_md_path, "w", encoding="utf-8") as f:
                                    f.write(f"# {page_title}\n\n")
                                    f.write(f"- **URL:** {url}\n\n---\n\n")
                                    f.write(parsed_data["markdown"])
                            except Exception:
                                page_md_path = ""

                            db_item = {
                                "source_url": url,
                                "page_title": page_title,
                                "content_type": content_type,
                                "section_title": title,
                                "full_text": parsed_data["markdown"],
                                "tables_json": parsed_data["tables"],
                                "images_json": images,
                                "raw_metadata": {
                                    "headings": parsed_data.get("headings", []),
                                    "total_headings": headings_found,
                                    "total_paragraphs": paragraphs_found,
                                    "total_italics": italics_found,
                                    "total_table_cells": cells_found,
                                    "total_tables": len(parsed_data["tables"]),
                                    "total_images": len(images),
                                    "content_hash": page_hash,
                                    "change_type": page_change_type
                                },
                                "status": "SUCCESS"
                            }

                            self.content_registry[url] = {
                                "hash": page_hash,
                                "path": page_md_path,
                                "type": "page",
                                "title": page_title,
                                "updated_at": datetime.now().isoformat()
                            }

                            summary_item = {
                                "type": "Web HTML",
                                "title": page_title,
                                "url": url,
                                "file_size": len(html_content.encode("utf-8", errors="ignore")),
                                "char_count": len(parsed_data["full_text"]),
                                "num_items": headings_found,
                                "file_path": "",
                                "text_path": page_md_path,
                                "status": f"{'MỚI' if page_change_type == 'NEW' else 'CẬP NHẬT'} (Đã lưu)"
                            }

                            self.save_item_realtime(
                                summary_record=summary_item,
                                summary_records=summary_records,
                                db_record=db_item,
                                db_records_to_save=db_records_to_save,
                                results=results
                            )

                        crawled_count += 1
                        # Dọn dẹp RAM định kỳ sau mỗi 20 trang để máy chạy êm, chống tràn RAM
                        if crawled_count % 20 == 0:
                            gc.collect()

                        self.log(f"  -> ✅ Bóc thành công: {headings_found} thẻ H, {paragraphs_found} thẻ P, {cells_found} ô TD, {italics_found} thẻ I, {len(parsed_data['tables'])} bảng biểu, {len(images)} hình ảnh", "SUCCESS")
                        sub_page.close()

                    except Exception as err:
                        self.log(f"  -> Lỗi khi cào URL {url}: {err}", "WARNING")
                        try:
                            sub_page.close()
                        except:
                            pass

                browser.close()
                self._save_content_registry()

                results["subpages_crawled"] = subpages_data
                results["all_images"] = all_images_collector
                results["total_images_found"] = len(all_images_collector)
                results["total_subpages_crawled"] = len(subpages_data)
                results["status"] = "SUCCESS"

                # Dữ liệu đã được lưu Realtime từng trang vào Supabase
                saved_db_count = results["supabase_records_saved"]

                # Save structured JSON & Markdown locally
                self._save_outputs(results)

                # Export summary spreadsheet CSV
                self.export_summary_csv(summary_records)

                # Thống kê phân loại trùng lặp & lưu mới
                dup_count = sum(1 for r in summary_records if "TRÙNG LẶP" in r.get("status", ""))
                new_count = sum(1 for r in summary_records if "MỚI" in r.get("status", ""))
                updated_count = sum(1 for r in summary_records if "CẬP NHẬT" in r.get("status", ""))
                results["stats_duplicates"] = dup_count
                results["stats_new"] = new_count
                results["stats_updated"] = updated_count

        except Exception as e:
            results["status"] = "FAILED"
            results["error_message"] = str(e)
            self.log(f"Crawl thất bại: {e}", "ERROR")

        duration = (datetime.now() - start_time).total_seconds()
        results["duration_seconds"] = round(duration, 2)

        status_banner = "🎉 CRAWL HOÀN TẤT TOÀN BỘ WEBSITE!" if results["status"] == "SUCCESS" else "❌ CRAWL THẤT BÀI!"
        print("\n" + "="*75, flush=True)
        print(f"       {status_banner} (Thời gian xử lý: {results['duration_seconds']}s)", flush=True)
        print("="*75, flush=True)
        print(f" - URL mục tiêu:            {self.base_url}", flush=True)
        print(f" - Trạng thái:              {results['status']}", flush=True)
        print(f" - Tổng tài nguyên quét:    {len(summary_records)}", flush=True)
        print(f"   ├─ Mới tinh (Đã lưu):     {results.get('stats_new', 0)}", flush=True)
        print(f"   ├─ Cập nhật (Đã lưu):     {results.get('stats_updated', 0)}", flush=True)
        print(f"   └─ Trùng lặp (Bỏ qua):    {results.get('stats_duplicates', 0)}", flush=True)
        print(f" - Tổng trang/bài viết cào: {results['total_subpages_crawled'] + (1 if results['main_page'] else 0)}", flush=True)
        print(f" - Tổng hình ảnh trích xuất: {results['total_images_found']}", flush=True)
        print(f" - Bản ghi lưu Supabase:     {results['supabase_records_saved']} (Table: public.crawled_web_data)", flush=True)
        print(f" - Thư mục lưu trữ:         {self.domain_dir}", flush=True)
        print(f" - Bảng tổng hợp:           {self.summary_csv_path}", flush=True)
        if results.get("error_message"):
            print(f" - Chi tiết lỗi:            {results['error_message']}", flush=True)
        print("="*75 + "\n", flush=True)
        disable_anti_sleep()
        return results

    def export_summary_csv(self, records: List[Dict[str, Any]]):
        """Xuất bảng tổng hợp thống kê toàn bộ tài nguyên đã crawl sang CSV (UTF-8 BOM)"""
        try:
            with open(self.summary_csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "STT", "Loại tài nguyên", "Tiêu đề", "URL nguồn", 
                    "Dung lượng (Bytes)", "Số ký tự", "Số đề mục / Trang", 
                    "Đường dẫn file gốc", "Đường dẫn file Text/MD", "Trạng thái"
                ])
                for idx, r in enumerate(records, 1):
                    writer.writerow([
                        idx,
                        r.get("type", "Web HTML"),
                        r.get("title", ""),
                        r.get("url", ""),
                        r.get("file_size", 0),
                        r.get("char_count", 0),
                        r.get("num_items", 0),
                        r.get("file_path", ""),
                        r.get("text_path", ""),
                        r.get("status", "SUCCESS")
                    ])
            self.log(f"📊 Đã xuất bảng tổng hợp tại: {self.summary_csv_path}", "SUCCESS")
        except Exception as e:
            self.log(f"Lỗi khi xuất bảng summary.csv: {e}", "WARNING")

    def _save_outputs(self, results: Dict[str, Any]):
        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', urlparse(self.base_url).path.strip('/') or 'home')
        
        # 1. Lưu trong thư mục riêng theo domain
        domain_json_path = os.path.join(self.domain_dir, "crawl_report.json")
        domain_md_path = os.path.join(self.domain_dir, "crawl_report.md")
        
        # 2. Lưu ở output_dir gốc (để tương thích ngược với crawler_server)
        root_json_path = os.path.join(self.output_dir, f"{slug}.json")
        root_md_path = os.path.join(self.output_dir, f"{slug}.md")
        
        for j_path in [domain_json_path, root_json_path]:
            try:
                with open(j_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        self.log(f"Đã lưu dữ liệu JSON tại: {domain_json_path}", "SUCCESS")

        md_text = f"# BÁO CÁO CRAWL DỮ LIỆU TOÀN DIỆN WEBSITE\n\n"
        md_text += f"- **URL Mục tiêu:** {results['target_url']}\n"
        md_text += f"- **Trạng thái:** {results['status']}\n"
        md_text += f"- **Thời gian cào:** {results['crawled_at']}\n"
        md_text += f"- **Tổng trang con & bài viết đã cào:** {results['total_subpages_crawled']}\n"
        md_text += f"- **Tổng hình ảnh trích xuất:** {results['total_images_found']}\n"
        md_text += f"- **Bản ghi đã lưu Supabase DB:** {results.get('supabase_records_saved', 0)}\n"
        md_text += f"- **Thư mục lưu trữ chi tiết:** `{self.domain_dir}`\n\n"
        md_text += "---\n\n"
        
        md_text += "## 1. NỘI DUNG TRANG CHÍNH TỔNG QUAN\n\n"
        md_text += f"### Tiêu đề: {results['main_page'].get('title', '')}\n\n"
        main_md = results['main_page'].get('markdown', '') or results['main_page'].get('raw_text', '')
        md_text += main_md + "\n\n"
        
        md_text += "---\n\n"
        md_text += "## 2. NỘI DUNG CHI TIẾT TẤT CẢ CÁC BÀI VIẾT & TRANG CON (ĐẦY ĐỦ THẺ H1-H6, PDF, WORD)\n\n"
        for sp_idx, sp in enumerate(results["subpages_crawled"], 1):
            heading_title = sp.get('page_title') or sp.get('button_text') or f'Trang {sp_idx}'
            md_text += f"### 📍 [{sp_idx}] {heading_title}\n\n"
            md_text += f"- **Tiêu đề / Nút:** {sp['button_text']}\n"
            md_text += f"- **URL:** {sp['url']}\n"
            if sp.get("tables_count", 0) > 0:
                md_text += f"- **Số lượng bảng biểu:** {sp['tables_count']}\n\n"
            if sp.get("tables"):
                md_text += "#### Bảng dữ liệu trích xuất:\n\n"
                for tbl_idx, tbl in enumerate(sp["tables"], 1):
                    md_text += f"*Bảng {tbl_idx}:*\n\n"
                    for row in tbl:
                        md_text += "| " + " | ".join(row) + " |\n"
                    md_text += "\n"
            md_text += "#### Nội dung chi tiết:\n\n"
            sub_md = sp.get('markdown', '') or sp.get('raw_text', '')
            md_text += sub_md + "\n\n---\n\n"
            
        md_text += "## 3. DANH SÁCH TOÀN BỘ HÌNH ẢNH TRÍCH XUẤT\n\n"
        for img_idx, img in enumerate(results["all_images"], 1):
            md_text += f"{img_idx}. [{img.get('alt') or 'Hình ảnh'}]({img['url']})\n"
            
        for m_path in [domain_md_path, root_md_path]:
            try:
                with open(m_path, "w", encoding="utf-8") as f:
                    f.write(md_text)
            except Exception:
                pass

        self.log(f"Đã lưu báo cáo Markdown tại: {domain_md_path}", "SUCCESS")


def main():
    parser = argparse.ArgumentParser(description="Universal 2-Phase Deep Web Crawler & Supabase Hub")
    parser.add_argument("--url", default="https://rcgv.vn/", help="Target URL to crawl")
    parser.add_argument("--output-dir", default="crawled_data", help="Output directory")
    parser.add_argument("--max-subpages", type=int, default=50, help="Max subpages/articles to scrape (0 for unlimited)")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--no-supabase", action="store_true", default=False, help="Disable saving to Supabase")
    args = parser.parse_args()

    crawler = DeepWebCrawler(
        base_url=args.url,
        output_dir=args.output_dir,
        headless=args.headless,
        max_subpages=args.max_subpages,
        save_to_supabase=not args.no_supabase
    )
    crawler.run()

if __name__ == "__main__":
    main()
