import os
import sys
import json
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database credentials
DB_HOST = os.getenv("DB_HOST", "aws-0-ap-northeast-2.pooler.supabase.com")
DB_PORT = int(os.getenv("DB_PORT", "6543"))
DB_USER = os.getenv("DB_USER", "postgres.azpvcqpnecljsosamnot")
DB_PASSWORD = os.getenv("DB_PASSWORD", "thanhvuong16@")
DB_NAME = os.getenv("DB_NAME", "postgres")

# Gemini API credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = "models/gemini-embedding-001"

def test_db_connection():
    """Verify DB connection is active and valid."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            connect_timeout=10
        )
        conn.close()
        return True
    except Exception as e:
        print(f"❌ [DB Connection Error]: {e}")
        return False

def get_gemini_embedding(text, api_key, max_retries=5):
    """Retrieve 3072-dimensional vector embedding from Google Gemini with retry logic."""
    model_path = EMBEDDING_MODEL if EMBEDDING_MODEL.startswith("models/") else f"models/{EMBEDDING_MODEL}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:embedContent?key={api_key}"
    payload = {
        "model": model_path,
        "content": {
            "parts": [{"text": text}]
        }
    }
    
    retries = 0
    backoff = 2
    while retries < max_retries:
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                return data["embedding"]["values"]
            elif r.status_code == 429:
                print(f"  ⚠️ Gặp lỗi giới hạn Rate Limit (429). Đang nghỉ {backoff}s trước khi thử lại...")
                time.sleep(backoff)
                retries += 1
                backoff *= 2
            else:
                # Handle general errors (e.g. invalid text)
                raise Exception(f"Lỗi API (Status {r.status_code}): {r.text}")
        except Exception as e:
            print(f"  ⚠️ Lỗi kết nối/gọi API: {e}. Thử lại sau {backoff}s...")
            time.sleep(backoff)
            retries += 1
            backoff *= 2
            
    raise Exception("❌ Đã vượt quá số lần thử lại tối đa. Không thể lấy vector embedding từ Gemini.")

def split_text_recursive(text, chunk_size=600, overlap=100, separators=["\n\n", "\n", " ", ""]):
    """Split text recursively into chunks based on characters. Emulates LangChain RecursiveCharacterTextSplitter."""
    if len(text) <= chunk_size:
        return [text]
        
    separator = ""
    for sep in separators:
        if sep == "":
            separator = sep
            break
        if sep in text:
            separator = sep
            break
            
    if separator != "":
        parts = text.split(separator)
    else:
        parts = list(text)
        
    chunks = []
    current_chunk = []
    current_len = 0
    
    for part in parts:
        part_len = len(part) + (len(separator) if current_len > 0 else 0)
        if current_len + part_len <= chunk_size:
            current_chunk.append(part)
            current_len += part_len
        else:
            if current_chunk:
                chunks.append(separator.join(current_chunk))
            
            # Simple overlap rollback
            new_chunk = []
            new_len = 0
            for p in reversed(current_chunk):
                p_len = len(p) + (len(separator) if new_len > 0 else 0)
                if new_len + p_len <= overlap:
                    new_chunk.insert(0, p)
                    new_len += p_len
                else:
                    break
            current_chunk = new_chunk
            current_chunk.append(part)
            current_len = sum(len(p) for p in current_chunk) + len(separator) * (len(current_chunk) - 1)
            
    if current_chunk:
        chunks.append(separator.join(current_chunk))
        
    # Recursively split any chunk that is still too large
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size:
            next_seps = separators[separators.index(separator) + 1:] if separator in separators else []
            if next_seps:
                final_chunks.extend(split_text_recursive(chunk, chunk_size, overlap, next_seps))
            else:
                # Force cut split if no separators left
                i = 0
                while i < len(chunk):
                    final_chunks.append(chunk[i : i + chunk_size])
                    i += chunk_size - overlap
        else:
            final_chunks.append(chunk)
            
    # Clean up empty or whitespace-only chunks
    return [c.strip() for c in final_chunks if c.strip()]

def run_rag_ingestion(reset=False):
    print("=" * 60)
    print("🤖  QUY TRÌNH NẠP DỮ LIỆU RAG VÀO VECTOR STORE (SUPABASE)")
    print("=" * 60)
    
    if not test_db_connection():
        print("❌ Không thể kết nối DB. Vui lòng kiểm tra cấu hình trong .env")
        return
        
    if not GEMINI_API_KEY:
        print("❌ Không tìm thấy GEMINI_API_KEY trong hệ thống!")
        return

    print(f"🔑 Gemini Key: {GEMINI_API_KEY[:6]}...{GEMINI_API_KEY[-6:]}")
    print(f"🧠 Model Embedding: {EMBEDDING_MODEL} (3072 dimensions)")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Reset database if selected
        if reset:
            print("\n🚨 [RESET MODE] Đang xóa sạch dữ liệu cũ trong bảng public.documents...")
            cur.execute("TRUNCATE TABLE public.documents RESTART IDENTITY;")
            print("✅ Đã làm sạch bảng public.documents.")
            processed_crawled_ids = set()
        else:
            # Check already processed crawled_ids to run incrementally
            print("\n🔍 Đang lấy danh sách các crawled_id đã được nạp RAG trước đó...")
            cur.execute("""
                SELECT DISTINCT metadata->>'crawled_id' as id 
                FROM public.documents 
                WHERE metadata->>'crawled_id' IS NOT NULL;
            """)
            processed_crawled_ids = set()
            for row in cur.fetchall():
                val = row['id']
                if val:
                    # Hỗ trợ trường hợp ID dạng danh sách dấu phẩy "1, 2, 3" hoặc chuỗi đơn "1"
                    if ',' in val:
                        for part in val.split(','):
                            try:
                                processed_crawled_ids.add(int(part.strip()))
                            except ValueError:
                                pass
                    else:
                        try:
                            processed_crawled_ids.add(int(val.strip()))
                        except ValueError:
                            pass
            print(f"ℹ️ Đã tìm thấy {len(processed_crawled_ids)} bài viết (ID thô) đã được xử lý RAG trước đó.")

        # 2. Fetch Crawled Web Data
        print("\n📥 Đang tải dữ liệu thô từ bảng crawled_web_data...")
        cur.execute("""
            SELECT id, source_url, page_title, section_title, full_text 
            FROM public.crawled_web_data 
            WHERE status = 'SUCCESS'
            ORDER BY id ASC;
        """)
        crawled_rows = cur.fetchall()
        print(f"📊 Tìm thấy tổng cộng {len(crawled_rows)} bản ghi đã crawl thành công.")
        
        # Filter rows
        rows_to_process = []
        for row in crawled_rows:
            # Skip if already processed in incremental mode
            if not reset and row['id'] in processed_crawled_ids:
                continue
                
            raw_text = (row['full_text'] or '').strip()
            # Ignore empty or too short text (less than 15 chars)
            if len(raw_text) < 15:
                continue
                
            rows_to_process.append(row)
            
        print(f"👉 Số lượng bản ghi mới cần xử lý RAG: {len(rows_to_process)}")
        
        if not rows_to_process:
            print("🎉 Không có dữ liệu mới nào cần nạp RAG. Quy trình hoàn tất!")
            cur.close()
            conn.close()
            return
            
        # 3. Process each record
        total_chunks_inserted = 0
        start_time = time.time()
        
        for idx, row in enumerate(rows_to_process, start=1):
            row_id = row['id']
            url = row['source_url']
            title = row['page_title'] or ''
            section = row['section_title'] or ''
            full_text = row['full_text'].strip()
            
            # Combine content exactly like the n8n logic
            combined_text = ""
            if title:
                combined_text += f"Tiêu đề: {title}\n"
            if section:
                combined_text += f"Mục: {section}\n\n"
            combined_text += full_text
            
            # Split text recursively (size 1000, overlap 150)
            chunks = split_text_recursive(combined_text, chunk_size=1000, overlap=150)
            print(f"\n📄 [{idx}/{len(rows_to_process)}] Xử lý bài viết #{row_id}: '{title[:40]}...'")
            print(f"   -> Cắt thành {len(chunks)} đoạn nhỏ.")
            
            for chunk_idx, chunk in enumerate(chunks, start=1):
                try:
                    # Sleep 4.0 seconds to safely adhere to Google Gemini Free Tier 15 RPM limit
                    time.sleep(4.0)
                    vector = get_gemini_embedding(chunk, GEMINI_API_KEY)
                    
                    # Prepare metadata
                    metadata = {
                        "source": url or "crawled_web",
                        "title": title,
                        "section": section,
                        "crawled_id": row_id
                    }
                    
                    # Insert chunk to database
                    cur.execute(
                        "INSERT INTO public.documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                        (chunk, json.dumps(metadata), vector)
                    )
                    total_chunks_inserted += 1
                    print(f"   ✅ Đã nạp đoạn {chunk_idx}/{len(chunks)} vào Supabase Vector Store")
                except Exception as chunk_err:
                    print(f"   ❌ Lỗi khi nạp đoạn {chunk_idx} của bài viết #{row_id}: {chunk_err}")
                    
        end_time = time.time()
        elapsed = end_time - start_time
        print("\n" + "=" * 60)
        print("🎉 HOÀN THÀNH QUY TRÌNH NẠP RAG TRÊN PYTHON!")
        print(f"⏱️ Tổng thời gian xử lý: {elapsed:.2f} giây")
        print(f"✨ Số đoạn chunks đã được thêm vào bảng documents: {total_chunks_inserted}")
        print("=" * 60)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Lỗi hệ thống trong quá trình xử lý RAG: {e}")

if __name__ == "__main__":
    # Check if reset argument is passed
    reset_db = False
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--reset", "-r", "reset"]:
        reset_db = True
        
    run_rag_ingestion(reset=reset_db)
