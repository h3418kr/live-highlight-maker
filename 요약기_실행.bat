@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 시스템에 설치된 파이썬으로 요약기 GUI 실행
where pythonw >nul 2>nul && (
    start "" pythonw "%~dp0요약기_gui.py"
    exit /b 0
)
where python >nul 2>nul && (
    start "" python "%~dp0요약기_gui.py"
    exit /b 0
)
echo [오류] 파이썬을 찾을 수 없습니다. https://www.python.org 에서 설치하세요.
pause
