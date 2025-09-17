@echo off
setlocal
taskkill /f /im chrome.exe
python ".\applyBot.py" skip