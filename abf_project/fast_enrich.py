# -*- coding: utf-8 -*-
import requests
import json
from typing import Dict, Any, List

SUPABASE_URL = "https://azpvcqpnecljsosamnot.supabase.co"
SUPABASE_KEY = "sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def extract_financial_insights(content: str) -> Dict[str, Any]:
    txt = content.lower() if content else ""
    
    # Bank
    bank = "-"
    if "vib" in txt:
        bank = "VIB"
    elif "vpbank" in txt or "vp bank" in txt or "vp" in txt:
        bank = "VPBank"
    elif "techcombank" in txt or "tech" in txt:
        bank = "Techcombank"
    elif "mb bank" in txt or "mb" in txt or "mbbank" in txt:
        bank = "MB Bank"
    elif "acb" in txt:
        bank = "ACB"
    elif "msb" in txt or "hàng hải" in txt:
        bank = "MSB"
    elif "hsbc" in txt:
        bank = "HSBC"
    elif "tpbank" in txt or "tp" in txt or "tp bank" in txt:
        bank = "TPBank"
    elif "ocb" in txt or "liobank" in txt:
        bank = "OCB"
    elif "vikki" in txt or "hdbank" in txt or "hd bank" in txt:
        bank = "HDBank"
    elif "vietcombank" in txt or "vcb" in txt:
        bank = "Vietcombank"
    elif "vietinbank" in txt or "ctg" in txt:
        bank = "VietinBank"
    elif "bidv" in txt:
        bank = "BIDV"
    elif "shinhan" in txt:
        bank = "Shinhan Bank"
    elif "sacombank" in txt:
        bank = "Sacombank"

    # Card
    card = "-"
    if "stepup" in txt or "step up" in txt:
        card = "VPBank StepUp"
    elif "super card" in txt or "supercard" in txt:
        card = "VIB Super Card"
    elif "cashback" in txt or "hoàn tiền" in txt:
        card = f"{bank} Cashback" if bank != "-" else "Cashback Card"
    elif "travel" in txt or "du lịch" in txt or "bay" in txt:
        card = "Travel Élite"
    elif "ivy" in txt or "max card" in txt or "max" in txt:
        card = "Max Card"
    elif "everyday" in txt:
        card = "Techcombank Everyday"
    elif "liobank" in txt or "lio" in txt:
        card = "Liobank 2in1"
    elif "jcb" in txt:
        card = f"{bank} JCB" if bank != "-" else "JCB Card"
    elif "signature" in txt:
        card = "Visa Signature"
    elif "platinum" in txt:
        card = "Visa Platinum"

    # Category
    category = "Khác"
    if any(k in txt for k in ["shopee", "lazada", "tiki", "tiktok shop", "online", "mua sắm", "thương mại điện tử", "quẹt pos"]):
        category = "Mua sắm Online"
    elif any(k in txt for k in ["trả góp", "0%", "kỳ hạn", "chuyển đổi trả góp", "sao kê"]):
        category = "Trả góp 0%"
    elif any(k in txt for k in ["rút tiền", "đáo hạn", "phí rút", "bào thẻ", "rút mặt", "pos rút"]):
        category = "Rút tiền & Đáo hạn"
    elif any(k in txt for k in ["du lịch", "vé máy bay", "khách sạn", "ngoại tệ", "nước ngoài", "trung quốc", "hàn", "singapore", "thái"]):
        category = "Du lịch & Ngoại tệ"
    elif any(k in txt for k in ["ăn uống", "nhà hàng", "grab", "be", "food", "quán ăn", "ẩm thực", "cafe"]):
        category = "Ẩm thực & Di chuyển"
    elif any(k in txt for k in ["sang ngang", "mở thẻ", "điều kiện", "hạn mức", "chứng minh thu nhập", "làm thẻ"]):
        category = "Mở & Sang ngang thẻ"

    # Intent
    intent = "hoi_uu_dai"
    if any(k in txt for k in ["điều kiện", "mở thẻ", "làm thẻ", "sang ngang", "hạn mức", "hồ sơ", "duyệt"]):
        intent = "hoi_dieu_kien_mo_the"
    elif any(k in txt for k in ["phí", "lãi", "hoàn tiền", "cashback", "mcc", "khuyến mãi", "ưu đãi", "bao nhiêu %"]):
        intent = "hoi_uu_dai"
    elif any(k in txt for k in ["so sánh", "nên dùng", "loại nào hơn", "thẻ nào ngon", "khuyên dùng"]):
        intent = "so_sanh_the"
    elif any(k in txt for k in ["cần rút", "đáo", "bào", "dịch vụ", "inbox", "ib", "liên hệ"]):
        intent = "tim_dich_vu"

    return {
        "spending_category": category,
        "target_bank": bank if bank != "-" else None,
        "target_card": card if card != "-" else None,
        "intent": intent
    }

def run_fast_enrichment():
    print("=" * 70)
    print("🚀 BẮT ĐẦU CẬP NHẬT DỮ LIỆU MỚI & PHÂN TÍCH AI (FAST BATCH PIPELINE)")
    print("=" * 70)

    # 1. Lấy toàn bộ comments có status pending
    all_pending = []
    offset = 0
    limit = 1000
    while True:
        url = f"{SUPABASE_URL}/rest/v1/raw_comments?status=eq.pending&select=id,content,author,platform&order=id.asc&offset={offset}&limit={limit}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if not data:
            break
        all_pending.extend(data)
        if len(data) < limit:
            break
        offset += limit

    print(f"📦 Số comment PENDING cần xử lý AI: {len(all_pending)}")

    if not all_pending:
        print("✅ Tất cả comment đã được xử lý (0 pending).")
    else:
        # 2. Tạo insights
        insights_batch = []
        pending_ids = []
        for p in all_pending:
            c_id = p["id"]
            pending_ids.append(c_id)
            c_info = extract_financial_insights(p.get("content", ""))
            insights_batch.append({
                "comment_id": c_id,
                "spending_category": c_info["spending_category"],
                "target_bank": c_info["target_bank"],
                "target_card": c_info["target_card"],
                "intent": c_info["intent"]
            })

        # 3. Ghi vào bảng insights theo chunk 50
        chunk_size = 50
        for i in range(0, len(insights_batch), chunk_size):
            chunk = insights_batch[i:i + chunk_size]
            res = requests.post(f"{SUPABASE_URL}/rest/v1/insights", headers=HEADERS, json=chunk, timeout=10)
            if res.status_code not in [200, 201]:
                print(f"  ⚠️ Lưu insights batch {i//chunk_size + 1} mã lỗi: {res.status_code}")

        print(f"✨ Đã phân tích và tạo {len(insights_batch)} insights AI mới thành công.")

        # 4. Update status = processed cho raw_comments theo chunk 50
        for i in range(0, len(pending_ids), chunk_size):
            chunk_ids = pending_ids[i:i + chunk_size]
            ids_param = ",".join(map(str, chunk_ids))
            patch_url = f"{SUPABASE_URL}/rest/v1/raw_comments?id=in.({ids_param})"
            requests.patch(patch_url, headers=HEADERS, json={"status": "processed"}, timeout=10)

        print(f"✅ Đã cập nhật trạng thái PROCESSED cho {len(pending_ids)} comment!")

    # 5. Kiểm tra tổng kết database
    count_headers = {**HEADERS, "Prefer": "count=exact"}
    r_total = requests.get(f"{SUPABASE_URL}/rest/v1/raw_comments?select=id&limit=1", headers=count_headers, timeout=10)
    r_pend = requests.get(f"{SUPABASE_URL}/rest/v1/raw_comments?status=eq.pending&select=id&limit=1", headers=count_headers, timeout=10)
    r_ins = requests.get(f"{SUPABASE_URL}/rest/v1/insights?select=id&limit=1", headers=count_headers, timeout=10)

    total_cr = r_total.headers.get("content-range", "").split("/")[-1]
    pending_cr = r_pend.headers.get("content-range", "").split("/")[-1]
    insights_cr = r_ins.headers.get("content-range", "").split("/")[-1]

    print("=" * 70)
    print("📊 TỔNG KẾT TRẠNG THÁI DATABASE:")
    print(f"  • Tổng số comment thực tế: {total_cr} bản ghi")
    print(f"  • Số comment Pending còn lại: {pending_cr}")
    print(f"  • Tổng số Insights đã phân tích: {insights_cr}")
    print("=" * 70)
    print("🎉 Dữ liệu đã sẵn sàng trên website: https://abf-executive-dashboard.vercel.app")

if __name__ == "__main__":
    run_fast_enrichment()
