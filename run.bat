@echo off
title ABF Universal Automation ^& Crawler Control Center v6.0
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
set "ABF_DIR=%ROOT_DIR%abf_project"

:CHECK_ENV
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ===============================================================================
    echo [ERROR] May chua cai dat Python hoac chua them Python vao PATH!
    echo Vui long kiem tra lai cai dat Python tren Windows.
    echo ===============================================================================
    pause
    exit /b 1
)

:MENU
cls
cd /d "%ROOT_DIR%"
set "choice="
echo ===============================================================================
echo            ABF - TRUNG TAM TU DONG HOA VA THU THAP DU LIEU DA KENH
echo                            (ALL-IN-ONE CONTROL CENTER)
echo ===============================================================================
echo.
echo   --- [ A. THU THAP ^& CAO DU LIEU WEBSITE (UNIVERSAL DEEP CRAWLER) ] ---
echo   [1]  Cao toan dien Website bat ky (The a, the p, the em, H1-H6, PDF, Word DOCX)
echo.
echo   --- [ B. THU THAP MANG XA HOI ^& CHAT REALTIME ] ---
echo   [2]  Cao Binh luan TikTok thuc te (Theo URL video / username, luu Supabase)
echo   [3]  Cao Tin nhan ^& Nhom Zalo Realtime 24/7 (Dong bo Supabase DB)
echo.
echo   --- [ C. GIAO DIEN ^& TRUC QUAN HOA DU LIEU (DASHBOARDS) ] ---
echo   [4]  Khoi chay ABF Executive Dashboard Server (Local Port 3000)
echo   [5]  Mo Streamlit Data Analytics Dashboard (crawler_dashboard.py)
echo   [6]  Mo Giao dien Web Crawler Hub (Trinh duyet http://127.0.0.1:8000)
echo.
echo   --- [ D. DEVOPS, PIPELINE ^& TIEN ICH HE THONG ] ---
echo   [7]  Chay RAG Pipeline thu cong (Tao Vector Embeddings nap Supabase DB)
echo   [8]  Mo Ngrok Tunnel cho n8n (Port 5678 - run_ngrok.py)
echo   [9]  Deploy Executive Dashboard len Vercel Production (CI/CD)
echo   [0]  Thoat chuong trinh
echo.
echo ===============================================================================
set /p choice="Nhap lua chon cua ban [0-9]: "
if defined choice set "choice=%choice: =%"

if not defined choice (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! geq 3 exit /b 0
    echo.
    echo [!] Vui long nhap so tu 0 den 9.
    ping 127.0.0.1 -n 2 >nul
    goto MENU
)
set RETRY_COUNT=0

if "%choice%"=="1" goto RUN_UNIVERSAL_CRAWLER
if "%choice%"=="2" goto RUN_TIKTOK
if "%choice%"=="3" goto RUN_ZALO
if "%choice%"=="4" goto RUN_EXEC_DASHBOARD
if "%choice%"=="5" goto RUN_STREAMLIT
if "%choice%"=="6" goto RUN_GUI
if "%choice%"=="7" goto RUN_RAG_ONLY
if "%choice%"=="8" goto RUN_NGROK
if "%choice%"=="9" goto RUN_VERCEL
if "%choice%"=="0" goto EXIT_PROG

echo.
echo [!] Lua chon khong hop le! Vui long chon tu 0 den 9.
ping 127.0.0.1 -n 2 >nul
goto MENU

:: ===============================================================================
:: 1. CAO TOAN DIEN WEBSITE BAT KY (UNIVERSAL DEEP CRAWLER)
:: ===============================================================================
:RUN_UNIVERSAL_CRAWLER
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [1] UNIVERSAL DEEP WEB ^& DOCUMENT CRAWLER (MA NGUON DUY NHAT CHO MOI WEBSITE)
echo       - Tu dong nhan dien Root Domain ^& Subdomains (media., cdn., static.,...)
echo       - Quet 100%% the ^<a^> tren toan bo Menu, Header, Footer va cac trang con
echo       - Tu dong click Accordion, Tab, Dropdown an de lay toan bo noi dung
echo       - Boc tach day du the doan van ^<p^>, in nghieng ^<em/i^>, in dam ^<strong/b^>
echo       - Giu nguyen 100%% the tieu de ^<h1^> den ^<h6^>, code, danh sach, bang bieu
echo       - Tu dong tai ^& bieu mau, bieu phi, hop dong PDF (.pdf), Word (.docx, .doc)
echo       - Tu dong giai ma loi Font tieng Viet ngan hang trong file PDF
echo       - Luu dong thoi JSON, Markdown va Supabase DB (Table: crawled_web_data)
echo ===============================================================================
echo.
echo Goi y nhanh hoac dan bat ky link website nao cua ban:
echo   [1] VIB - The Tin Dung (https://www.vib.com.vn/vn/the-tin-dung)
echo   [2] VPBank - Dich Vu The (https://www.vpbank.com.vn/ca-nhan/dich-vu-the)
echo   [3] Techcombank - The (https://techcombank.com/khach-hang-ca-nhan/the)
echo   [4] TPBank - The Tin Dung (https://tpb.vn/khach-hang-ca-nhan/the-tin-dung)
echo   [5] RCGV - Review The Co Gi Vui (https://rcgv.vn/)
echo.
set "target_url="
set /p target_url="Nhap link website bat ky (hoac go 1-5 theo goi y tren): "
if defined target_url set "target_url=%target_url: =%"

if "%target_url%"=="1" set target_url=https://www.vib.com.vn/vn/the-tin-dung
if "%target_url%"=="2" set target_url=https://www.vpbank.com.vn/ca-nhan/dich-vu-the
if "%target_url%"=="3" set target_url=https://techcombank.com/khach-hang-ca-nhan/the
if "%target_url%"=="4" set target_url=https://tpb.vn/khach-hang-ca-nhan/the-tin-dung
if "%target_url%"=="5" set target_url=https://rcgv.vn/

if not defined target_url (
    echo.
    echo [!] Ban chua nhap URL.
    ping 127.0.0.1 -n 2 >nul
    goto MENU
)

echo.
set /p max_pages="Nhap so luong trang toi da muon cao [Mac dinh 50, nhap 0 de cao TOAN BO 100%%]: "
if "%max_pages%"=="" set max_pages=50

echo.
echo Ban muon chay an trinh duyet (Headless) hay hien trinh duyet?
echo   [1] Hien trinh duyet Chrome (Xem bot tu dong quet, cuon va tai file) [Mac dinh]
echo   [2] An trinh duyet (Chay ngam nhanh hon)
set /p hl_choice="Lua chon [1/2]: "

set HL_FLAG=
if "%hl_choice%"=="2" set HL_FLAG=--headless

echo.
echo Ban co muon tu dong dong bo luu vao Supabase Cloud Database khong?
echo   [1] Co (Luu day du vao bang crawled_web_data de san sang lam RAG) [Mac dinh]
echo   [2] Khong (Chi luu file JSON va Markdown tren may cuc bo)
set /p sb_choice="Lua chon [1/2]: "

set SB_FLAG=
if "%sb_choice%"=="2" set SB_FLAG=--no-supabase

echo.
echo Ban muon chay truc tiep hay Chay An Duoi Nen (Background Process)?
echo   [1] Chay truc tiep tai cua so nay (Theo doi log realtime) [Mac dinh]
echo   [2] Chay an duoi nen (Tu dong an CMD, ghi log ra file crawler_bg.log)
set /p bg_choice="Lua chon [1/2]: "

if "%bg_choice%"=="2" (
    echo.
    echo ===============================================================================
    echo [*] Dang khoi dong Crawler chay an duoi nen (Background Daemon)...
    echo [*] File log tien do: "%ABF_DIR%\crawler_bg.log"
    echo [*] Tinh nang Chong Sleep: TU DONG KICH HOAT (May khong tu dong ngu)
    echo [*] Luu tru Realtime: Da bat (Cap nhat Supabase va may tinh tung giay)
    echo ===============================================================================
    powershell -NoProfile -Command "Start-Process python -ArgumentList 'deep_web_crawler.py --url \"%target_url%\" --max-subpages %max_pages% %HL_FLAG% %SB_FLAG%' -WorkingDirectory '%ABF_DIR%' -WindowStyle Hidden -RedirectStandardOutput '%ABF_DIR%\crawler_bg.log' -RedirectStandardError '%ABF_DIR%\crawler_err.log'"
    echo.
    echo [V] DA KHOI DONG TIEN TRINH CHAY NGAM THANH CONG!
    echo     Ban co the dong cua so nay hoac lam viec khac.
    echo.
    pause
    goto MENU
)

echo.
echo ===============================================================================
echo Dang khoi dong Universal Deep Crawler: %target_url%
echo (Gioi han: %max_pages% trang/tai lieu)...
echo ===============================================================================
python deep_web_crawler.py --url "%target_url%" --max-subpages %max_pages% %HL_FLAG% %SB_FLAG%
call :ASK_RAG
pause
goto MENU

:: ===============================================================================
:: 2. CAO TIKTOK COMMENTS
:: ===============================================================================
:RUN_TIKTOK
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [2] CAO COMMENT TIKTOK THUC TE VA LUU SUPABASE
echo ===============================================================================
echo.
set /p tiktok_target="Nhap link video hoac username TikTok [Mac dinh: https://www.tiktok.com/@baothetindung.abf]: "
if "%tiktok_target%"=="" set tiktok_target=https://www.tiktok.com/@baothetindung.abf

set /p tiktok_limit="So comment muon cao [Mac dinh: 30]: "
if "%tiktok_limit%"=="" set tiktok_limit=30

echo.
echo Dang cao binh luan tu: %tiktok_target% ...
python crawl_tiktok_n8n.py --target "%tiktok_target%" --limit %tiktok_limit%
echo.
pause
goto MENU

:: ===============================================================================
:: 3. CAO ZALO REALTIME
:: ===============================================================================
:RUN_ZALO
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [3] DANG KHOI DONG HE THONG CAO ZALO REALTIME 24/7...
echo ===============================================================================
echo.
echo  - Che do: Tu dong cuon 100 lan [cho 10-15s moi lan] lay lich su
echo  - Chuyen tiep: Lang nghe Realtime 24/7 cac tin nhan moi
echo  - Luu tru: Dong bo truc tiep vao Supabase DB
echo.
REM Tu dong don dep Chromium bi treo neu co
powershell -NoProfile -Command "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force" >nul 2>&1

REM Kiem tra cac thu vien can thiet
echo [*] Dang kiem tra moi truong thu vien Playwright ^& Requests...
python -c "import playwright, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Dang cai dat thu vien con thieu...
    pip install playwright requests
    playwright install chromium
)

echo [*] Dang khoi dong Zalo Crawler...
echo.
python zalo_crawler.py
echo.
echo ===============================================================================
echo  Chuong trinh Zalo da ket thuc hoac da dung.
echo ===============================================================================
pause
goto MENU

:: ===============================================================================
:: 4. EXECUTIVE DASHBOARD SERVER (PORT 3000)
:: ===============================================================================
:RUN_EXEC_DASHBOARD
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [4] ABF EXECUTIVE DASHBOARD (CHAY DOC LAP - PORT 3000)
echo ===============================================================================
echo.
REM Giai phong cong 3000 neu truoc do co tien trinh chay ngam
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

python serve.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Khong the chay server bang serve.py. Thu chay che do du phong...
    start http://127.0.0.1:3000
    python -m http.server 3000 --bind 127.0.0.1
)
pause
goto MENU

:: ===============================================================================
:: 5. STREAMLIT DATA DASHBOARD
:: ===============================================================================
:RUN_STREAMLIT
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [5] DANG KHOI DONG DASHBOARD STREAMLIT...
echo ===============================================================================
echo.
streamlit run crawler_dashboard.py
pause
goto MENU

:: ===============================================================================
:: 6. GIAO DIEN WEB CRAWLER HUB (PORT 8000)
:: ===============================================================================
:RUN_GUI
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [6] DANG KHOI DONG GIAO DIEN WEB CRAWLER TAI http://127.0.0.1:8000
echo ===============================================================================
echo.
start http://127.0.0.1:8000
python crawler_server.py
echo.
pause
goto MENU

:: ===============================================================================
:: 7. CHAY RAG PIPELINE THU CONG
:: ===============================================================================
:RUN_RAG_ONLY
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [7] DANG TIEN HANH XU LY RAG PIPELINE ^& EMBEDDING VECTOR...
echo ===============================================================================
echo.
python process_rag_pipeline.py
echo.
echo [V] Da hoan tat nap du lieu Vector vao Supabase!
pause
goto MENU

:: ===============================================================================
:: 8. NGROK TUNNEL CHO N8N (PORT 5678)
:: ===============================================================================
:RUN_NGROK
cls
cd /d "%ROOT_DIR%"
echo ===============================================================================
echo   [8] KHOI DONG NGROK TUNNEL CHO N8N (PORT 5678)
echo ===============================================================================
echo.
python run_ngrok.py 5678
pause
goto MENU

:: ===============================================================================
:: 9. DEPLOY VERCEL (CI/CD)
:: ===============================================================================
:RUN_VERCEL
cls
cd /d "%ABF_DIR%"
echo ===============================================================================
echo   [9] ABF EXECUTIVE DASHBOARD - INSTANT CI/CD DEPLOY (VERCEL)
echo ===============================================================================
echo Dang cap nhat code va deploy truc tiep len Production:
echo https://abf-executive-dashboard.vercel.app/
echo -------------------------------------------------------------------------------
call npx vercel --prod --yes
echo -------------------------------------------------------------------------------
echo [V] DEPLOY HOAN TAT!
pause
goto MENU

:: ===============================================================================
:: HAM HOI DONG BO RAG PIPELINE
:: ===============================================================================
:ASK_RAG
echo.
echo -------------------------------------------------------------------------------
set /p do_rag="Ban co muon chay tiep RAG Pipeline de tao Vector Knowledge Base khong? (Y/N) [Mac dinh Y]: "
if /i "%do_rag%"=="N" (
    echo [i] Da bo qua buoc RAG Vector. Du lieu tho da luu tai Supabase 'crawled_web_data'.
    goto :eof
)
echo.
echo [*] Dang khoi dong RAG Pipeline...
cd /d "%ABF_DIR%"
python process_rag_pipeline.py
goto :eof

:EXIT_PROG
echo.
echo Cam on ban da su dung ABF Universal Automation Control Center!
exit /b 0
