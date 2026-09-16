"""
Script Dọn Dẹp Dữ Liệu Mẫu / Mock Data Trong Supabase Database (ABF Solution)
Xóa tất cả các comment giả lập cũ để cơ sở dữ liệu chỉ chứa dữ liệu CÀO THỰC TẾ.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

POOLER_HOST = os.getenv("POOLER_HOST", "aws-0-ap-northeast-2.pooler.supabase.com")
POOLER_USER = os.getenv("POOLER_USER", "postgres.azpvcqpnecljsosamnot")
POOLER_PORT = int(os.getenv("POOLER_PORT", "6543"))
PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "thanhvuong16@")
DBNAME = os.getenv("DBNAME", "postgres")

def clean_mock_comments():
    print("🧹 Đang tiến hành xóa các dữ liệu mẫu (Mock Comments) khỏi Supabase DB...")
    try:
        conn = psycopg2.connect(
            host=POOLER_HOST, port=POOLER_PORT, user=POOLER_USER,
            password=PASSWORD, dbname=DBNAME, connect_timeout=10
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Delete mock rows where author matches mock patterns or source_url is null
        cursor.execute("""
            DELETE FROM insights 
            WHERE comment_id IN (
                SELECT id FROM raw_comments 
                WHERE author LIKE 'TikTok_User_%' 
                   OR author LIKE 'User_TikTok_%' 
                   OR author LIKE 'Zalo_%'
                   OR source_url IS NULL
            );
        """)
        
        cursor.execute("""
            DELETE FROM raw_comments 
            WHERE author LIKE 'TikTok_User_%' 
               OR author LIKE 'User_TikTok_%' 
               OR author LIKE 'Zalo_%'
               OR source_url IS NULL;
        """)
        deleted_count = cursor.rowcount
        
        cursor.close()
        conn.close()
        print(f"✅ Đã dọn dẹp xong! Đã xóa {deleted_count} bản ghi dữ liệu mẫu khỏi Supabase.")
    except Exception as e:
        print(f"❌ Lỗi khi xóa dữ liệu mẫu: {e}")

if __name__ == "__main__":
    clean_mock_comments()
