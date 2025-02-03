import os
import sys
import subprocess
import requests
import zipfile
import tempfile
import shutil

# URL for FFmpeg essentials build (ffmpeg.exe is inside the ZIP)
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_and_extract_ffmpeg(destination_dir):
    """
    Downloads the FFmpeg essentials ZIP from FFMPEG_ZIP_URL,
    extracts ffmpeg.exe, and places it in destination_dir.

    Returns the full path to ffmpeg.exe if successful.
    """
    try:
        print("Downloading FFmpeg from:", FFMPEG_ZIP_URL)
        response = requests.get(FFMPEG_ZIP_URL, stream=True)
        response.raise_for_status()
        # Write the ZIP to a temporary file.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
            tmp_zip_path = tmp_file.name
        print("Download complete. Extracting ffmpeg.exe...")
        with zipfile.ZipFile(tmp_zip_path, "r") as zip_ref:
            exe_name = None
            # Look for ffmpeg.exe (case-insensitive)
            for name in zip_ref.namelist():
                if name.lower().endswith("ffmpeg.exe"):
                    exe_name = name
                    break
            if exe_name is None:
                raise Exception("ffmpeg.exe not found in the downloaded zip file.")
            # Extract the file to destination_dir.
            zip_ref.extract(exe_name, destination_dir)
            extracted_path = os.path.join(destination_dir, exe_name)
            final_path = os.path.join(destination_dir, "ffmpeg.exe")
            if os.path.abspath(extracted_path) != os.path.abspath(final_path):
                os.makedirs(destination_dir, exist_ok=True)
                shutil.move(extracted_path, final_path)
        os.remove(tmp_zip_path)
        print(f"ffmpeg.exe successfully downloaded and extracted to {final_path}.")
        return final_path
    except Exception as e:
        print(f"Failed to download and extract ffmpeg: {e}")
        raise


def get_ffmpeg_location():
    """
    Determines the availability and location of ffmpeg.exe using these steps:
      1. Check if ffmpeg.exe exists in the current directory (or the PyInstaller bundled folder).
      2. If not, try running 'ffmpeg -version' to see if ffmpeg is available system-wide.
      3. Only if neither is available, download and extract ffmpeg.exe.

    Returns:
      - (True, <directory>) if a local copy is found or was successfully downloaded.
      - (True, "") if a system-installed ffmpeg is available.
      - (False, "") if ffmpeg is not available.
    """
    base_dir = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.abspath(".")
    local_ffmpeg = os.path.join(base_dir, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        print("Found ffmpeg.exe locally in:", base_dir)
        return True, base_dir
    else:
        print("ffmpeg.exe not found locally.")
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            print("System ffmpeg is available.")
            return True, ""
        except Exception:
            print("No system ffmpeg found. Proceeding to download ffmpeg.exe...")
            try:
                download_and_extract_ffmpeg(base_dir)
                if os.path.exists(os.path.join(base_dir, "ffmpeg.exe")):
                    return True, base_dir
                else:
                    return False, ""
            except Exception as e:
                print("Download failed:", e)
                return False, ""


if __name__ == "__main__":
    available, location = get_ffmpeg_location()
    if available:
        if location:
            print(f"FFmpeg is available locally at: {location}")
        else:
            print("FFmpeg is available system-wide.")
    else:
        print("FFmpeg is not available.")
