import os
import sys
import json
import argparse
import requests
import psycopg2
from dotenv import load_dotenv

# Load credentials
load_dotenv()

DB_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
DB_PORT = 6543
DB_USER = "postgres.azpvcqpnecljsosamnot"
DB_PASSWORD = "thanhvuong16@"
DB_NAME = "postgres"

def get_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("\n🔑 Không tìm thấy GEMINI_API_KEY trong file .env.")
        key = input("Vui lòng nhập Gemini API Key của bạn (hoặc bấm Enter để bỏ qua): ").strip()
    return key

def get_gemini_embedding(text, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text}]
        }
    }
    r = requests.post(url, json=payload, timeout=10)
    if r.status_code == 200:
        return r.json()["embedding"]["values"]
    else:
        raise Exception(f"Lỗi gọi Gemini API (Status {r.status_code}): {r.text}")

def chunk_text(text, chunk_size=800, overlap=100):
    """Chia văn bản thành các đoạn nhỏ có gối đầu (overlap)"""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += ("\n\n" + para if current_chunk else para)
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Handle paragraphs larger than chunk_size
            if len(para) > chunk_size:
                # hard split para by characters
                start = 0
                while start < len(para):
                    chunks.append(para[start:start+chunk_size])
                    start += (chunk_size - overlap)
                current_chunk = ""
            else:
                current_chunk = para
                
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def import_txt(filepath, api_key, cur):
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
        
    print(f"📖 Đang đọc file văn bản: {filename} ({len(text)} ký tự)...")
    chunks = chunk_text(text)
    print(f"✂️ Đã phân tách thành {len(chunks)} đoạn kiến thức.")
    
    success = 0
    for idx, chunk in enumerate(chunks):
        try:
            print(f"  - Đang sinh vector & nạp đoạn {idx+1}/{len(chunks)}...")
            vector = get_gemini_embedding(chunk, api_key)
            metadata = {
                "source": filename,
                "chunk_index": idx,
                "total_chunks": len(chunks)
            }
            cur.execute(
                "INSERT INTO public.documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                (chunk, json.dumps(metadata), vector)
            )
            success += 1
        except Exception as e:
            print(f"  ❌ Lỗi ở đoạn {idx+1}: {e}")
    return success, len(chunks)

def import_csv(filepath, api_key, cur):
    import csv
    filename = os.path.basename(filepath)
    print(f"📊 Đang đọc file CSV: {filename}...")
    
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
            
    print(f"📋 Tìm thấy {len(rows)} hàng dữ liệu.")
    
    success = 0
    for idx, row in enumerate(rows):
        content = row.get("content") or row.get("text") or ""
        if not content.strip():
            print(f"  ⚠️ Bỏ qua dòng {idx+1} vì trường 'content' rỗng.")
            continue
            
        # Parse metadata column if exists, else construct it
        metadata_str = row.get("metadata")
        metadata = {}
        if metadata_str:
            try:
                metadata = json.loads(metadata_str)
            except:
                metadata = {"raw_metadata": metadata_str}
        
        # Add source info
        metadata["source"] = filename
        for k, v in row.items():
            if k not in ["content", "text", "metadata", "embedding"] and v:
                metadata[k] = v
                
        try:
            print(f"  - Đang sinh vector & nạp dòng {idx+1}/{len(rows)}...")
            vector = get_gemini_embedding(content, api_key)
            cur.execute(
                "INSERT INTO public.documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                (content, json.dumps(metadata), vector)
            )
            success += 1
        except Exception as e:
            print(f"  ❌ Lỗi ở dòng {idx+1}: {e}")
            
    return success, len(rows)

def main():
    parser = argparse.ArgumentParser(description="ABF RAG Ingestion CLI tool")
    parser.add_argument("--file", help="Đường dẫn tới file cần import (.txt hoặc .csv)")
    args = parser.parse_args()
    
    filepath = args.file
    if not filepath:
        filepath = input("Nhập đường dẫn tới file (.txt hoặc .csv): ").strip()
        
    # Remove quotes if dragged and dropped
    filepath = filepath.strip("'\"")
    
    if not os.path.exists(filepath):
        print(f"❌ Không tìm thấy file: {filepath}")
        return
        
    api_key = get_api_key()
    if not api_key:
        print("❌ Không có API Key. Hủy bỏ import.")
        return
        
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in [".txt", ".csv"]:
        print("❌ Định dạng file không được hỗ trợ. Chỉ hỗ trợ file .txt hoặc .csv")
        return
        
    try:
        print("\n🔌 Kết nối tới cơ sở dữ liệu Supabase...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            connect_timeout=15
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        if ext == ".txt":
            success, total = import_txt(filepath, api_key, cur)
        else:
            success, total = import_csv(filepath, api_key, cur)
            
        print(f"\n🎉 THÀNH CÔNG: Đã nạp {success}/{total} đoạn dữ liệu vào RAG Vector Store!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Lỗi hệ thống: {e}")

if __name__ == "__main__":
    main()
