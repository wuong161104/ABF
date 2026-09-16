import os
import time
import psycopg2

# Connection details
HOST = "db.azpvcqpnecljsosamnot.supabase.co"
PORT = 5432
USER = "postgres"
PASSWORD = "thanhvuong16@"
DBNAME = "postgres"

# Alternative Pooler host if direct connection is ipv6 only
POOLER_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
POOLER_USER = "postgres.azpvcqpnecljsosamnot"
POOLER_PORT = 6543

def run_schema_migration():
    print("🚀 Đang khởi tạo kết nối PostgreSQL tới Supabase...")
    
    # Read schema.sql
    with open("schema.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()

    conn = None
    # Try Direct Connection first
    try:
        print(f"Connecting to {HOST}:{PORT}...")
        conn = psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            dbname=DBNAME,
            connect_timeout=10
        )
        print("✅ Kết nối trực tiếp thành công!")
    except Exception as e1:
        print(f"⚠️ Kết nối trực tiếp không thành công ({e1}), đang thử kết nối qua Supabase Transaction Pooler...")
        try:
            conn = psycopg2.connect(
                host=POOLER_HOST,
                port=POOLER_PORT,
                user=POOLER_USER,
                password=PASSWORD,
                dbname=DBNAME,
                connect_timeout=10
            )
            print("✅ Kết nối qua Transaction Pooler thành công!")
        except Exception as e2:
            print(f"❌ Không thể kết nối tới Supabase Postgres: {e2}")
            return False

    if conn:
        try:
            conn.autocommit = True
            cursor = conn.cursor()
            print("⚙️ Đang thực thi mã SQL để tạo các bảng (raw_comments, insights, card_knowledge)...")
            cursor.execute(sql_script)
            print("🎉 THÀNH CÔNG! Đã tạo đầy đủ 3 bảng và Vector Extension trên Supabase Database.")
            
            # Verify tables created
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = [row[0] for row in cursor.fetchall()]
            print(f"📋 Danh sách các bảng hiện có trong public schema: {tables}")
            
            cursor.close()
            conn.close()
            return True
        except Exception as err:
            print(f"❌ Lỗi khi thực thi SQL: {err}")
            return False

if __name__ == "__main__":
    run_schema_migration()
