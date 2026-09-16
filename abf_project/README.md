# ABF AI Engineering Test Repository

Dự án này triển khai bộ giải pháp hoàn chỉnh cho 2 bài toán test vị trí **BA kiêm AI Engineering** tại **ABF**:

1. **Bài toán 1**: Hệ thống Crawl comment (TikTok, FB, Zalo) -> AI/LLM Extraction Insights -> Dashboard BOD -> Weekly Telegram Bot Report.
2. **Bài toán 2**: Chatbot Zalo RAG (dòng thẻ VIB Max Card) -> Trả lời tự động trên Group Zalo -> Sales Trigger Telegram Bot khi khách nhắn 1-1 Inbox.

---

## 📁 Cấu Trúc File Dự Án

```
ABF/
├── schema.sql              # Cấu trúc Database PostgreSQL + Vector Extension (Supabase)
├── crawl_comments.py       # Script thu thập/sinh dữ liệu comment từ TikTok, FB, Zalo (Bài 1)
├── ai_processor.py         # Module AI LLM phân loại lĩnh vực chi tiêu, ngân hàng & loại thẻ (Bài 1)
├── dashboard_app.py        # Giao diện Streamlit Dashboard cho BOD hiển thị 3 chỉ số chính (Bài 1)
├── rag_ingest.py           # Module nạp chính sách thẻ VIB Max Card & Vector RAG Search (Bài 2)
├── telegram_bot.py         # Module gửi báo cáo T2 cho BOD & Trigger cho Đội ngũ Sale (Bài 1 & 2)
└── requirements.txt        # Các thư viện Python cần thiết
```

---

## 🚀 Hướng Dẫn Chạy Hệ Thống

### 1. Cài đặt Môi trường & Thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình File `.env`
Tạo file `.env` tại thư mục gốc với thông tin cấu hình:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyZ
TELEGRAM_BOD_CHAT_ID=-100123456789
TELEGRAM_SALES_CHAT_ID=-100987654321
```

### 3. Khởi tạo Database trên Supabase
* Đăng nhập vào Supabase -> SQL Editor -> Chạy nội dung file `schema.sql` để tạo các bảng và Vector index.

### 4. Thực thi các Module theo Quy trình

#### **Bước 1: Crawl & Sinh dữ liệu Comment (Bài 1)**
```bash
python crawl_comments.py
```

#### **Bước 2: Chạy AI/LLM Phân tích & Trích xuất Insights (Bài 1)**
```bash
python ai_processor.py
```

#### **Bước 3: Mở Dashboard cho BOD (Bài 1)**
```bash
streamlit run dashboard_app.py
```
*Giao diện Dashboard sẽ mở tại `http://localhost:8501`.*

#### **Bước 4: Nạp dữ liệu RAG VIB Max Card (Bài 2)**
```bash
python rag_ingest.py
```

#### **Bước 5: Test Gửi Báo cáo Telegram & Trigger Sale (Bài 1 & 2)**
```bash
python telegram_bot.py
```

---

## 📑 Chi Tiết Bản Kế Hoạch 3 Ngày
Bản kế hoạch chi tiết với luồng trực quan Mermaid Diagram nằm tại artifact:
`brain/9de87542-a48c-4bef-9105-b5522fd4129d/implementation_plan.md`.
