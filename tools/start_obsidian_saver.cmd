@echo off
call "%USERPROFILE%\miniconda3\Scripts\activate.bat" "%USERPROFILE%\miniconda3"
call conda activate Steuerung3d
cd /d C:\dev\Steuerung3d_Remake
python chatgpt_active_to_obsidian.py
pause