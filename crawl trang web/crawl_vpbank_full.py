"""
VPBANK TOÀN DIỆN CRAWLER (FULL WEBSITE & PDF EXTRACTOR)
======================================================
Mục tiêu:
1. Thu thập TOÀN BỘ nội dung tất cả các trang web của https://www.vpbank.com.vn/:
   - Bóc tách tiêu đề, breadcrumbs, danh mục, nội dung bài viết dạng văn bản sạch (Clean Text / Markdown).
   - Lưu vào: D:\\VPBank_Full_Data\\pages\\
2. Thu thập TOÀN BỘ các file PDF đính kèm trên toàn bộ website:
   - Tải file PDF gốc lưu vào: D:\\VPBank_Full_Data\\pdfs\\
   - Trích xuất toàn bộ nội dung chữ (Text) từng trang của PDF lưu vào: D:\\VPBank_Full_Data\\pdf_texts\\
3. Cơ sở dữ liệu theo dõi SQLite (D:\\VPBank_Full_Data\\crawl_index.db):
   - Quản lý trạng thái từng URL (web và pdf), hỗ trợ Resume 100% khi dừng hoặc gặp lỗi mạng.
   - Xuất dữ liệu thống kê ra D:\\VPBank_Full_Data\\summary.csv.
4. Cơ chế chống chặn WAF (Imperva Rate Limit):
   - Giãn cách truy vấn (Rate Limiting) an toàn.
   - Tự động tạm dừng (Backoff) nếu phát hiện cảnh báo mã lỗi 403 / 429.
"""

import os
import sys
import re
import time
import json
import csv
import sqlite3
import argparse
import urllib.parse
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
import pypdf

# Đường dẫn lưu trữ trên ổ D
OUTPUT_ROOT = Path(r"D:\VPBank_Full_Data")
PAGES_DIR = OUTPUT_ROOT / "pages"
PDFS_DIR = OUTPUT_ROOT / "pdfs"
PDF_TEXTS_DIR = OUTPUT_ROOT / "pdf_texts"
DB_PATH = OUTPUT_ROOT / "crawl_index.db"
SUMMARY_CSV = OUTPUT_ROOT / "summary.csv"

# Checkpoint đã quét trước đó từ phiên làm việc trước
PREV_CHECKPOINT = Path(r"D:\VPBank_Crawl_Data\checkpoint.json")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.vpbank.com.vn/',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
}

def init_environment():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    PDF_TEXTS_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            type TEXT,            -- 'web_page' hoặc 'pdf'
            title TEXT,
            category TEXT,
            status TEXT,          -- 'pending', 'completed', 'failed'
            file_path TEXT,
            text_path TEXT,
            file_size INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0,
            num_pages INTEGER DEFAULT 0,
            error TEXT,
            updated_at TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON items(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON items(type)')
    conn.commit()
    conn.close()

def sanitize_filename(name: str, max_length: int = 100) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = re.sub(r'\s+', '_', clean).strip('_')
    if len(clean) > max_length:
        clean = clean[:max_length]
    return clean or "document"

def seed_database():
    """Khởi tạo danh sách URL từ sitemap và danh mục PDF đã quét"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM items")
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute("SELECT COUNT(*), type, status FROM items GROUP BY type, status")
        stats = cursor.fetchall()
        print(f"[*] Cơ sở dữ liệu đã có {count} mục cần xử lý:", flush=True)
        for s in stats:
            print(f"    - Loại: {s[1]:<10} | Trạng thái: {s[2]:<10} | Số lượng: {s[0]}", flush=True)
        conn.close()
        return

    print("[*] Đang khởi tạo danh mục toàn bộ website từ Sitemap và API...", flush=True)
    all_items = []

    # 1. Nạp các liên kết trang web từ Sitemap (6.912 URLs)
    sitemap_cache = Path(r"C:\Users\vuong\.gemini\antigravity\brain\a6be2d77-16b3-45ae-9eda-e9d8a5c7d776\.system_generated\steps\7\content.md")
    if sitemap_cache.exists():
        try:
            with open(sitemap_cache, 'r', encoding='utf-8') as f:
                text = f.read()
            xml_start = text.find('<?xml')
            if xml_start != -1:
                root = ET.fromstring(text[xml_start:])
                for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    u = elem.text.strip() if elem.text else ''
                    if u and u.startswith('http'):
                        all_items.append((u, 'web_page', '', '', 'pending'))
        except Exception as e:
            print(f"[!] Lỗi đọc sitemap: {e}", flush=True)

    # 2. Nạp 2.417 liên kết file PDF từ checkpoint trước
    if PREV_CHECKPOINT.exists():
        try:
            with open(PREV_CHECKPOINT, 'r', encoding='utf-8') as f:
                pdf_docs = json.load(f)
            for doc in pdf_docs:
                u = doc.get('url', '').strip()
                t = doc.get('title', '').strip()
                c = doc.get('category_title') or doc.get('category_path', '')
                if u and u.startswith('http'):
                    all_items.append((u, 'pdf', t, c, 'pending'))
        except Exception as e:
            print(f"[!] Lỗi đọc PDF checkpoint: {e}", flush=True)

    # Lưu vào SQLite với INSERT OR IGNORE
    cursor.executemany('''
        INSERT OR IGNORE INTO items (url, type, title, category, status)
        VALUES (?, ?, ?, ?, ?)
    ''', all_items)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM items")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM items WHERE type='web_page'")
    pages_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM items WHERE type='pdf'")
    pdf_count = cursor.fetchone()[0]

    print(f"[+] Khởi tạo thành công: {total} mục (Trang web HTML: {pages_count}, File PDF: {pdf_count})", flush=True)
    conn.close()

def extract_clean_web_content(html: str, url: str) -> dict:
    """Bóc tách văn bản sạch, tiêu đề, và liên kết PDF mới từ HTML trang web"""
    soup = BeautifulSoup(html, 'html.parser')

    # Trích xuất tiêu đề
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find('h1'):
        title = soup.find('h1').get_text(strip=True)

    # Trích xuất mô tả meta
    meta_desc = ""
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_tag and desc_tag.get('content'):
        meta_desc = desc_tag['content'].strip()

    # Tìm các liên kết PDF mới xuất hiện trong trang web
    discovered_pdfs = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if '.pdf' in href.lower():
            full_pdf_url = urllib.parse.urljoin(url, href).rstrip('\\/.,')
            if full_pdf_url.startswith('http'):
                discovered_pdfs.add((full_pdf_url, a.get_text(strip=True)))

    # Loại bỏ các thành phần rác (script, style, navigation, footer, iframe...)
    for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'header', 'footer', 'nav']):
        tag.decompose()

    # Lấy văn bản chính
    lines = (line.strip() for line in soup.get_text().splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = '\n'.join(chunk for chunk in chunks if chunk)

    formatted_content = f"TIÊU ĐỀ: {title}\n"
    formatted_content += f"URL GỐC: {url}\n"
    if meta_desc:
        formatted_content += f"MÔ TẢ: {meta_desc}\n"
    formatted_content += f"{'='*70}\n\n"
    formatted_content += clean_text

    return {
        'title': title,
        'clean_text': formatted_content,
        'char_count': len(clean_text),
        'discovered_pdfs': list(discovered_pdfs)
    }

def process_web_page(item_id: int, url: str, session: requests.Session) -> dict:
    """Tải và bóc tách một trang web HTML"""
    slug = urllib.parse.urlparse(url).path.strip('/').replace('/', '_') or 'home'
    filename = f"{item_id:05d}_{sanitize_filename(slug)}.txt"
    filepath = PAGES_DIR / filename

    result = {
        'status': 'failed',
        'file_path': str(filepath),
        'text_path': str(filepath),
        'char_count': 0,
        'file_size': 0,
        'title': '',
        'error': '',
        'new_pdfs': []
    }

    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 200:
            extracted = extract_clean_web_content(resp.text, url)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(extracted['clean_text'])

            result['status'] = 'completed'
            result['title'] = extracted['title']
            result['char_count'] = extracted['char_count']
            result['file_size'] = filepath.stat().st_size
            result['new_pdfs'] = extracted['discovered_pdfs']
        elif resp.status_code in [403, 429]:
            result['status'] = 'waf_blocked'
            result['error'] = f'HTTP {resp.status_code}'
        else:
            result['status'] = f'http_{resp.status_code}'
    except Exception as e:
        result['error'] = str(e)

    return result

def process_pdf_file(item_id: int, url: str, title: str, session: requests.Session) -> dict:
    """Tải và trích xuất nội dung file PDF"""
    raw_name = Path(urllib.parse.urlparse(url).path).name
    if not raw_name.lower().endswith('.pdf'):
        raw_name += '.pdf'

    base_name = f"{item_id:05d}_{sanitize_filename(raw_name)}"
    pdf_path = PDFS_DIR / base_name
    txt_path = PDF_TEXTS_DIR / f"{base_name[:-4]}.txt"

    result = {
        'status': 'failed',
        'file_path': str(pdf_path),
        'text_path': str(txt_path),
        'file_size': 0,
        'char_count': 0,
        'num_pages': 0,
        'error': ''
    }

    try:
        parts = urllib.parse.urlsplit(url)
        safe_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(parts.path), parts.query, parts.fragment))

        # Tải file PDF nếu chưa tồn tại
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            resp = session.get(safe_url, timeout=25, stream=True)
            if resp.status_code == 200:
                with open(pdf_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                # Kiểm tra magic bytes
                if pdf_path.stat().st_size < 1500:
                    with open(pdf_path, 'rb') as f:
                        header = f.read(10)
                    if not header.startswith(b'%PDF'):
                        pdf_path.unlink(missing_ok=True)
                        result['status'] = 'waf_blocked'
                        result['error'] = 'Chặn WAF (nhận HTML thay vì PDF)'
                        return result
            elif resp.status_code in [403, 429]:
                result['status'] = 'waf_blocked'
                result['error'] = f'HTTP {resp.status_code}'
                return result
            else:
                result['status'] = f'http_{resp.status_code}'
                return result

        result['file_size'] = pdf_path.stat().st_size

        # Bóc tách nội dung Text từ PDF
        reader = pypdf.PdfReader(str(pdf_path))
        result['num_pages'] = len(reader.pages)
        full_text = []

        for p_idx, page in enumerate(reader.pages, start=1):
            try:
                txt = page.extract_text() or ''
                if txt.strip():
                    full_text.append(f"--- TRANG {p_idx} ---\n{txt}\n")
            except Exception:
                full_text.append(f"--- TRANG {p_idx} [Lỗi đọc text] ---\n")

        extracted_text = "\n".join(full_text)
        result['char_count'] = len(extracted_text)

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"TIÊU ĐỀ: {title}\n")
            f.write(f"URL PDF GỐC: {url}\n")
            f.write(f"SỐ TRANG: {result['num_pages']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(extracted_text)

        result['status'] = 'completed'
    except Exception as e:
        result['error'] = str(e)

    return result

def export_summary():
    """Xuất file thống kê CSV tổng hợp tất cả tài nguyên đã crawl"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, type, title, category, status, file_size, char_count, num_pages, file_path, text_path, url, error
        FROM items
    ''')
    rows = cursor.fetchall()
    conn.close()

    headers = ['ID', 'Loại', 'Tiêu đề', 'Danh mục', 'Trạng thái', 'Kích thước (Bytes)', 'Số ký tự', 'Số trang', 'Đường dẫn File', 'Đường dẫn Text', 'URL', 'Ghi chú / Lỗi']
    with open(SUMMARY_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="VPBank Full Content & PDF Crawler")
    parser.add_argument('--delay', type=float, default=0.6, help="Độ trễ giữa các lượt tải (giây)")
    parser.add_argument('--filter-type', choices=['all', 'web_page', 'pdf'], default='all', help="Lọc loại cần crawl")
    args = parser.parse_args()

    print("="*75, flush=True)
    print("VPBANK TOÀN DIỆN CRAWLER (TẤT CẢ TRANG WEB & FILE PDF)", flush=True)
    print(f"Thư mục lưu trữ: {OUTPUT_ROOT}", flush=True)
    print("="*75, flush=True)

    init_environment()
    seed_database()

    session = requests.Session()
    session.headers.update(HEADERS)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT id, url, type, title FROM items WHERE status != 'completed'"
    if args.filter_type != 'all':
        query += f" AND type = '{args.filter_type}'"
    query += " ORDER BY type DESC, id ASC"  # Ưu tiên các trang web trước hoặc theo thứ tự

    cursor.execute(query)
    pending_items = cursor.fetchall()
    total_pending = len(pending_items)

    print(f"\n[*] Bắt đầu xử lý {total_pending} mục còn lại...", flush=True)

    consecutive_waf = 0

    for idx, (item_id, url, item_type, title) in enumerate(pending_items, start=1):
        # 1. Tạm dừng nếu bị WAF chặn
        if consecutive_waf > 0:
            wait_time = 30 * min(consecutive_waf, 4)
            print(f"\n[!] WAF Imperva đang giới hạn. Tự động tạm nghỉ {wait_time}s trước khi thử lại...", flush=True)
            time.sleep(wait_time)

        # 2. Thực hiện crawl theo loại tài nguyên
        if item_type == 'web_page':
            res = process_web_page(item_id, url, session)
            # Thêm các file PDF mới phát hiện vào DB nếu có
            if res.get('new_pdfs'):
                new_entries = [(p_url, 'pdf', p_title, 'web_extracted', 'pending') for p_url, p_title in res['new_pdfs']]
                cursor.executemany("INSERT OR IGNORE INTO items (url, type, title, category, status) VALUES (?, ?, ?, ?, ?)", new_entries)
                conn.commit()
        else:
            res = process_pdf_file(item_id, url, title, session)

        # 3. Đánh giá trạng thái WAF
        if res['status'] == 'waf_blocked':
            consecutive_waf += 1
            cursor.execute('''
                UPDATE items SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?
            ''', ('pending', res['error'], item_id))
        else:
            consecutive_waf = 0
            cursor.execute('''
                UPDATE items
                SET status = ?, title = COALESCE(NULLIF(?, ''), title), file_path = ?, text_path = ?,
                    file_size = ?, char_count = ?, num_pages = ?, error = ?, updated_at = datetime('now')
                WHERE id = ?
            ''', (res['status'], res.get('title', ''), res['file_path'], res['text_path'],
                  res['file_size'], res['char_count'], res.get('num_pages', 0), res['error'], item_id))

        conn.commit()

        # In tiến độ định kỳ
        if idx % 10 == 0 or idx == total_pending:
            pct = (idx / total_pending) * 100
            print(f"[{idx}/{total_pending} - {pct:.1f}%] [{item_type.upper()}] Xử lý ID {item_id}: {url[:50]}...", flush=True)

        # Xuất thống kê CSV mỗi 100 lượt
        if idx % 100 == 0:
            export_summary()

        time.sleep(args.delay)

    export_summary()
    conn.close()

    print("\n" + "="*75, flush=True)
    print(f"HOÀN THÀNH QUÁ TRÌNH CRAWL TOÀN DIỆN!", flush=True)
    print(f"Toàn bộ dữ liệu được lưu trữ tại: {OUTPUT_ROOT}", flush=True)
    print(f"  - Nội dung các trang web: {PAGES_DIR}", flush=True)
    print(f"  - Toàn bộ file PDF gốc : {PDFS_DIR}", flush=True)
    print(f"  - Nội dung text của PDF: {PDF_TEXTS_DIR}", flush=True)
    print(f"  - Báo cáo tổng hợp     : {SUMMARY_CSV}", flush=True)
    print("="*75, flush=True)

if __name__ == '__main__':
    main()
