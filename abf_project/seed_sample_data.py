import psycopg2
from datetime import datetime, timedelta
import random

POOLER_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
POOLER_USER = "postgres.azpvcqpnecljsosamnot"
POOLER_PORT = 6543
PASSWORD = "thanhvuong16@"
DBNAME = "postgres"

SAMPLE_DATA = [
    ("tiktok", "Bào Thẻ thông minh", "User_TikTok_01", "Thẻ VIB Max Card mở online hoàn bao nhiêu % chi tiêu siêu thị vậy mng?", "mua_sam_online", "VIB", "Max Card", "hoi_uu_dai"),
    ("tiktok", "Bào Thẻ thông minh", "User_TikTok_02", "Lương 10tr chuyển khoản mở được thẻ tín dụng bên VPBank không ạ?", "sang_ngang_the", "VPBank", "StepUp", "hoi_dieu_kien_mo_the"),
    ("facebook", "Bào Thẻ thông minh Fanpage", "TranVanB", "Thẻ Travel Élite của VIB đi du lịch Hàn Quốc quẹt phí ngoại tệ bao nhiêu nhỉ?", "du_lich", "VIB", "Travel Élite", "hoi_uu_dai"),
    ("facebook", "Bào Thẻ thông minh Fanpage", "NguyenThiC", "Em muốn làm thẻ tín dụng trả góp mua iPhone sang năm ngân hàng nào ưu đãi nhất?", "tra_gop", "Techcombank", "Everyday", "so_sanh_the"),
    ("zalo", "Bào Thẻ Thông Minh Group 1", "Zalo_Hung", "Ai hỗ trợ sang ngang thẻ Techcombank qua VIB Max Card hạn mức 50tr không?", "sang_ngang_the", "VIB", "Max Card", "hoi_dieu_kien_mo_the"),
    ("zalo", "Hỗ trợ mở thẻ tín dụng Group 2", "Zalo_Mai", "Có thẻ nào hoàn tiền 10% mua sắm Shopee Lazada tốt hơn VPBank StepUp không admin?", "mua_sam_online", "VPBank", "StepUp", "so_sanh_the"),
    ("tiktok", "Bào Thẻ thông minh", "User_TikTok_03", "Rút tiền mặt từ thẻ tín dụng phí thấp nhất giờ là thẻ nào các bác?", "rut_tien", "MB", "Hi Collection", "hoi_dieu_kien_mo_the"),
    ("facebook", "Bào Thẻ thông minh Fanpage", "LeHoangD", "Thẻ HSBC Live+ chi tiêu ăn uống được hoàn tiền bao nhiêu k mỗi tháng?", "an_uong", "HSBC", "Live+", "hoi_uu_dai"),
    ("zalo", "Bào Thẻ Thông Minh Group 1", "Zalo_Phuong", "Mình cần tư vấn mở thẻ tín dụng miễn phí thường niên trọn đời!", "mua_sam_online", "VIB", "Financial Free", "hoi_dieu_kien_mo_the"),
    ("zalo", "Hỗ trợ mở thẻ tín dụng Group 2", "Zalo_Kien", "Thẻ VIB Max Card điều kiện mở thế nào ad ơi, inbox mình với!", "mua_sam_online", "VIB", "Max Card", "hoi_dieu_kien_mo_the")
]

VIB_KNOWLEDGE = [
    ("VIB Max Card", "VIB", "uu_dai_hoan_tien", "Thẻ VIB Max Card có ưu đãi hoàn tiền lên tới 15% cho tất cả các giao dịch chi tiêu Mua sắm Online (Shopee, Lazada, Tiki) và Siêu thị (WinMart, Co.opmart). Mức hoàn tiền tối đa 1.000.000 VNĐ/kỳ sao kê."),
    ("VIB Max Card", "VIB", "dieu_kien_mo_the", "Điều kiện mở thẻ VIB Max Card: Độ tuổi từ 22 đến 60 tuổi. Thu nhập chuyển khoản tối thiểu 7.000.000 VNĐ/tháng (hoặc sở hữu hợp đồng bảo hiểm nhân thọ / sang ngang từ thẻ tín dụng ngân hàng khác có hạn mức tối thiểu 30 triệu)."),
    ("VIB Max Card", "VIB", "phi_thuong_nien", "Phí thường niên thẻ VIB Max Card là 699.000 VNĐ/năm. Miễn phí thường niên năm đầu tiên khi đạt tổng chi tiêu tối thiểu 1.000.000 VNĐ trong vòng 30 ngày kể từ ngày kích hoạt thẻ."),
    ("VIB Max Card", "VIB", "uu_dai_tra_gop", "Thẻ VIB Max Card hỗ trợ trả góp 0% lãi suất tại hơn 100+ đối tác liên kết (FPT Shop, Thế Giới Di Động, Điện Máy Xanh) với phí quản lý trả góp chỉ 0.99%/tháng.")
]

def seed_database():
    print("🌱 Đang khởi tạo dữ liệu mẫu (Seed Data) vào Supabase...")
    conn = psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=POOLER_USER,
        password=PASSWORD,
        dbname=DBNAME
    )
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. Seed raw_comments & insights
    start_date = datetime(2026, 7, 1)
    for i in range(25):
        item = random.choice(SAMPLE_DATA)
        platform, group_name, author, content, category, bank, card, intent = item
        created_at = start_date + timedelta(days=random.randint(0, 50), hours=random.randint(0, 23))
        
        cursor.execute("""
            INSERT INTO raw_comments (platform, group_or_page, author, content, comment_created_at, status)
            VALUES (%s, %s, %s, %s, %s, 'processed') RETURNING id;
        """, (platform, group_name, author, content, created_at))
        comment_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO insights (comment_id, spending_category, target_bank, target_card, intent)
            VALUES (%s, %s, %s, %s, %s);
        """, (comment_id, category, bank, card, intent))

    # 2. Seed card_knowledge
    for card_name, bank_name, topic, content in VIB_KNOWLEDGE:
        cursor.execute("""
            INSERT INTO card_knowledge (card_name, bank_name, topic, content)
            VALUES (%s, %s, %s, %s);
        """, (card_name, bank_name, topic, content))

    cursor.close()
    conn.close()
    print("🎉 Nạp thành công dữ liệu mẫu vào 3 bảng: raw_comments, insights, card_knowledge!")

if __name__ == "__main__":
    seed_database()
