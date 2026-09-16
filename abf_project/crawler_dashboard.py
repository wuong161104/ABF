# -*- coding: utf-8 -*-
"""
=============================================================================
ABF UNIVERSAL CRAWLER & SUPABASE WEB GUI (STREAMLIT DASHBOARD)
-----------------------------------------------------------------------------
- Giao diện trực quan cho phép dán bất kỳ URL nào để cào dữ liệu.
- Tự động cuộn từ trên xuống dưới mượt mà để không bỏ sót dữ liệu.
- Tự động click các nút "Biểu phí & điều kiện", "Bảo hiểm thẻ", "Xem chi tiết",...
- Tự động loại trừ các nút đăng ký / mở thẻ giao dịch.
- TỰ ĐỘNG ĐỒNG BỘ VÀO BẢNG 'crawled_web_data' TRÊN SUPABASE DB.
=============================================================================
"""

import os
import json
import time
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from deep_web_crawler import DeepWebCrawler

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

st.set_page_config(
    page_title="ABF Universal Deep Web Crawler & Supabase Hub",
    page_icon="🌐",
    layout="wide"
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .status-card-success {
        background: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 1.2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .status-card-error {
        background: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 1.2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .db-badge {
        display: inline-block;
        background: #E0E7FF;
        color: #3730A3;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🌐 ABF Universal Deep-Click Web Crawler & Supabase Sync</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Cuộn trang toàn diện • Click nút con ("Biểu phí & điều kiện", "Bảo hiểm thẻ") • Lưu trực tiếp vào Supabase Database</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# Configuration & URL Input Section
# ----------------------------------------------------
with st.container():
    st.subheader("🎯 Cấu hình Mục tiêu Cào Dữ Liệu")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        target_url = st.text_input(
            "🔗 Dán đường link trang web cần crawl:",
            value="https://www.vib.com.vn/vn/the-tin-dung",
            help="Bạn có thể dán link VIB hoặc bất kỳ trang web nào (Thương mại điện tử, Ngân hàng, Báo chí,...)"
        )
    with col2:
        max_subpages = st.number_input("Số nút phụ / link cào sâu tối đa:", min_value=1, max_value=50, value=12)

    col_btn, col_opt1, col_opt2 = st.columns([1.2, 1, 1])
    with col_btn:
        start_crawl = st.button("🚀 BẮT ĐẦU CRAWL & LƯU SUPABASE", type="primary", use_container_width=True)
    with col_opt1:
        save_supabase_toggle = st.checkbox("Đồng bộ vào Supabase DB", value=True)
    with col_opt2:
        headless_mode = st.checkbox("Chạy ẩn trình duyệt (Headless)", value=True)

# ----------------------------------------------------
# Execution Handler
# ----------------------------------------------------
if start_crawl and target_url:
    progress_container = st.container()
    with progress_container:
        with st.spinner(f"🚀 Đang khởi động Chromium engine, cuộn toàn trang và cào dữ liệu từ {target_url}..."):
            crawler = DeepWebCrawler(
                base_url=target_url,
                output_dir="crawled_data",
                headless=headless_mode,
                max_subpages=max_subpages,
                save_to_supabase=save_supabase_toggle
            )
            result = crawler.run()
            st.session_state["last_crawl_result"] = result

# ----------------------------------------------------
# Display Crawl Results
# ----------------------------------------------------
if "last_crawl_result" in st.session_state:
    res = st.session_state["last_crawl_result"]
    
    st.markdown("---")
    
    # Status Banner
    if res.get("status") == "SUCCESS":
        db_count = res.get('supabase_records_saved', 0)
        st.markdown(f"""
        <div class="status-card-success">
            <h3 style="color: #065F46; margin:0 0 5px 0;">🎉 CRAWL VÀ ĐỒNG BỘ SUPABASE THÀNH CÔNG RỰC RỠ!</h3>
            <p style="color: #047857; margin:0;">
                Đã hoàn thành cuộn toàn trang, bóc tách trang chính, click chuột vào các nút hành động con và lưu <b>{db_count} bản ghi</b> vào bảng <code>public.crawled_web_data</code> trên Supabase DB.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        err = res.get("error_message") or "Không xác định"
        st.markdown(f"""
        <div class="status-card-error">
            <h3 style="color: #991B1B; margin:0 0 5px 0;">❌ CRAWL THẤT BÀI!</h3>
            <p style="color: #B91C1C; margin:0;">Lỗi: {err}</p>
        </div>
        """, unsafe_allow_html=True)

    # Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⏱️ Thời gian xử lý", f"{res.get('duration_seconds', 0)}s")
    m2.metric("🔗 Link phụ đã click & cào", res.get("total_subpages_crawled", 0))
    m3.metric("🖼️ Hình ảnh trích xuất", res.get("total_images_found", 0))
    m4.metric("💾 Bản ghi lưu Supabase", res.get("supabase_records_saved", 0))

    # Detail Tabs
    tab_img, tab_subpages, tab_db, tab_main, tab_export = st.tabs([
        "🖼️ Thư viện Hình ảnh & Đường link",
        "📑 Chi tiết Nút bấm (Biểu phí, Bảo hiểm,...)",
        "💾 Xem Dữ liệu Supabase DB",
        "📜 Toàn văn Trang chính",
        "💾 Xuất Dữ liệu (JSON / Markdown)"
    ])

    with tab_img:
        st.subheader(f"🖼️ Tổng cộng {res.get('total_images_found', 0)} Hình ảnh / Link ảnh")
        images = res.get("all_images", [])
        if images:
            cols = st.columns(4)
            for idx, img in enumerate(images):
                with cols[idx % 4]:
                    img_url = img.get("url", "")
                    alt = img.get("alt") or f"Hình ảnh #{idx+1}"
                    try:
                        st.image(img_url, caption=alt, use_container_width=True)
                    except Exception:
                        st.caption(f"[{alt}]({img_url})")
                    st.code(img_url, language="text")
        else:
            st.info("Không tìm thấy hình ảnh nào.")

    with tab_subpages:
        st.subheader("📑 Danh sách Trang phụ / Nút bấm đã Click và Cào nội dung")
        subpages = res.get("subpages_crawled", [])
        if subpages:
            for sp in subpages:
                with st.expander(f"📍 {sp.get('button_text')} ({sp.get('url')}) - {len(sp.get('tables', []))} Bảng biểu", expanded=False):
                    st.markdown(f"**Tiêu đề trang phụ:** {sp.get('page_title')}")
                    st.markdown(f"**URL:** [{sp.get('url')}]({sp.get('url')})")
                    
                    if sp.get("tables"):
                        st.markdown("#### 📊 Các Bảng Dữ liệu:")
                        for t_idx, tbl in enumerate(sp.get("tables", []), 1):
                            st.write(f"**Bảng {t_idx}:**")
                            st.table(tbl)
                            
                    st.markdown("#### 📝 Nội dung văn bản chi tiết:")
                    st.text_area("Văn bản trích xuất", sp.get("raw_text", ""), height=250, key=sp.get("url"))
        else:
            st.info("Chưa có trang phụ nào được cào.")

    with tab_db:
        st.subheader("💾 Dữ liệu trong bảng `public.crawled_web_data` (Supabase DB)")
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/crawled_web_data?select=id,source_url,page_title,content_type,section_title,crawled_at&order=id.desc&limit=25",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                },
                timeout=10
            )
            if resp.status_code == 200:
                records = resp.json()
                if records:
                    df = pd.DataFrame(records)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Chưa có bản ghi nào trong bảng crawled_web_data.")
            else:
                st.warning(f"Không thể tải dữ liệu Supabase: {resp.text}")
        except Exception as db_err:
            st.error(f"Lỗi kết nối Supabase: {db_err}")

    with tab_main:
        st.subheader(f"📜 {res.get('main_page', {}).get('title', '')}")
        st.text_area(
            "Toàn bộ văn bản trang chính:",
            res.get("main_page", {}).get("raw_text", ""),
            height=400
        )
        if res.get("main_page", {}).get("tables"):
            st.markdown("### 📊 Các Bảng Biểu trên Trang chính:")
            for t_idx, tbl in enumerate(res.get("main_page", {}).get("tables", []), 1):
                st.write(f"**Bảng {t_idx}:**")
                st.table(tbl)

    with tab_export:
        st.subheader("💾 Tải về Kết quả Crawl")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 TẢI VỀ FILE JSON (Đầy đủ cấu trúc)",
                data=json.dumps(res, ensure_ascii=False, indent=2),
                file_name="crawled_result.json",
                mime="application/json",
                use_container_width=True
            )
        with c2:
            md_content = f"# KẾT QUẢ CRAWL\n\nTarget URL: {res.get('target_url')}\nStatus: {res.get('status')}\n\n"
            md_content += f"## Main Content\n\n{res.get('main_page', {}).get('raw_text', '')}\n\n"
            for sp in res.get("subpages_crawled", []):
                md_content += f"## Subpage: {sp.get('button_text')}\n{sp.get('url')}\n\n{sp.get('raw_text', '')}\n\n"
            st.download_button(
                "📥 TẢI VỀ FILE MARKDOWN (.md)",
                data=md_content,
                file_name="crawled_result.md",
                mime="text/markdown",
                use_container_width=True
            )
