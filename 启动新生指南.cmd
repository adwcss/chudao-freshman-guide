@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 goto try_py
python -X utf8 -S run.py
goto done
:try_py
where py >nul 2>nul
if errorlevel 1 goto missing
py -3 -X utf8 -S run.py
goto done
:missing
echo 未找到 Python。请先安装 Python 3.10 或更新版本，并添加到 PATH。
echo 详细说明见当前目录的 README.md。
:done
pause
