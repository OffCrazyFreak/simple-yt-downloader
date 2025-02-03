@echo off
REM Check if ffmpeg.exe exists in the current directory.
if not exist "ffmpeg.exe" (
    echo ffmpeg.exe not found. Forcing download...
    python ffmpeg_manager.py --force
)

REM Build the executable with PyInstaller, bundling ffmpeg.exe, icon.png, and ffmpeg_manager.py.
pyinstaller --onefile --windowed --hidden-import ffmpeg_manager --add-data "ffmpeg.exe;." --add-data "icon.png;." yt_downloader.py

echo Build complete.