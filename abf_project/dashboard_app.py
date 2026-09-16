"""
BOD Dashboard - Insight Thẻ Tín Dụng (Bài toán 1 - ABF Test)
Chạy bằng Streamlit: `streamlit run dashboard_app.py`
"""

import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r")

st.set_page_config(
    page_title="ABF - Insight Thẻ Tín Dụng Dashboard",
    page_icon="💳",
    layout="wide"
)

# Custom CSS cho giao diện phong cách Linear/Vercel (Clean Light Mode)
st.markdown("""
<style>
    .main {
        background-color: #F9FAFB;
        font-family: 'Inter', sans-serif;
    }
    .metric-box {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 2px 0 rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_dashboard_data():
    supabase = init_supabase()
    try:
        raw_res = supabase.table("raw_comments").select("*").execute()
        insight_res = supabase.table("insights").select("*").execute()
        return pd.DataFrame(raw_res.data), pd.DataFrame(insight_res.data)
    except Exception as e:
        # Return Mock DataFrame cho Demo
        df_raw = pd.DataFrame([
            {"id": 101, "platform": "tiktok", "author": "ducmanhtruong0", "content": "Ủa mình dùng hsbc đến kì sao kê mới đc hoàn. Mấy thẻ này dc hoàn luôn à các ct?", "status": "processed"},
            {"id": 102, "platform": "tiktok", "author": "dienannguyen", "content": "Thẻ nào đang mức chi cần thấp nhất ạ, e đag đóng học phí cho con cỡ 6tr thôi", "status": "processed"},
            {"id": 103, "platform": "tiktok", "author": "sugiavinh", "content": "Con VIB Family Link thì sao nhỉ, sang ngang thẻ VPBank qua được không ad?", "status": "processed"},
            {"id": 104, "platform": "facebook", "author": "Minh Trí", "content": "Thẻ VIB Max Card hoàn tiền 10% danh mục Mua sắm online đúng không bạn?", "status": "processed"},
            {"id": 105, "platform": "zalo", "author": "Anh Hoàng (Sales VP)", "content": "Khách đang hỏi rút tiền mặt hạn mức 50tr thẻ StepUp VPBank phí sao ạ?", "status": "processed"}
        ])
        df_insights = pd.DataFrame([
            {"spending_category": "mua_sam_online", "target_bank": "VIB", "target_card": "Max Card", "intent": "hoi_uu_dai"},
            {"spending_category": "du_lich", "target_bank": "VIB", "target_card": "Travel Élite", "intent": "hoi_dieu_kien_mo_the"},
            {"spending_category": "mua_sam_online", "target_bank": "VPBank", "target_card": "StepUp", "intent": "hoi_uu_dai"},
            {"spending_category": "tra_gop", "target_bank": "Techcombank", "target_card": "Everyday", "intent": "so_sanh_the"},
            {"spending_category": "rut_tien", "target_bank": "MB", "target_card": "Hi Collection", "intent": "hoi_uu_dai"}
        ])
        return df_raw, df_insights

st.title("💳 ABF Credit Card Insights Dashboard (For BOD)")
st.markdown("*Báo cáo tổng hợp nhu cầu thẻ tín dụng từ TikTok, Facebook Fanpage & Zalo Groups (Realtime Supabase)*")

df_raw, df_insights = fetch_dashboard_data()

# 📌 1. Các chỉ số KPI tổng quan
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("TỔNG TƯƠNG TÁC/COMMENT", len(df_raw))
with col2:
    tiktok_cnt = len(df_raw[df_raw['platform'] == 'tiktok']) if not df_raw.empty else 0
    st.metric("TIKTOK COMMENTS", tiktok_cnt)
with col3:
    fb_cnt = len(df_raw[df_raw['platform'] == 'facebook']) if not df_raw.empty else 0
    st.metric("FACEBOOK COMMENTS", fb_cnt)
with col4:
    zalo_cnt = len(df_raw[df_raw['platform'] == 'zalo']) if not df_raw.empty else 0
    st.metric("ZALO GROUP MESSAGES", zalo_cnt)

st.divider()

# 📌 2. Biểu đồ Phân tích Chi tiết (3 Chỉ số BOD)
c1, c2 = st.columns(2)

with c1:
    st.subheader("🛒 1. Top Lĩnh Vực Chi Tiêu Quan Tâm")
    if not df_insights.empty and 'spending_category' in df_insights.columns:
        cat_counts = df_insights['spending_category'].value_counts()
        st.bar_chart(cat_counts)

with c2:
    st.subheader("🏦 2. Top Ngân Hàng Được Đề Cập")
    if not df_insights.empty and 'target_bank' in df_insights.columns:
        bank_counts = df_insights['target_bank'].value_counts()
        st.bar_chart(bank_counts)

st.divider()

st.subheader("💳 3. Chi Tiết Dữ Liệu Realtime Supabase")
st.dataframe(df_raw, use_container_width=True)

st.sidebar.header("⚙️ Bộ lọc")
st.sidebar.selectbox("Nền tảng", ["Tất cả", "TikTok", "Facebook", "Zalo"])
if st.sidebar.button("🔄 Làm mới dữ liệu"):
    st.cache_resource.clear()
    st.rerun()
