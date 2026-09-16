import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Supabase Connection
POOLER_HOST = os.getenv("POOLER_HOST", "aws-0-ap-northeast-2.pooler.supabase.com")
POOLER_USER = os.getenv("POOLER_USER", "postgres.azpvcqpnecljsosamnot")
POOLER_PORT = int(os.getenv("POOLER_PORT", "6543"))
PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "thanhvuong16@")
DBNAME = os.getenv("DBNAME", "postgres")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.crawled_web_data (
    id BIGSERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    page_title TEXT,
    content_type TEXT DEFAULT 'main_page',
    section_title TEXT,
    full_text TEXT,
    tables_json JSONB DEFAULT '[]'::jsonb,
    images_json JSONB DEFAULT '[]'::jsonb,
    raw_metadata JSONB DEFAULT '{}'::jsonb,
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'SUCCESS'
);

-- Index for fast lookup by source_url and content_type
CREATE INDEX IF NOT EXISTS idx_crawled_web_data_url ON public.crawled_web_data(source_url);
CREATE INDEX IF NOT EXISTS idx_crawled_web_data_type ON public.crawled_web_data(content_type);
"""

def create_crawled_web_data_table():
    print("🚀 Đang kết nối tới Supabase để tạo bảng public.crawled_web_data...")
    conn = None
    try:
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
        cursor.execute(CREATE_TABLE_SQL)
        print("✅ [SUCCESS] Bảng 'crawled_web_data' đã được tạo thành công trên Supabase DB!")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ [ERROR] Không thể tạo bảng trên Supabase: {e}")
        return False

if __name__ == "__main__":
    create_crawled_web_data_table()
