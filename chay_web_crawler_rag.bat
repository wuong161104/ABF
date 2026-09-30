@echo off
chcp 65001 >nul
echo =========================================================================
echo    🚀 KHỞI ĐỘNG HỆ THỐNG CRAWLER & MULTIMODAL RAG (LOCAL SERVER)
echo =========================================================================
echo.
echo Địa chỉ truy cập: http://localhost:3000
echo CSDL: Supabase (Table: public.documents - Vector 3072D)
echo AI: Google Gemini Multimodal Vision & Embeddings
echo.

cd /d "%~dp0crawler-rag-app"
start "" http://localhost:3000
call npm run start -p 3000

pause
