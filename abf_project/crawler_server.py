# -*- coding: utf-8 -*-
"""
=============================================================================
ABF UNIVERSAL CRAWLER - STANDALONE WEB APPLICATION SERVER (NO STREAMLIT)
-----------------------------------------------------------------------------
- Sử dụng Python Standard HTTP Server kết hợp REST API.
- Tự động mở trình duyệt tại http://127.0.0.1:8000 trong 0.5 giây.
- Giao diện HTML5/CSS3/JavaScript hiện đại, trực quan, mượt mà.
- Hỗ trợ dán link, cào toàn trang, bóc tách ảnh, nút con và lưu vào Supabase.
=============================================================================
"""

import os
import sys
import json
import time
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv
from deep_web_crawler import DeepWebCrawler

load_dotenv()

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# In-memory last crawl result cache
LATEST_CRAWL_RESULT = None
IS_CRAWLING = False

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ABF Universal Deep Web Crawler & Supabase Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0B0F19;
            --surface: #111827;
            --surface-card: #1F2937;
            --border: #374151;
            --primary: #3B82F6;
            --primary-hover: #2563EB;
            --success: #10B981;
            --warning: #F59E0B;
            --danger: #EF4444;
            --text-main: #F9FAFB;
            --text-muted: #9CA3AF;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: var(--bg); color: var(--text-main); min-height: 100vh; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .header h1 { font-size: 22px; font-weight: 800; background: linear-gradient(135deg, #60A5FA, #A78BFA); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .header p { color: var(--text-muted); font-size: 13px; margin-top: 4px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .input-group { display: flex; gap: 12px; margin-top: 12px; }
        input[type="text"] { flex: 1; background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; color: #fff; font-size: 14px; outline: none; }
        input[type="text"]:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2); }
        .btn { background: var(--primary); color: white; border: none; border-radius: 8px; padding: 12px 24px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: 0.2s; }
        .btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .options-row { display: flex; gap: 20px; align-items: center; margin-top: 14px; font-size: 13px; color: var(--text-muted); }
        .options-row label { display: flex; align-items: center; gap: 6px; cursor: pointer; color: var(--text-main); }
        .badge-preset { background: rgba(59, 130, 246, 0.15); color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.3); padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; margin-right: 8px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
        .metric-card { background: var(--surface-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; text-align: center; }
        .metric-val { font-size: 24px; font-weight: 800; color: #fff; margin-top: 4px; }
        .metric-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
        .tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .tab-btn { background: transparent; border: none; color: var(--text-muted); padding: 8px 16px; font-weight: 600; font-size: 13px; border-radius: 6px; cursor: pointer; }
        .tab-btn.active { background: var(--surface-card); color: var(--text-main); border: 1px solid var(--border); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; max-height: 450px; overflow-y: auto; padding: 4px; }
        .image-card { background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 10px; text-align: center; }
        .image-card img { width: 100%; height: 120px; object-fit: contain; background: #000; border-radius: 4px; margin-bottom: 8px; }
        .image-url { font-size: 11px; color: var(--text-muted); word-break: break-all; max-height: 36px; overflow: hidden; }
        .subpage-item { background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-bottom: 12px; }
        .subpage-hdr { display: flex; justify-content: space-between; align-items: center; font-weight: 700; color: #60A5FA; margin-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid var(--border); padding: 8px 10px; text-align: left; }
        th { background: #111827; color: #93C5FD; }
        .status-banner { padding: 14px 18px; border-radius: 8px; font-weight: 600; font-size: 14px; margin-bottom: 16px; display: none; }
        .status-success { background: rgba(16, 185, 129, 0.15); border: 1px solid var(--success); color: #34D399; display: flex; align-items: center; gap: 8px; }
        .status-error { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #F87171; display: flex; align-items: center; gap: 8px; }
        .spinner { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid #3B82F6; border-radius: 50%; width: 18px; height: 18px; animation: spin 0.8s linear infinite; display: none; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🌐 ABF Universal Deep Web Crawler</h1>
                <p>Cuộn toàn trang mượt mà • Click nút con ("Biểu phí & điều kiện", "Bảo hiểm thẻ") • Lưu tự động vào Supabase DB</p>
            </div>
            <div style="text-align: right;">
                <span style="font-size: 11px; color: var(--text-muted);">Database Target:</span>
                <div style="font-size: 12px; font-weight: bold; color: #34D399;">● Supabase: crawled_web_data</div>
            </div>
        </div>

        <!-- Input Box -->
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <label style="font-size: 13px; font-weight: 700; color: var(--text-main);">🔗 Dán đường link website cần cào toàn bộ nội dung:</label>
                <div>
                    <span class="badge-preset" onclick="setPreset('https://www.vpbank.com.vn/')">VPBank Toàn Trang</span>
                    <span class="badge-preset" onclick="setPreset('https://www.vib.com.vn/vn/the-tin-dung')">Thẻ VIB</span>
                    <span class="badge-preset" onclick="setPreset('https://www.vpbank.com.vn/ca-nhan/dich-vu-the')">Thẻ VPBank</span>
                    <span class="badge-preset" onclick="setPreset('https://techcombank.com/khach-hang-ca-nhan/the')">Thẻ Techcombank</span>
                </div>
            </div>
            <div class="input-group">
                <input type="text" id="targetUrl" value="https://www.vpbank.com.vn/" placeholder="https://...">
                <button class="btn" id="crawlBtn" onclick="triggerCrawl()">
                    <div class="spinner" id="btnSpinner"></div>
                    <span id="btnText">🚀 BẮT ĐẦU CRAWL</span>
                </button>
            </div>
            <div class="options-row">
                <label><input type="checkbox" id="saveDb" checked> Tự động lưu vào Supabase DB (Table: crawled_web_data)</label>
                <label><input type="checkbox" id="headless" checked> Chạy ẩn trình duyệt (Headless)</label>
                <label>Số trang tối đa: <input type="number" id="maxSubpages" value="50" min="0" max="2000" style="width: 65px; background: var(--surface-card); color:#fff; border:1px solid var(--border); border-radius:4px; padding:2px 6px; margin-left:4px;"> <span style="font-size: 11px; color: var(--text-muted);">(0 = cào 100% tất cả)</span></label>
            </div>
        </div>

        <!-- Status Banner -->
        <div id="statusBanner" class="status-banner"></div>

        <!-- Metric Cards -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-lbl">Trạng thái</div>
                <div class="metric-val" id="metricStatus" style="color: #60A5FA;">READY</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">Thời gian xử lý</div>
                <div class="metric-val" id="metricDuration">0s</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">Link con đã click</div>
                <div class="metric-val" id="metricSubpages">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">Hình ảnh trích xuất</div>
                <div class="metric-val" id="metricImages">0</div>
            </div>
        </div>

        <!-- Results Tabs -->
        <div class="card">
            <div class="tabs">
                <button class="tab-btn active" onclick="showTab('tabImages', this)">🖼️ Thư viện Ảnh (<span id="countImages">0</span>)</button>
                <button class="tab-btn" onclick="showTab('tabSubpages', this)">📑 Trang con & Biểu phí (<span id="countSubpages">0</span>)</button>
                <button class="tab-btn" onclick="showTab('tabDb', this)">💾 Bản ghi Supabase DB</button>
                <button class="tab-btn" onclick="showTab('tabMain', this)">📜 Toàn văn Trang chính</button>
            </div>

            <!-- Tab 1: Images -->
            <div id="tabImages" class="tab-content active">
                <div class="image-grid" id="imagesContainer">
                    <div style="color: var(--text-muted); font-size: 13px; padding: 20px;">Chưa có dữ liệu. Nhấn "Bắt đầu Crawl" để tải toàn bộ hình ảnh.</div>
                </div>
            </div>

            <!-- Tab 2: Subpages & Fee Tables -->
            <div id="tabSubpages" class="tab-content">
                <div id="subpagesContainer">
                    <div style="color: var(--text-muted); font-size: 13px; padding: 20px;">Chưa có dữ liệu các nút con.</div>
                </div>
            </div>

            <!-- Tab 3: Supabase DB Records -->
            <div id="tabDb" class="tab-content">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="font-size: 13px; color: var(--text-muted);">20 Bản ghi mới nhất trong bảng <code>public.crawled_web_data</code>:</div>
                    <button class="btn" style="padding: 6px 12px; font-size: 12px;" onclick="loadSupabaseRecords()">🔄 Tải lại Supabase</button>
                </div>
                <div id="supabaseTableContainer" style="overflow-x: auto;">
                    <table id="dbTable">
                        <thead>
                            <tr><th>ID</th><th>Tiêu đề</th><th>Loại nội dung</th><th>Nút bấm / Section</th><th>Thời gian cào</th><th>URL Nguồn</th></tr>
                        </thead>
                        <tbody id="dbTableBody">
                            <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Nhấn "Tải lại Supabase" để xem dữ liệu lưu trên Cloud.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Tab 4: Main Page Text -->
            <div id="tabMain" class="tab-content">
                <textarea id="mainPageText" readonly style="width: 100%; height: 350px; background: var(--surface-card); color: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: monospace; font-size: 12px; resize: vertical;" placeholder="Toàn văn trang chính sẽ hiển thị tại đây..."></textarea>
            </div>
        </div>
    </div>

    <script>
        function setPreset(url) {
            document.getElementById('targetUrl').value = url;
        }

        function showTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
            if (tabId === 'tabDb') {
                loadSupabaseRecords();
            }
        }

        async function triggerCrawl() {
            const url = document.getElementById('targetUrl').value.trim();
            const maxSubpagesRaw = document.getElementById('maxSubpages').value;
            const maxSubpages = maxSubpagesRaw !== '' ? parseInt(maxSubpagesRaw) : 50;
            const saveDb = document.getElementById('saveDb').checked;
            const headless = document.getElementById('headless').checked;

            if (!url) {
                alert('Vui lòng nhập URL hợp lệ!');
                return;
            }

            const btn = document.getElementById('crawlBtn');
            const spinner = document.getElementById('btnSpinner');
            const btnText = document.getElementById('btnText');
            const banner = document.getElementById('statusBanner');

            btn.disabled = true;
            spinner.style.display = 'block';
            btnText.innerText = 'Đang cuộn & cào dữ liệu...';
            banner.style.display = 'none';
            document.getElementById('metricStatus').innerText = 'RUNNING';
            document.getElementById('metricStatus').style.color = '#F59E0B';

            try {
                const resp = await fetch('/api/crawl', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: url,
                        max_subpages: maxSubpages,
                        save_to_supabase: saveDb,
                        headless: headless
                    })
                });
                const data = await resp.json();
                renderResults(data);
            } catch (err) {
                banner.className = 'status-banner status-error';
                banner.innerText = '❌ Lỗi kết nối: ' + err.message;
                banner.style.display = 'flex';
                document.getElementById('metricStatus').innerText = 'FAILED';
                document.getElementById('metricStatus').style.color = '#EF4444';
            } finally {
                btn.disabled = false;
                spinner.style.display = 'none';
                btnText.innerText = '🚀 BẮT ĐẦU CRAWL';
            }
        }

        function renderResults(data) {
            const banner = document.getElementById('statusBanner');
            if (data.status === 'SUCCESS') {
                banner.className = 'status-banner status-success';
                banner.innerHTML = `🎉 CRAWL THÀNH CÔNG! Đã bóc tách toàn bộ trang, click ${data.total_subpages_crawled} nút phụ, lấy ${data.total_images_found} hình ảnh và lưu ${data.supabase_records_saved} bản ghi vào Supabase DB!`;
                document.getElementById('metricStatus').innerText = 'SUCCESS';
                document.getElementById('metricStatus').style.color = '#10B981';
            } else {
                banner.className = 'status-banner status-error';
                banner.innerHTML = `❌ CRAWL THẤT BÀI! Lỗi: ${data.error_message || 'Không xác định'}`;
                document.getElementById('metricStatus').innerText = 'FAILED';
                document.getElementById('metricStatus').style.color = '#EF4444';
            }
            banner.style.display = 'flex';

            document.getElementById('metricDuration').innerText = data.duration_seconds + 's';
            document.getElementById('metricSubpages').innerText = data.total_subpages_crawled || 0;
            document.getElementById('metricImages').innerText = data.total_images_found || 0;
            document.getElementById('countImages').innerText = data.total_images_found || 0;
            document.getElementById('countSubpages').innerText = data.total_subpages_crawled || 0;

            // Render Images
            const imgContainer = document.getElementById('imagesContainer');
            imgContainer.innerHTML = '';
            if (data.all_images && data.all_images.length > 0) {
                data.all_images.forEach(img => {
                    const card = document.createElement('div');
                    card.className = 'image-card';
                    card.innerHTML = `
                        <img src="${img.url}" alt="${img.alt || ''}" onerror="this.src='https://via.placeholder.com/200x120?text=Image'">
                        <div style="font-size:11px; font-weight:600; color:#fff; margin-bottom:4px;">${img.alt || 'Hình ảnh'}</div>
                        <div class="image-url">${img.url}</div>
                    `;
                    imgContainer.appendChild(card);
                });
            } else {
                imgContainer.innerHTML = '<div style="color: var(--text-muted); padding:20px;">Không tìm thấy hình ảnh nào.</div>';
            }

            // Render Subpages
            const subContainer = document.getElementById('subpagesContainer');
            subContainer.innerHTML = '';
            if (data.subpages_crawled && data.subpages_crawled.length > 0) {
                data.subpages_crawled.forEach(sp => {
                    const item = document.createElement('div');
                    item.className = 'subpage-item';
                    
                    let tableHtml = '';
                    if (sp.tables && sp.tables.length > 0) {
                        sp.tables.forEach((tbl, tIdx) => {
                            tableHtml += `<strong>Bảng biểu #${tIdx+1}:</strong><table>`;
                            tbl.forEach((row, rIdx) => {
                                tableHtml += '<tr>';
                                row.forEach(cell => {
                                    tableHtml += rIdx === 0 ? `<th>${cell}</th>` : `<td>${cell}</td>`;
                                });
                                tableHtml += '</tr>';
                            });
                            tableHtml += '</table><br>';
                        });
                    }

                    item.innerHTML = `
                        <div class="subpage-hdr">
                            <span>📍 Nút: ${sp.button_text}</span>
                            <span style="font-size:12px; color:var(--text-muted);">${sp.tables_count || 0} bảng biểu • ${sp.images ? sp.images.length : 0} ảnh</span>
                        </div>
                        <div style="font-size:12px; margin-bottom:8px;"><a href="${sp.url}" target="_blank" style="color:#93C5FD;">${sp.url}</a></div>
                        ${tableHtml}
                        <textarea readonly style="width:100%; height:160px; background:#111827; color:#ccc; border:1px solid var(--border); border-radius:4px; font-size:11px; padding:8px;">${sp.markdown || sp.raw_text || ''}</textarea>
                    `;
                    subContainer.appendChild(item);
                });
            } else {
                subContainer.innerHTML = '<div style="color: var(--text-muted); padding:20px;">Không có trang con nào được cào.</div>';
            }

            // Render Main Text
            if (data.main_page && (data.main_page.markdown || data.main_page.raw_text)) {
                document.getElementById('mainPageText').value = data.main_page.markdown || data.main_page.raw_text;
            }
        }

        async function loadSupabaseRecords() {
            const tbody = document.getElementById('dbTableBody');
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Đang tải dữ liệu từ Supabase Cloud...</td></tr>';
            try {
                const resp = await fetch('/api/supabase-records');
                const records = await resp.json();
                if (records && records.length > 0) {
                    tbody.innerHTML = '';
                    records.forEach(r => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><b>#${r.id}</b></td>
                            <td>${r.page_title || 'N/A'}</td>
                            <td><span style="background:#1E3A8A; color:#93C5FD; padding:2px 6px; border-radius:4px;">${r.content_type}</span></td>
                            <td>${r.section_title || '-'}</td>
                            <td>${new Date(r.crawled_at).toLocaleString('vi-VN')}</td>
                            <td><a href="${r.source_url}" target="_blank" style="color:#60A5FA;">Link</a></td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Chưa có bản ghi nào trong bảng.</td></tr>';
                }
            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #EF4444;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
            }
        }

        // Auto load Supabase records on start
        window.addEventListener('DOMContentLoaded', () => {
            loadSupabaseRecords();
        });
    </script>
</body>
</html>
"""

class CrawlerRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
            self._set_headers(200, "text/html; charset=utf-8")
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return
            
        elif parsed.path == "/api/supabase-records":
            try:
                resp = requests.get(
                    f"{SUPABASE_URL}/rest/v1/crawled_web_data?select=id,source_url,page_title,content_type,section_title,crawled_at&order=id.desc&limit=25",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}"
                    },
                    timeout=8
                )
                data = resp.json() if resp.status_code == 200 else []
                self._set_headers(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
            
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"Not Found")

    def do_POST(self):
        global LATEST_CRAWL_RESULT, IS_CRAWLING
        
        if self.path == "/api/crawl":
            if IS_CRAWLING:
                self._set_headers(429)
                self.wfile.write(json.dumps({"status": "FAILED", "error_message": "Đang có tiến trình cào khác đang chạy!"}).encode("utf-8"))
                return
                
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = json.loads(body) if body else {}
            
            target_url = params.get("url", "https://www.vib.com.vn/vn/the-tin-dung")
            max_subpages = int(params.get("max_subpages", 10))
            save_to_supabase = bool(params.get("save_to_supabase", True))
            headless = bool(params.get("headless", True))
            
            IS_CRAWLING = True
            try:
                crawler = DeepWebCrawler(
                    base_url=target_url,
                    output_dir="crawled_data",
                    headless=headless,
                    max_subpages=max_subpages,
                    save_to_supabase=save_to_supabase
                )
                result = crawler.run()
                LATEST_CRAWL_RESULT = result
                
                # Tự động kích hoạt quy trình nạp RAG nếu bật lưu Supabase
                if save_to_supabase:
                    print("\n[*] Tự động kích hoạt quy trình nạp RAG (RAG Ingestion)...", flush=True)
                    try:
                        from process_rag_pipeline import run_rag_ingestion
                        run_rag_ingestion(reset=False)
                        print("[*] Hoàn thành quy trình RAG!", flush=True)
                    except Exception as rag_err:
                        print(f"[!] Lỗi quy trình nạp RAG tự động: {rag_err}", flush=True)
                
                self._set_headers(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"status": "FAILED", "error_message": str(e)}).encode("utf-8"))
            finally:
                IS_CRAWLING = False
            return

def open_browser():
    time.sleep(0.8)
    url = f"http://127.0.0.1:{PORT}"
    print(f"[*] Đang tự động mở trình duyệt: {url}", flush=True)
    webbrowser.open(url)

def main():
    print("=" * 70)
    print("       ABF UNIVERSAL CRAWLER - STANDALONE WEB APPLICATION")
    print("=" * 70)
    print(f"[*] Server Address: http://127.0.0.1:{PORT}")
    print("[*] Tự động kết nối Supabase Cloud Database.")
    print("[*] Để dừng server: Đóng cửa sổ đen này hoặc nhấn Ctrl + C.")
    print("=" * 70)

    threading.Thread(target=open_browser, daemon=True).start()
    
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, CrawlerRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Server đã dừng.")

if __name__ == "__main__":
    main()
