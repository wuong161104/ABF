# -*- coding: utf-8 -*-
"""
Script xóa toàn bộ dữ liệu trùng lặp trong Supabase (raw_comments)
- Giữ lại bản ghi gốc đầu tiên (ID nhỏ nhất).
- Xóa tất cả các bản ghi bị nhân bản / trùng nội dung trên cùng nền tảng.
"""

import requests
from collections import defaultdict

SUPABASE_URL = "https://azpvcqpnecljsosamnot.supabase.co"
SUPABASE_KEY = "sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "return=minimal"
}

def clean_database_duplicates():
    print("=" * 70)
    print("🧹 BẮT ĐẦU QUÉT VÀ DỌN DẸP DỮ LIỆU TRÙNG LẶP TRÊN SUPABASE")
    print("=" * 70)

    # 1. Tải toàn bộ dữ liệu raw_comments
    all_records = []
    offset = 0
    limit = 1000
    while True:
        url = f"{SUPABASE_URL}/rest/v1/raw_comments?select=id,platform,author,content,comment_created_at,crawled_at&order=id.asc&offset={offset}&limit={limit}"
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"❌ Lỗi khi tải dữ liệu: {res.status_code} - {res.text}")
            return
        data = res.json()
        if not data:
            break
        all_records.extend(data)
        if len(data) < limit:
            break
        offset += limit

    print(f"📊 Tổng số bản ghi hiện tại trong database: {len(all_records)}")

    # 2. Gom nhóm để tìm các bản ghi trùng lặp
    # Tiêu chí trùng: Cùng platform và cùng nội dung (chuẩn hóa khoảng trắng + chữ thường)
    seen = defaultdict(list)
    for rec in all_records:
        platform = (rec.get("platform") or "").strip().lower()
        norm_content = " ".join((rec.get("content") or "").strip().lower().split())
        key = (platform, norm_content)
        seen[key].append(rec["id"])

    ids_to_delete = []
    for key, ids in seen.items():
        if len(ids) > 1:
            # Giữ lại ID đầu tiên (bản ghi sớm nhất), đưa các ID còn lại vào danh sách xóa
            ids_to_delete.extend(ids[1:])

    print(f"🔍 Phát hiện: {len(ids_to_delete)} bản ghi bị trùng lặp cần xóa.")

    if not ids_to_delete:
        print("✅ Không có dữ liệu nào bị trùng lặp!")
        return

    # 3. Tiến hành xóa theo từng đợt (batch)
    chunk_size = 50
    deleted_count = 0
    total_batches = (len(ids_to_delete) + chunk_size - 1) // chunk_size

    for i in range(0, len(ids_to_delete), chunk_size):
        chunk = ids_to_delete[i:i + chunk_size]
        ids_param = ",".join(map(str, chunk))
        del_url = f"{SUPABASE_URL}/rest/v1/raw_comments?id=in.({ids_param})"
        del_res = requests.delete(del_url, headers=HEADERS, timeout=15)
        
        batch_no = (i // chunk_size) + 1
        if del_res.status_code in [200, 204]:
            deleted_count += len(chunk)
            print(f"  ↳ Đang xóa batch {batch_no}/{total_batches}: {len(chunk)} bản ghi thành công.")
        else:
            print(f"  ⚠️ Lỗi khi xóa batch {batch_no}: {del_res.status_code} - {del_res.text}")

    print("=" * 70)
    print(f"🎉 HOÀN TẤT: Đã xóa sạch {deleted_count} bản ghi trùng lặp!")

    # 4. Kiểm tra lại số lượng bản ghi còn lại
    count_headers = {**HEADERS, "Prefer": "count=exact"}
    r_check = requests.get(f"{SUPABASE_URL}/rest/v1/raw_comments?select=id&limit=1", headers=count_headers, timeout=10)
    cr = r_check.headers.get("content-range", "")
    final_count = cr.split("/")[-1] if "/" in cr else "Không rõ"
    print(f"📦 Tổng số bản ghi chuẩn DUY NHẤT còn lại trên Supabase: {final_count}")
    print("=" * 70)

if __name__ == "__main__":
    clean_database_duplicates()
