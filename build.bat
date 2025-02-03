@echo off
REM Run PyInstaller to build the executable.
pyinstaller --onefile --windowed --add-data "ffmpeg.exe;." yt_downloader.py

REM Remove the temporary build folder.
if exist build (
    rmdir /s /q build
    echo Build folder removed.
)

REM Remove the .spec file.
if exist yt_downloader.spec (
    del /q yt_downloader.spec
    echo Spec file removed.
)

echo Build complete.
