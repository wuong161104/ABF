import os
import sys
import json
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

def run_migration():
    print("=" * 60)
    print("      MIGRATION & RE-INGESTION VECTOR STORAGE (768 Dims)")
    print("=" * 60)
    
    api_key = get_api_key()
    if not api_key:
        print("❌ Không có API Key. Hủy bỏ migration.")
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
        
        # 1. Back up existing documents
        print("📥 Đang sao lưu dữ liệu hiện tại từ bảng documents...")
        cur.execute("SELECT id, content, metadata FROM public.documents ORDER BY id ASC")
        backup = cur.fetchall()
        print(f"✅ Đã sao lưu {len(backup)} bản ghi.")
        
        if len(backup) == 0:
            print("⚠️ Bảng documents trống hoặc không tồn tại. Không có dữ liệu để re-ingest.")
            # We will still proceed to create the table structure
            
        # 2. Re-create table structure
        print("\n🗑️ Đang xóa cấu trúc bảng cũ...")
        cur.execute("DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb);")
        cur.execute("DROP TABLE IF EXISTS public.documents CASCADE;")
        
        print("🏗️ Đang tạo lại bảng documents với vector(768) cho Gemini...")
        cur.execute("""
            CREATE TABLE public.documents (
                id bigserial PRIMARY KEY,
                content text,
                metadata jsonb,
                embedding vector(768)
            );
        """)
        
        print("⚙️ Đang tạo lại function match_documents...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION public.match_documents(
                query_embedding vector(768), 
                match_count int, 
                filter jsonb DEFAULT '{}'::jsonb
            )
            RETURNS TABLE(
                id bigint, 
                content text, 
                metadata jsonb, 
                similarity float
            )
            LANGUAGE plpgsql
            AS $$
            #variable_conflict use_column
            BEGIN
              RETURN QUERY
              SELECT
                documents.id,
                documents.content,
                documents.metadata,
                1 - (documents.embedding <=> query_embedding) AS similarity
              FROM public.documents
              WHERE documents.metadata @> filter
              ORDER BY documents.embedding <=> query_embedding
              LIMIT match_count;
            END;
            $$;
        """)
        
        # 3. Generate embeddings and ingest data
        if len(backup) > 0:
            print(f"\n🧠 Bắt đầu sinh vector 768 chiều từ Gemini API cho {len(backup)} tài liệu...")
            success_count = 0
            for row in backup:
                doc_id, content, metadata = row
                if not content or not content.strip():
                    continue
                try:
                    print(f"  - Đang sinh vector cho tài liệu #{doc_id} ({content[:30].strip()}...)...")
                    vector = get_gemini_embedding(content, api_key)
                    
                    cur.execute(
                        "INSERT INTO public.documents (id, content, metadata, embedding) VALUES (%s, %s, %s, %s)",
                        (doc_id, content, json.dumps(metadata), vector)
                    )
                    success_count += 1
                except Exception as e:
                    print(f"  ❌ Lỗi khi re-ingest tài liệu #{doc_id}: {e}")
                    
            print(f"✅ Hoàn thành sinh vector! Đã nạp thành công {success_count}/{len(backup)} tài liệu.")

        # 4. Create HNSW index
        print("\n⚡ Đang tạo chỉ mục HNSW (idx_documents_embedding) tối ưu hóa truy vấn...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_embedding 
            ON public.documents USING hnsw (embedding vector_cosine_ops);
        """)
        print("✅ Đã kích hoạt chỉ mục HNSW thành công!")

        # Verify indexes
        cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents'")
        print("\n=== CÁC CHỈ MỤC HIỆN TẠI TRÊN BẢNG DOCUMENTS ===")
        for idx in cur.fetchall():
            print(f"- {idx[0]}: {idx[1]}")
            
        cur.close()
        conn.close()
        print("\n🎉 MIGRATION THÀNH CÔNG RỰC RỠ!")
        
    except Exception as e:
        print(f"\n❌ Lỗi hệ thống trong quá trình migration: {e}")

if __name__ == "__main__":
    run_migration()
