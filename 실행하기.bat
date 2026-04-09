@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   좋은생각 굿즈 워크 스테이션
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 패키지 설치중... 잠시 기다려주세요...
pip install flask flask-login flask-sqlalchemy werkzeug pdfplumber --quiet 2>nul
if errorlevel 1 (
    echo pip가 안 되면 아래로 시도합니다...
    python -m pip install flask flask-login flask-sqlalchemy werkzeug pdfplumber --quiet
)
echo      설치 완료!
echo.
echo [2/2] 서버를 시작합니다!
echo.
echo ==========================================
echo.
echo   3초 후 브라우저가 자동으로 열립니다.
echo   아래 주소로 접속하세요:
echo.
echo   http://127.0.0.1:5000
echo.
echo   로그인 아이디: director
echo   비밀번호: 1234
echo.
echo   !! 이 검은 창은 닫지 마세요 !!
echo.
echo ==========================================
echo.

start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"
python app.py

pause
