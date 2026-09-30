@echo off
chcp 65001 >nul
echo =========================================================================
echo    🚀 ABF MULTIMODAL CRAWLER & RAG ENGINE - VERCEL DEPLOYMENT
echo =========================================================================
echo.
echo Đang kiểm tra đăng nhập Vercel...
echo Hãy làm theo hướng dẫn trên trình duyệt nếu đây là lần đầu tiên đăng nhập.
echo.

cd /d "%~dp0crawler-rag-app"
call npx vercel --prod

echo.
echo =========================================================================
echo  ✅ Đã hoàn tất lệnh Deploy Vercel!
echo =========================================================================
pause
