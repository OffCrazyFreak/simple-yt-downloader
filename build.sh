#!/bin/bash
# Run PyInstaller to build the executable.
pyinstaller --onefile --windowed --add-data "ffmpeg.exe:." yt_downloader.py

# Remove the temporary build folder.
if [ -d "build" ]; then
    rm -rf build
    echo "Build folder removed."
fi

# Remove the .spec file.
if [ -f "yt_downloader.spec" ]; then
    rm -f yt_downloader.spec
    echo "Spec file removed."
fi

echo "Build complete."
