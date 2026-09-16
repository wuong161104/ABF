# -*- coding: utf-8 -*-
"""
=============================================================================
ZALO REALTIME & HISTORICAL CONTINUOUS CRAWLER (OpenClaw / Local Engine)
-----------------------------------------------------------------------------
- Hỗ trợ lựa chọn nhiều nhóm Zalo mục tiêu để cào dữ liệu.
- Chạy liên tục 24/7 (Realtime Listener), chỉ dừng khi bạn bấm Ctrl + C.
- Giai đoạn 1: Tự động cuộn 100 lần (dừng 10 - 15s mỗi lần cuộn để Zalo tải tin nhắn cũ)
               và lưu toàn bộ vào Supabase DB.
- Giai đoạn 2: Lắng nghe LIÊN TỤC tin nhắn MỚI phát sinh trong nhóm đã chọn.
- TỰ ĐỘNG BÓC TÁCH QUOTE & KIỂM TRA TRÙNG LẶP ĐA TẦNG (PRE-CHECK DEDUPLICATION):
  + Tự động loại bỏ đoạn text trích dẫn (quote banner) bị lặp lại khi trả lời.
  + Tầng 1: In-memory Normalized Cache (quét 0ms, không tốn tài nguyên).
  + Tầng 2: Direct Supabase REST verification trước khi thực hiện lệnh INSERT.
=============================================================================
"""

import os
import sys
import re
import time
import random
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Set
import requests
from playwright.sync_api import sync_playwright

PRESET_GROUPS = {
    "1": {
        "search_name": "Bào thẻ thông minh",
        "group_id": "51668508783094466",
        "display_name": "Zalo Group - Bào thẻ thông minh (51668508783094466)",
        "aliases": ["bào thẻ thông minh", "bao the thong minh", "bào thẻ", "bao the", "51668508783094466"]
    },
    "2": {
        "search_name": "Cardfind - Hỗ trợ làm thẻ tín dụng",
        "group_id": "cardfind_credit_support",
        "display_name": "Zalo Group - Cardfind - Hỗ trợ làm thẻ tín dụng",
        "aliases": ["cardfind - hỗ trợ làm thẻ tín dụng", "cardfind", "hỗ trợ làm thẻ tín dụng", "ho tro lam the tin dung", "lam the tin dung"]
    }
}

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zalo_browser_profile")

SUPABASE_URL = "https://azpvcqpnecljsosamnot.supabase.co"
SUPABASE_KEY = "sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def normalize_text(text: str) -> str:
    """Chuẩn hóa chuỗi văn bản để so sánh trùng lặp chính xác tuyệt đối"""
    if not text:
        return ""
    return " ".join(text.replace('\xa0', ' ').strip().lower().split())

def cleanup_profile_locks():
    """Dọn dẹp tiến trình Chromium tự động cũ và file khóa profile để tránh lỗi xung đột"""
    try:
        if os.name == 'nt':
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force"],
                capture_output=True, timeout=5
            )
    except Exception:
        pass
    
    for fname in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        fpath = os.path.join(PROFILE_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass

def load_existing_zalo_messages() -> Set[str]:
    """Tải TOÀN BỘ tin nhắn Zalo đã có trong DB với cơ chế phân trang để chống trùng lặp tuyệt đối"""
    cache = set()
    offset = 0
    limit = 1000
    try:
        while True:
            url = f"{SUPABASE_URL}/rest/v1/raw_comments?platform=eq.zalo&select=content&order=id.asc&offset={offset}&limit={limit}"
            res = requests.get(url, headers=SUPABASE_HEADERS, timeout=10)
            if res.status_code == 200:
                items = res.json()
                if not items:
                    break
                for it in items:
                    c = it.get("content")
                    if c:
                        cache.add(normalize_text(c))
                if len(items) < limit:
                    break
                offset += limit
            else:
                break
    except Exception as e:
        print(f"⚠️ Không thể tải cache Supabase: {e}")
    return cache

def parse_zalo_message(card_text: str):
    """Trích xuất sạch Tác giả & Nội dung thật của tin nhắn, bóc tách đoạn trích dẫn quote và rác hệ thống"""
    if not card_text or len(card_text.strip()) < 3:
        return None, None
        
    text = card_text.replace('\xa0', ' ').strip()
    lowered = text.lower()
    
    ignored_keywords = [
        "đã tham gia nhóm", "đã đổi tên", "đã rời nhóm", "đã xóa",
        "tin nhắn đã được thu hồi", "đã ghim tin nhắn", "đã bình chọn",
        "việc làm bắc ninh", "thời gian áp dụng", "tổng hợp các thẻ"
    ]
    if any(k in lowered for k in ignored_keywords):
        return None, None

    # Lọc bỏ dòng timestamp hoặc emo code
    lines = []
    for l in text.splitlines():
        l_str = l.strip()
        if not l_str:
            continue
        if re.match(r'^\d{1,2}:\d{2}(\s+\d+)?$', l_str):
            continue
        if l_str.startswith("/-") or l_str in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", ":>", ":o", ":-h", ":-(("]:
            continue
        lines.append(l_str)
        
    if not lines:
        return None, None

    author = "Thành viên Zalo"
    
    first_line = lines[0]
    if 2 <= len(first_line) <= 30 and not first_line.startswith("http") and not first_line.startswith("@"):
        if "cardfind" not in first_line.lower() and "bào thẻ" not in first_line.lower() and ":" not in first_line:
            author = first_line
            lines = lines[1:] if len(lines) > 1 else lines

    # Bóc tách quote trích dẫn: nếu có nhiều đoạn @, chỉ lấy đoạn trả lời thật sự ở cuối
    paragraphs = []
    curr = []
    for l in lines:
        if l.startswith('@') and curr:
            paragraphs.append('\n'.join(curr))
            curr = [l]
        else:
            curr.append(l)
    if curr:
        paragraphs.append('\n'.join(curr))

    content = paragraphs[-1].strip() if paragraphs else '\n'.join(lines).strip()
    content = re.sub(r'\s+\d{1,2}:\d{2}(\s+\d+)?$', '', content).strip()

    if len(content) < 3 or content.isdigit():
        return None, None

    return author, content

def save_message_to_supabase(msg: Dict[str, Any], cache: Set[str]) -> bool:
    """
    KIỂM TRA TRÙNG LẶP TRƯỚC KHI LƯU VÀO SUPABASE (PRE-CHECK DEDUPLICATION):
    - Tầng 1: Kiểm tra nhanh trong in-memory cache (0ms).
    - Tầng 2: Truy vấn Supabase trực tiếp xác nhận chưa từng có bản ghi nào tương tự.
    - Chỉ gửi lệnh INSERT khi nội dung HOÀN TOÀN MỚI.
    """
    raw_content = msg.get("content", "").strip()
    if not raw_content or len(raw_content) < 3:
        return False
        
    norm_content = normalize_text(raw_content)
    
    # 1. TẦNG 1: Kiểm tra trong Cache Bộ Nhớ (0ms)
    if norm_content in cache:
        return False
        
    # 2. TẦNG 2: Kiểm tra trực tiếp trên Supabase DB qua REST API trước khi ghi
    try:
        check_url = f"{SUPABASE_URL}/rest/v1/raw_comments?platform=eq.zalo&content=eq.{requests.utils.quote(raw_content)}&select=id&limit=1"
        check_res = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=5)
        if check_res.status_code == 200 and len(check_res.json()) > 0:
            cache.add(norm_content)
            return False
    except Exception:
        pass

    # 3. GHI MỚI VÀO SUPABASE
    try:
        url = f"{SUPABASE_URL}/rest/v1/raw_comments"
        payload = {
            "platform": "zalo",
            "group_or_page": msg["group_or_page"],
            "author": msg["author"],
            "content": raw_content,
            "comment_created_at": msg["created_at"],
            "source_url": msg["source_url"],
            "status": "pending"
        }
        res = requests.post(url, headers=SUPABASE_HEADERS, json=payload, timeout=10)
        if res.status_code in [200, 201]:
            cache.add(norm_content)
            return True
        return False
    except Exception as e:
        print(f"⚠️ Lỗi lưu Supabase: {e}")
        return False

def select_target_group() -> Dict[str, Any]:
    """Hiển thị menu để người dùng chọn nhóm Zalo muốn cào"""
    print("\n" + "=" * 75)
    print("🎯 CHỌN NHÓM ZALO BẠN MUỐN CÀO DỮ LIỆU:")
    print("=" * 75)
    print("  [1] Nhóm 1: Bào thẻ thông minh")
    print("  [2] Nhóm 2: Cardfind - Hỗ trợ làm thẻ tín dụng")
    print("  [3] Tự nhập tên một nhóm Zalo khác...")
    print("=" * 75)
    
    choice = input("👉 Nhập lựa chọn của bạn (1, 2 hoặc 3): ").strip()
    
    if choice == "1":
        selected = PRESET_GROUPS["1"]
    elif choice == "2":
        selected = PRESET_GROUPS["2"]
    elif choice == "3":
        custom_name = input("👉 Nhập chính xác tên nhóm Zalo bạn muốn tìm: ").strip()
        if not custom_name:
            print("⚠️ Tên nhóm không được để trống! Tự động chọn Nhóm 1.")
            selected = PRESET_GROUPS["1"]
        else:
            selected = {
                "search_name": custom_name,
                "group_id": "custom_group",
                "display_name": f"Zalo Group - {custom_name}",
                "aliases": [custom_name.lower()]
            }
    else:
        print("⚠️ Lựa chọn không hợp lệ, tự động chọn [1] Bào thẻ thông minh.")
        selected = PRESET_GROUPS["1"]
        
    return selected

def run_continuous_zalo_crawler():
    cleanup_profile_locks()
    selected_group = select_target_group()
    
    search_name = selected_group["search_name"]
    group_id = selected_group["group_id"]
    display_group_name = selected_group["display_name"]
    aliases = selected_group.get("aliases", [search_name.lower()])
    
    print("\n" + "=" * 75)
    print("🚀 [OpenClaw Engine] KHỞI ĐỘNG HỆ THỐNG CÀO ZALO LIÊN TỤC 24/7")
    print(f"🎯 Nhóm mục tiêu: '{search_name}'")
    print(f"📁 Session Storage: {PROFILE_DIR}")
    print("🛡️  Cơ chế kiểm tra trùng lặp: Đã kích hoạt Pre-Check đa tầng & Bóc tách Quote")
    print("🛑 Để DỪNG chương trình: Bấm tổ hợp phím [Ctrl + C] trên Terminal")
    print("=" * 75)

    saved_texts_cache: Set[str] = load_existing_zalo_messages()
    print(f"📦 Đã nạp {len(saved_texts_cache)} tin nhắn Zalo chuẩn từ Supabase vào bộ nhớ Pre-Check.")

    with sync_playwright() as p:
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 850},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = browser_context.new_page()
        print("\n🌐 Đang mở Zalo Web (chat.zalo.me)...")
        page.goto("https://chat.zalo.me/", timeout=60000)
        
        # 1. Kiểm tra đăng nhập
        try:
            page.wait_for_selector("#main-tab, .leftbar-tab, .nav__tabs__top", timeout=10000)
            print("✅ Đã nhận diện phiên đăng nhập Zalo thành công!")
        except Exception:
            print("\n" + "!" * 75)
            print("👉 VUI LÒNG DÙNG ĐIỆN THOẠI QUÉT MÃ QR TRÊN MÀN HÌNH ĐỂ ĐĂNG NHẬP (CHỈ LÀM 1 LẦN) 👈")
            print("!" * 75 + "\n")
            page.wait_for_selector("#main-tab, .leftbar-tab, .nav__tabs__top", timeout=180000)
            print("🎉 Đăng nhập thành công! Phiên làm việc đã được lưu vĩnh viễn.")
        
        time.sleep(2)
        
        # 2. BẮT BUỘC TÌM KIẾM TRÊN THANH SEARCH
        print(f"\n🔍 Đang tìm kiếm nhóm '{search_name}' trên thanh tìm kiếm Zalo...")
        group_found = False
        
        try:
            search_selectors = [
                "input#contact-search-input",
                "input[placeholder*='Tìm kiếm']",
                "input[placeholder*='Search']",
                ".search-input input",
                "input[type='search']"
            ]
            search_box = None
            for sel in search_selectors:
                search_box = page.query_selector(sel)
                if search_box:
                    break
            
            if search_box:
                search_box.click()
                time.sleep(0.5)
                clear_btn = page.query_selector(".search-input .fa-close, .search-input .icon-close, .search-box-clear")
                if clear_btn:
                    try:
                        clear_btn.click()
                        time.sleep(0.3)
                    except Exception:
                        pass
                
                search_box.fill("")
                time.sleep(0.3)
                search_box.fill(search_name)
                print(f"🔎 Đã gõ từ khóa: '{search_name}' vào thanh tìm kiếm.")
                time.sleep(2.5)
                
                results = page.query_selector_all(".conv-item, .chat-item, .list-item, div[class*='search-item'], div[data-id], .left-list .chat-box, div[class*='global-search-item']")
                for r in results:
                    try:
                        r_text = r.inner_text().lower()
                        if any(alias in r_text for alias in aliases) or any(w in r_text for w in search_name.lower().split() if len(w) > 3):
                            r.click()
                            time.sleep(2)
                            group_found = True
                            print(f"👉 Đã chọn chính xác nhóm từ danh sách kết quả tìm kiếm: '{r.inner_text().splitlines()[0]}'")
                            break
                    except Exception:
                        continue
                
                if not group_found and results:
                    results[0].click()
                    time.sleep(2)
                    group_found = True
                    print("👉 Đã chọn kết quả tìm kiếm đầu tiên.")
                
                if not group_found:
                    search_box.press("Enter")
                    time.sleep(2)
                    group_found = True
                    print("👉 Đã nhấn Enter để mở nhóm.")
                
        except Exception as e:
            print(f"⚠️ Lỗi thao tác tìm kiếm: {e}")

        # 3. Kiểm tra Header nhóm hiện tại
        time.sleep(2)
        try:
            header_el = page.query_selector(".header-title, .header-chat__title, .chat-header__title, div[class*='header-title'], #header-chat span")
            current_header = header_el.inner_text() if header_el else ""
            if current_header:
                print(f"💬 Nhóm chat đang mở hiện tại: '{current_header.strip()}'")
        except Exception:
            pass

        if not group_found:
            print(f"\n💡 [LƯU Ý] Nếu chưa vào đúng nhóm, bạn có thể tự click mở nhóm trên màn hình trình duyệt...")

        # 4. GIAI ĐOẠN 1: TỰ ĐỘNG CUỘN 100 LẦN & ĐỢI 10-15s MỖI LẦN ĐỂ TẢI LỊCH SỬ TIN NHẮN
        print("\n" + "=" * 75)
        print("📜 GIAI ĐOẠN 1: TỰ ĐỘNG CUỘN 100 LẦN NGƯỢC LỊCH SỬ TIN NHẮN CŨ...")
        print("⏱️  Mỗi lần cuộn sẽ dừng lại 10 đến 15 giây để Zalo load đầy đủ tin nhắn.")
        print("=" * 75)

        initial_saved = 0
        scroll_rounds = 100
        last_saved_count = 0
        no_new_rounds = 0

        for r in range(1, scroll_rounds + 1):
            cards = page.query_selector_all(".chat-message, .msg-item, .message-view, .card-message, .bubble-item, div[data-id]")
            for card in cards:
                try:
                    raw_text = card.inner_text().strip()
                    author, content = parse_zalo_message(raw_text)
                    if not author or not content:
                        continue
                    
                    msg_obj = {
                        "platform": "zalo",
                        "group_or_page": display_group_name,
                        "author": author,
                        "content": content,
                        "created_at": datetime.now().isoformat(),
                        "source_url": f"https://zalo.me/g/{group_id}" if group_id.isdigit() else "https://chat.zalo.me"
                    }
                    if save_message_to_supabase(msg_obj, saved_texts_cache):
                        initial_saved += 1
                except Exception:
                    continue

            # Cuộn mạnh lên trên để kích hoạt Zalo tải thêm tin nhắn cũ
            try:
                page.mouse.move(600, 400)
                page.mouse.wheel(0, -5000)
                page.keyboard.press("PageUp")
                page.keyboard.press("PageUp")
                page.keyboard.press("Home")
            except Exception:
                pass

            # Dừng lại từ 10 đến 15 giây theo yêu cầu để Zalo load tin nhắn
            wait_time = round(random.uniform(10.0, 15.0), 1)
            print(f"  ↳ [Lượt {r}/{scroll_rounds}] Đang cuộn... Đã lưu mới: {initial_saved} tin nhắn. (Đang dừng đợi {wait_time}s để Zalo tải tin nhắn...)")
            time.sleep(wait_time)

            if initial_saved == last_saved_count:
                no_new_rounds += 1
            else:
                no_new_rounds = 0
            last_saved_count = initial_saved

            if no_new_rounds >= 8:
                print("  ✅ Đã chạm tới tin nhắn đầu tiên / giới hạn lịch sử của nhóm.")
                break

        cards = page.query_selector_all(".chat-message, .msg-item, .message-view, .card-message, .bubble-item, div[data-id]")
        for card in cards:
            try:
                raw_text = card.inner_text().strip()
                author, content = parse_zalo_message(raw_text)
                if not author or not content:
                    continue
                
                msg_obj = {
                    "platform": "zalo",
                    "group_or_page": display_group_name,
                    "author": author,
                    "content": content,
                    "created_at": datetime.now().isoformat(),
                    "source_url": f"https://zalo.me/g/{group_id}" if group_id.isdigit() else "https://chat.zalo.me"
                }
                if save_message_to_supabase(msg_obj, saved_texts_cache):
                    initial_saved += 1
            except Exception:
                continue

        print(f"\n🎉 HOÀN THÀNH GIAI ĐOẠN 1: Đã cào & lưu tổng cộng {initial_saved} tin nhắn LỊCH SỬ MỚI của nhóm '{search_name}' vào Supabase!")

        # 5. GIAI ĐOẠN 2: Chế độ Lắng Nghe Realtime Liên TỤC 24/7
        print("\n" + "=" * 75)
        print(f"🟢 GIAI ĐOẠN 2: ĐANG LẮNG NGHE REALTIME LIÊN TỤC 24/7 TRONG NHÓM '{search_name}'...")
        print("💬 Bất kỳ ai nhắn gì vào nhóm, hệ thống sẽ tự động bắt, kiểm tra trùng lặp và lưu ngay lập tức.")
        print("🛑 (Bấm Ctrl + C trong Terminal này bất cứ lúc nào bạn muốn dừng)")
        print("=" * 75 + "\n")

        try:
            loop_count = 0
            while True:
                time.sleep(3)
                loop_count += 1
                
                cards = page.query_selector_all(".chat-message, .msg-item, .message-view, .card-message, .bubble-item, div[data-id]")
                
                for card in cards[-10:]:
                    try:
                        raw_text = card.inner_text().strip()
                        author, content = parse_zalo_message(raw_text)
                        if not author or not content:
                            continue
                        
                        msg_obj = {
                            "platform": "zalo",
                            "group_or_page": display_group_name,
                            "author": author,
                            "content": content,
                            "created_at": datetime.now().isoformat(),
                            "source_url": f"https://zalo.me/g/{group_id}" if group_id.isdigit() else "https://chat.zalo.me"
                        }
                        if save_message_to_supabase(msg_obj, saved_texts_cache):
                            now_str = datetime.now().strftime("%H:%M:%S")
                            print(f"⚡ [{now_str}] [MỚI] {author}: \"{content[:60]}...\" ──► Đã lưu Supabase!")
                    except Exception:
                        continue
                
                if loop_count % 20 == 0:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"💓 [{current_time}] Hệ thống đang hoạt động bình thường, đang theo dõi nhóm '{search_name}'...")

        except KeyboardInterrupt:
            print("\n" + "=" * 75)
            print("🛑 Nhận được lệnh dừng (Ctrl + C). Đang đóng kết nối an toàn...")
            print("=" * 75)
        finally:
            try:
                browser_context.close()
            except Exception:
                pass
            print("✅ Đã dừng Crawler an toàn. Toàn bộ dữ liệu đã được bảo lưu trên Supabase!")

if __name__ == "__main__":
    run_continuous_zalo_crawler()
