import psycopg2

POOLER_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
POOLER_USER = "postgres.azpvcqpnecljsosamnot"
POOLER_PORT = 6543
PASSWORD = "thanhvuong16@"
DBNAME = "postgres"

def alter_schema():
    print("🛠 Đang bổ sung các cột `source_url` và `post_likes` vào Supabase DB...")
    conn = psycopg2.connect(
        host=POOLER_HOST, port=POOLER_PORT, user=POOLER_USER,
        password=PASSWORD, dbname=DBNAME
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    cursor.execute("""
        ALTER TABLE raw_comments 
        ADD COLUMN IF NOT EXISTS source_url TEXT,
        ADD COLUMN IF NOT EXISTS post_likes VARCHAR(50);
    """)
    print("✅ Đã bổ sung thành công 2 cột `source_url` (Link bài đăng) và `post_likes` (Số lượng tym) vào Supabase DB!")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    alter_schema()
