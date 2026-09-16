"""
Module Nạp Dữ Liệu Knowledge Base & Vector RAG (Bài toán 2) - ABF Test
Chạy ingestion cho chính sách dòng thẻ VIB Max Card & hỗ trợ truy vấn RAG Search.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import openai

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-supabase-url.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-supabase-service-role-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Dữ liệu chính sách dòng thẻ VIB Max Card (Demo Data)
VIB_MAX_CARD_KNOWLEDGE = [
    {
        "card_name": "VIB Max Card",
        "bank_name": "VIB",
        "topic": "uu_dai_hoan_tien",
        "content": "Thẻ VIB Max Card có ưu đãi hoàn tiền lên tới 15% cho tất cả các giao dịch chi tiêu Mua sắm Online (Shopee, Lazada, Tiki) và Siêu thị (WinMart, Co.opmart). Mức hoàn tiền tối đa 1.000.000 VNĐ/kỳ sao kê."
    },
    {
        "card_name": "VIB Max Card",
        "bank_name": "VIB",
        "topic": "dieu_kien_mo_the",
        "content": "Điều kiện mở thẻ VIB Max Card: Độ tuổi từ 22 đến 60 tuổi. Thu nhập chuyển khoản tối thiểu 7.000.000 VNĐ/tháng (hoặc sở hữu hợp đồng bảo hiểm nhân thọ / sang ngang từ thẻ tín dụng ngân hàng khác có hạn mức tối thiểu 30 triệu)."
    },
    {
        "card_name": "VIB Max Card",
        "bank_name": "VIB",
        "topic": "phi_thuong_nien",
        "content": "Phí thường niên thẻ VIB Max Card là 699.000 VNĐ/năm. Miễn phí thường niên năm đầu tiên khi đạt tổng chi tiêu tối thiểu 1.000.000 VNĐ trong vòng 30 ngày kể từ ngày kích hoạt thẻ."
    },
    {
        "card_name": "VIB Max Card",
        "bank_name": "VIB",
        "topic": "uu_dai_tra_gop",
        "content": "Thẻ VIB Max Card hỗ trợ trả góp 0% lãi suất tại hơn 100+ đối tác liên kết (FPT Shop, Thế Giới Di Động, Điện Máy Xanh) với phí quản lý trả góp chỉ 0.99%/tháng."
    }
]

def get_embedding(text: str):
    """Tạo vector embedding cho đoạn văn bản"""
    if not OPENAI_API_KEY:
        # Vector giả định nếu chưa có API Key
        return [0.01 * (i % 10) for i in range(1536)]
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Lỗi khi tạo embedding: {e}")
        return [0.0] * 1536

def ingest_vib_max_card_knowledge():
    """Nạp dữ liệu chính sách VIB Max Card vào Supabase `card_knowledge`"""
    print("📚 Đang nạp Knowledge Base chính sách VIB Max Card vào Supabase...")
    for doc in VIB_MAX_CARD_KNOWLEDGE:
        vector = get_embedding(doc["content"])
        supabase.table("card_knowledge").insert({
            "card_name": doc["card_name"],
            "bank_name": doc["bank_name"],
            "topic": doc["topic"],
            "content": doc["content"],
            "embedding": vector
        }).execute()
    print("✅ Hoàn thành nạp Knowledge Base!")

def query_rag_knowledge(query_text: str, top_k: int = 3):
    """Tìm kiếm đoạn văn bản chính sách liên quan nhất dựa trên vector search"""
    query_vector = get_embedding(query_text)
    try:
        res = supabase.rpc("match_card_knowledge", {
            "query_embedding": query_vector,
            "match_threshold": 0.3,
            "match_count": top_k
        }).execute()
        return res.data
    except Exception as e:
        print(f"Lỗi khi truy vấn RAG Vector: {e}")
        return []

if __name__ == "__main__":
    ingest_vib_max_card_knowledge()
    
    # Test RAG Search
    test_query = "Thu nhập bao nhiêu thì mở được thẻ VIB Max Card?"
    print(f"\n🔍 Test RAG với câu hỏi: '{test_query}'")
    results = query_rag_knowledge(test_query)
    for r in results:
        print(f"- [Độ tương đồng: {r.get('similarity', 0):.2f}] {r.get('content')}")
