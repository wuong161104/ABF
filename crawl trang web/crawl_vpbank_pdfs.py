"""
VPBank PDF Crawler & Text Content Extractor (Tối ưu hóa chống Rate-limit WAF)
------------------------------------------------------------------------------
Tính năng:
1. Tự động đọc lại danh sách 2.417 file PDF đã thu thập trong checkpoint.json (không cần quét lại).
2. Tải từng file PDF kèm độ trễ hợp lý (Rate limiting) tránh kích hoạt Incapsula WAF.
3. Tự động chờ (Backoff wait) nếu phát hiện WAF chặn tạm thời (HTTP 403 / 429).
4. Tải file về thư mục D:\\VPBank_Crawl_Data\\pdfs\\
5. Trích xuất toàn bộ nội dung văn bản (Text content) sang D:\\VPBank_Crawl_Data\\texts\\
6. Cập nhật liên tục tiến độ vào D:\\VPBank_Crawl_Data\\metadata.csv & metadata.json
7. Có thể dừng hoặc chạy lại bất cứ lúc nào (tự động bỏ qua các file đã tải thành công).
"""

import os
import sys
import re
import json
import csv
import time
import urllib.parse
from pathlib import Path

import requests
import pypdf

# Cấu hình đường dẫn lưu trữ trên ổ D
BASE_OUTPUT_DIR = Path(r"D:\VPBank_Crawl_Data")
PDF_DIR = BASE_OUTPUT_DIR / "pdfs"
TEXT_DIR = BASE_OUTPUT_DIR / "texts"
METADATA_JSON = BASE_OUTPUT_DIR / "metadata.json"
METADATA_CSV = BASE_OUTPUT_DIR / "metadata.csv"
CHECKPOINT_FILE = BASE_OUTPUT_DIR / "checkpoint.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/pdf,*/*;q=0.8',
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

def setup_directories():
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name: str, max_length: int = 120) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > max_length:
        clean = clean[:max_length]
    return clean

def extract_text_from_pdf(pdf_filepath: Path, txt_filepath: Path, doc_info: dict) -> tuple[int, int]:
    try:
        reader = pypdf.PdfReader(str(pdf_filepath))
        num_pages = len(reader.pages)
        full_text = []

        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ''
                if page_text.strip():
                    full_text.append(f"--- TRANG {page_idx} ---\n{page_text}\n")
            except Exception:
                full_text.append(f"--- TRANG {page_idx} [Lỗi đọc text] ---\n")

        extracted_str = "\n".join(full_text)
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(f"TIÊU ĐỀ: {doc_info.get('title', '')}\n")
            f.write(f"NGUỒN URL: {doc_info.get('url', '')}\n")
            f.write(f"SỐ TRANG: {num_pages}\n")
            f.write(f"{'='*60}\n\n")
            f.write(extracted_str)

        return num_pages, len(extracted_str)
    except Exception as e:
        return 0, 0

def load_existing_metadata() -> dict[str, dict]:
    """Tải lịch sử crawl nếu có để kiểm tra trạng thái từng URL."""
    meta_dict = {}
    if METADATA_JSON.exists():
        try:
            with open(METADATA_JSON, 'r', encoding='utf-8') as f:
                items = json.load(f)
                for it in items:
                    meta_dict[it['url']] = it
        except Exception:
            pass
    return meta_dict

def save_current_metadata(records: list[dict]):
    with open(METADATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    if records:
        fieldnames = ['id', 'title', 'category', 'status', 'num_pages', 'char_count', 'file_size_bytes', 'url', 'pdf_filename', 'pdf_path', 'text_path', 'source', 'error']
        with open(METADATA_CSV, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)

def main():
    print("="*70)
    print("VPBANK PDF CRAWLER & TEXT CONTENT EXTRACTOR")
    print("="*70)
    setup_directories()

    if not CHECKPOINT_FILE.exists():
        print("[!] Không tìm thấy file checkpoint.json. Vui lòng chạy bộ quét ban đầu.")
        return

    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
        all_docs = json.load(f)

    total_docs = len(all_docs)
    print(f"[+] Đã tải danh sách từ checkpoint: {total_docs} file PDF cần xử lý.")

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    consecutive_403 = 0
    delay_between_requests = 0.8  # Giây để tránh spam WAF

    print(f"[*] Bắt đầu tải và bóc tách nội dung vào thư mục: {BASE_OUTPUT_DIR}")

    for idx, doc in enumerate(all_docs, start=1):
        url = doc['url'].strip()
        raw_name = Path(urllib.parse.urlparse(url).path).name
        if not raw_name.lower().endswith('.pdf'):
            raw_name += '.pdf'

        base_filename = f"{idx:04d}_{sanitize_filename(raw_name)}"
        pdf_filepath = PDF_DIR / base_filename
        txt_filepath = TEXT_DIR / f"{base_filename[:-4]}.txt"

        record = {
            'id': idx,
            'title': doc.get('title', ''),
            'url': url,
            'source': doc.get('source', ''),
            'category': doc.get('category_title') or doc.get('category_path', ''),
            'pdf_filename': base_filename,
            'pdf_path': str(pdf_filepath),
            'text_path': str(txt_filepath),
            'file_size_bytes': 0,
            'num_pages': 0,
            'char_count': 0,
            'status': 'pending',
            'error': ''
        }

        # 1. Kiểm tra nếu file PDF và TXT đã tải và trích xuất hợp lệ trước đó
        if pdf_filepath.exists() and pdf_filepath.stat().st_size > 1000 and txt_filepath.exists() and txt_filepath.stat().st_size > 50:
            record['file_size_bytes'] = pdf_filepath.stat().st_size
            try:
                reader = pypdf.PdfReader(str(pdf_filepath))
                record['num_pages'] = len(reader.pages)
            except Exception:
                pass
            record['char_count'] = txt_filepath.stat().st_size
            record['status'] = 'completed'
            results.append(record)
            continue

        # 2. Tải PDF với cơ chế xử lý WAF / Backoff
        download_success = False
        retry_count = 0

        while not download_success and retry_count < 3:
            try:
                # Đảm bảo mã hóa URL hợp lệ
                parts = urllib.parse.urlsplit(url)
                encoded_path = urllib.parse.quote(parts.path)
                safe_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))

                resp = session.get(safe_url, timeout=25, stream=True)
                
                # Kiểm tra WAF block (403 hoặc 429)
                if resp.status_code in [403, 429]:
                    consecutive_403 += 1
                    wait_time = 30 * min(consecutive_403, 4)
                    print(f"\n[!] WAF tạm thời giới hạn tần suất (HTTP {resp.status_code}). Đang tạm dừng {wait_time}s...")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                elif resp.status_code == 200:
                    consecutive_403 = 0
                    # Ghi file PDF
                    with open(pdf_filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                    
                    # Kiểm tra xem file có phải là HTML do challenge trả về hay PDF thật
                    if pdf_filepath.stat().st_size < 1500:
                        with open(pdf_filepath, 'rb') as f:
                            header = f.read(10)
                        if not header.startswith(b'%PDF'):
                            pdf_filepath.unlink(missing_ok=True)
                            print(f"\n[!] Nhận nội dung không phải PDF hợp lệ tại file {idx}. Tạm dừng 15s...")
                            time.sleep(15)
                            retry_count += 1
                            continue

                    record['file_size_bytes'] = pdf_filepath.stat().st_size
                    download_success = True
                else:
                    record['status'] = f'failed_http_{resp.status_code}'
                    break

            except Exception as e:
                record['error'] = str(e)
                retry_count += 1
                time.sleep(3)

        if download_success:
            # 3. Trích xuất Text ngay sau khi tải
            num_pages, chars = extract_text_from_pdf(pdf_filepath, txt_filepath, doc)
            record['num_pages'] = num_pages
            record['char_count'] = chars
            record['status'] = 'completed'
        elif record['status'] == 'pending':
            record['status'] = 'download_failed'

        results.append(record)

        # Cập nhật thông tin tiến độ
        if idx % 10 == 0 or idx == total_docs:
            save_current_metadata(results)
            completed_so_far = sum(1 for r in results if r['status'] == 'completed')
            pct = (idx / total_docs) * 100
            print(f"[{idx}/{total_docs} - {pct:.1f}%] Hoàn thành: {completed_so_far} file | Đang xử lý: {record['title'][:40]}...", flush=True)

        time.sleep(delay_between_requests)

    save_current_metadata(results)
    print("\n" + "="*70, flush=True)
    print("HOÀN THÀNH TẤT CẢ QUÁ TRÌNH TẢI VÀ TRÍCH XUẤT NỘI DUNG PDF!", flush=True)
    print("="*70, flush=True)

if __name__ == '__main__':
    main()
