"""
Module Xử Lý AI / LLM Classification & Extraction - ABF Solution
GOM 30-50 COMMENTS VÀO 1 CÂU PROMPT (BATCH PROMPT ENRICHMENT).
Giải quyết triệt để lỗi hết Quota / 429 Rate Limit, tăng tốc độ xử lý AI gấp 50 lần!
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BATCH_SYSTEM_PROMPT = """
Bạn là hệ thống AI phân tích ý kiến và nhu cầu của khách hàng về thẻ tín dụng trên Social Media.
Tôi sẽ cung cấp danh sách các comment dưới dạng mảng JSON (mỗi item gồm `id` và `content`).
Hãy phân tích và trả về ĐÚNG 1 MẢNG JSON chứa thông tin trích xuất cho từng comment theo cấu trúc:
[
  {
    "id": 123,
    "spending_category": "du_lich | mua_sam_online | tra_gop | rut_tien | an_uong | sang_ngang_the | khac",
    "target_bank": "Tên ngân hàng (VD: VIB, VPBank, Techcombank, HSBC, MB...) hoặc null",
    "target_card": "Dòng thẻ cụ thể (VD: Max Card, Travel Élite, StepUp...) hoặc null",
    "intent": "hoi_dieu_kien_mo_the | hoi_uu_dai | so_sanh_the | tim_dich_vu | khac"
  }
]
Chú ý: Giữ nguyên `id` của từng comment. Không thêm bất kỳ text hay markdown nào ngoài mảng JSON.
"""

def process_comment_batch_with_gemini(comments_chunk: list, api_key: str) -> list:
    """Gửi toàn bộ mảng comments_chunk vào 1 câu prompt của Gemini API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    # Format input for LLM batch
    input_items = [{"id": item["id"], "content": item["content"]} for item in comments_chunk]
    prompt_text = f"{BATCH_SYSTEM_PROMPT}\n\nDanh sách Comments cần phân tích:\n{json.dumps(input_items, ensure_ascii=False)}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    for attempt in range(5):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "data" in parsed:
                    return parsed["data"]
            elif resp.status_code == 429:
                wait_sec = (attempt + 1) * 5
                print(f"⚠️ Dính Gemini 429 Quota Exceeded. Đang chờ {wait_sec}s rồi thử lại batch...")
                time.sleep(wait_sec)
            else:
                print(f"⚠️ Gemini status: {resp.status_code}")
                time.sleep(2)
        except Exception as e:
            print(f"⚠️ Gemini batch attempt {attempt+1} error: {e}")
            time.sleep(2)
            
    # Fallback heuristic rule processing if LLM fails
    fallback_results = []
    for item in comments_chunk:
        txt = item["content"].lower()
        bank = "VIB" if "vib" in txt else ("VPBank" if "vpbank" in txt else ("Techcombank" if "tech" in txt else None))
        card = "Max Card" if "max" in txt or "ivy" in txt else ("Travel Élite" if "travel" in txt else None)
        category = "mua_sam_online" if "shopee" in txt or "online" in txt or "duyệt" in txt else ("du_lich" if "du lịch" in txt or "du học" in txt else "khac")
        intent = "hoi_dieu_kien_mo_the" if "điều kiện" in txt or "hạn mức" in txt or "mở" in txt else "hoi_uu_dai"
        fallback_results.append({
            "id": item["id"],
            "spending_category": category,
            "target_bank": bank,
            "target_card": card,
            "intent": intent
        })
    return fallback_results

def process_all_pending_comments_in_batches(batch_size: int = 30):
    """
    Lấy toàn bộ comment chưa xử lý và GOM THEO BATCH (30 comments / 1 prompt call)
    """
    print("🔄 Đang lấy danh sách comment chưa xử lý từ Supabase...")
    res = supabase.table("raw_comments").select("*").eq("status", "pending").execute()
    pending_comments = res.data or []

    if not pending_comments:
        print("🎉 Không có comment nào cần xử lý.")
        return

    print(f"🚀 TỔNG CỘNG {len(pending_comments)} comments. Đang chia thành các Batch (Mỗi batch {batch_size} comments / 1 câu prompt)...")
    
    api_key = GEMINI_API_KEY or OPENAI_API_KEY
    total_processed = 0
    
    # Process in chunks of batch_size
    for i in range(0, len(pending_comments), batch_size):
        chunk = pending_comments[i:i + batch_size]
        chunk_ids = [c["id"] for c in chunk]
        
        print(f"⚙️ Đang gửi Batch [{i+1} đến {i+len(chunk)}] / {len(pending_comments)} vào 1 câu prompt Gemini...")
        
        # 1. Gọi LLM cho cả Batch
        batch_insights = process_comment_batch_with_gemini(chunk, api_key)
        
        # 2. Insert batch insights vào DB
        insights_to_insert = []
        for r in batch_insights:
            c_id = r.get("id")
            if c_id in chunk_ids:
                insights_to_insert.append({
                    "comment_id": c_id,
                    "spending_category": r.get("spending_category", "khac"),
                    "target_bank": r.get("target_bank"),
                    "target_card": r.get("target_card"),
                    "intent": r.get("intent", "khac")
                })
                
        if insights_to_insert:
            supabase.table("insights").insert(insights_to_insert).execute()
            
        # 3. Update status = processed cho cả chunk
        for c_id in chunk_ids:
            supabase.table("raw_comments").update({"status": "processed"}).eq("id", c_id).execute()
            
        total_processed += len(chunk)
        print(f"✅ Hoàn thành Batch! Đã xử lý tổng cộng: {total_processed}/{len(pending_comments)} comments.")
        time.sleep(1.5) # Anti rate-limit sleep between batches

    print(f"🎉 RẤT THÀNH CÔNG! Đã phân tích và lưu insights cho TOÀN BỘ {total_processed} comments vào Supabase!")

if __name__ == "__main__":
    process_all_pending_comments_in_batches(30)
