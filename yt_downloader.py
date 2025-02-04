import subprocess
import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import ffmpeg management functions from ffmpeg_manager.py
from ffmpeg_manager import get_ffmpeg_location, download_and_extract_ffmpeg

# Set creation flags for subprocesses.
if os.name == "nt":
    creation_flags = subprocess.CREATE_NO_WINDOW
else:
    creation_flags = 0


def check_ffmpeg_availability():
    """
    Checks whether FFmpeg is available by running 'ffmpeg -version'.
    Returns True if available, False otherwise.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except Exception:
        return False


# --- Global Cache for FFmpeg ---
# FFMPEG_CACHE is a tuple: (available, ffmpeg_path)
FFMPEG_CACHE = get_ffmpeg_location()

# --- Helper Functions ---


def get_video_urls(playlist_url):
    """
    Uses yt-dlp to fetch a flat JSON of the playlist and returns a list of video URLs.
    """
    try:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--flat-playlist",
            "-J",
            playlist_url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video_urls = []
        for entry in data.get("entries", []):
            video_id = entry.get("id")
            if video_id:
                video_urls.append(f"https://www.youtube.com/watch?v={video_id}")
        return video_urls
    except Exception as e:
        update_status(f"Error retrieving playlist videos: {e}")
        return []


def download_video(url, download_path, status_callback):
    """
    Downloads a single video as MP4 using yt-dlp.
    Only key messages (starting, completed, errors, and postprocessing) are sent to the GUI.
    Other progress details (like percentages or speeds) are printed only to the console.
    """
    try:
        format_selector = "bestvideo[ext=mp4]+bestaudio/best"
        # Use the cached ffmpeg info.
        global FFMPEG_CACHE
        available, ffmpeg_loc = FFMPEG_CACHE
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--newline",
            "-f",
            format_selector,
            "-o",
            os.path.join(download_path, "%(title)s.%(ext)s"),
            "--merge-output-format",
            "mp4",
        ]
        if ffmpeg_loc:
            command.extend(["--ffmpeg-location", ffmpeg_loc])
        command.append(url)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags,
        )
        postprocessing_reported = False
        # Read subprocess output line by line.
        for line in process.stdout:
            stripped = line.strip()
            print(stripped)  # Always print to console.
            lower = stripped.lower()
            if "%" in stripped or "speed" in lower or "ios player" in lower:
                continue
            if (
                "merg" in lower or "postprocess" in lower
            ) and not postprocessing_reported:
                status_callback("Postprocessing downloads")
                postprocessing_reported = True
        process.wait()
        if process.returncode == 0:
            status_callback(f"Completed video: {url}")
            return True
        else:
            status_callback(f"Error downloading video: {url}")
            return False
    except Exception as e:
        status_callback(f"Exception downloading video: {url}\n{e}")
        return False


def download_audio(url, download_path, status_callback):
    """
    Downloads a single video and extracts its audio as an MP3 using yt-dlp.
    Only key messages are sent to the GUI; detailed progress is logged to the console.
    """
    try:
        global FFMPEG_CACHE
        available, ffmpeg_loc = FFMPEG_CACHE
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--newline",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "-o",
            os.path.join(download_path, "%(title)s.%(ext)s"),
        ]
        if ffmpeg_loc:
            command.extend(["--ffmpeg-location", ffmpeg_loc])
        command.append(url)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags,
        )
        postprocessing_reported = False
        for line in process.stdout:
            stripped = line.strip()
            print(stripped)
            lower = stripped.lower()
            if "%" in stripped or "speed" in lower or "ios player" in lower:
                continue
            if (
                "merg" in lower or "postprocess" in lower
            ) and not postprocessing_reported:
                status_callback("Postprocessing downloads")
                postprocessing_reported = True
        process.wait()
        if process.returncode == 0:
            status_callback(f"Completed audio: {url}")
            return True
        else:
            status_callback(f"Error downloading audio: {url}")
            return False
    except Exception as e:
        status_callback(f"Exception downloading audio: {url}\n{e}")
        return False


progress_lock = threading.Lock()


def download_playlist_concurrently(
    video_urls, download_path, download_func, status_callback
):
    total_videos = len(video_urls)
    completed = 0
    max_workers = os.cpu_count() or 4
    status_callback(f"Found {total_videos} items. Using {max_workers} threads...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(download_func, url, download_path, status_callback): url
            for url in video_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception as exc:
                status_callback(f"Exception for {url}: {exc}")
            with progress_lock:
                completed += 1
                status_callback(f"Downloads completed {completed}/{total_videos}")
    status_callback("Playlist download completed!")


def process_video_download(url, download_path, status_callback):
    if "playlist" in url.lower():
        status_callback("Fetching playlist information...")
        video_urls = get_video_urls(url)
        if not video_urls:
            status_callback("No videos found in playlist.")
            return
        download_playlist_concurrently(
            video_urls, download_path, download_video, status_callback
        )
    else:
        download_video(url, download_path, status_callback)


def process_audio_download(url, download_path, status_callback):
    if "playlist" in url.lower():
        status_callback("Fetching playlist information...")
        video_urls = get_video_urls(url)
        if not video_urls:
            status_callback("No videos found in playlist.")
            return
        download_playlist_concurrently(
            video_urls, download_path, download_audio, status_callback
        )
    else:
        download_audio(url, download_path, status_callback)


# --- GUI Setup ---


def update_status(message):
    status_var.set(f"Status: {message}")


root = tk.Tk()
if os.path.exists("icon.ico"):
    root.iconbitmap("icon.ico")
root.title("Simple YT downloader (by CrazyFreak)")
root.geometry("500x150")
root.resizable(False, False)

# Create a main container frame with 10px padding on left and right.
main_frame = ttk.Frame(root, padding=(10, 0))
main_frame.pack(expand=True, fill="both")

# Frame for URL input with label.
input_frame = ttk.Frame(main_frame)
input_frame.pack(pady=(10, 5))
url_label = ttk.Label(input_frame, text="YouTube URL:")
url_label.pack(side="left", padx=(0, 5))
url_entry = ttk.Entry(input_frame, width=80)
url_entry.pack(side="left")
url_entry.focus()

# --- Destination Folder Input ---
destination_frame = ttk.Frame(main_frame)
destination_frame.pack(pady=(0, 10))
dest_label = ttk.Label(destination_frame, text="Destination folder:")
dest_label.pack(side="left", padx=(0, 5))
# Default to the Downloads folder.
default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
dest_var = tk.StringVar(value=default_downloads)
destination_entry = ttk.Entry(destination_frame, textvariable=dest_var, width=50)
destination_entry.pack(side="left", padx=(0, 5))


def browse_folder():
    folder = filedialog.askdirectory(title="Select Download Folder")
    if folder:
        dest_var.set(folder)


browse_button = ttk.Button(destination_frame, text="Browse", command=browse_folder)
browse_button.pack(side="left")

# Frame for buttons.
button_frame = ttk.Frame(main_frame)
button_frame.pack(pady=5)


def start_video_download():
    global FFMPEG_CACHE
    available, ffmpeg_loc = FFMPEG_CACHE
    if not available:
        base_dir = os.path.abspath(".")
        update_status("FFmpeg not found locally/system-wide. Downloading FFmpeg...")
        try:
            download_and_extract_ffmpeg(base_dir)
        except Exception as e:
            messagebox.showerror(
                "FFmpeg Not Found",
                f"FFmpeg could not be downloaded automatically.\n{e}",
            )
            update_status("FFmpeg download failed.")
            return
        FFMPEG_CACHE = get_ffmpeg_location()
        available, ffmpeg_loc = FFMPEG_CACHE
        if not available:
            messagebox.showerror(
                "FFmpeg Not Found",
                "FFmpeg is still not available after attempting to download it.",
            )
            update_status("FFmpeg still not available.")
            return

    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Needed", "Please enter a YouTube URL.")
        return

    download_path = dest_var.get().strip()
    if not download_path or not os.path.isdir(download_path):
        messagebox.showwarning("Input Needed", "Please enter a valid download folder.")
        return

    threading.Thread(
        target=process_video_download,
        args=(url, download_path, update_status),
        daemon=True,
    ).start()


def start_audio_download():
    global FFMPEG_CACHE
    available, ffmpeg_loc = FFMPEG_CACHE
    if not available:
        base_dir = os.path.abspath(".")
        update_status("FFmpeg not found locally/system-wide. Downloading FFmpeg...")
        try:
            download_and_extract_ffmpeg(base_dir)
        except Exception as e:
            messagebox.showerror(
                "FFmpeg Not Found",
                f"FFmpeg could not be downloaded automatically.\n{e}",
            )
            update_status("FFmpeg download failed.")
            return
        FFMPEG_CACHE = get_ffmpeg_location()
        available, ffmpeg_loc = FFMPEG_CACHE
        if not available:
            messagebox.showerror(
                "FFmpeg Not Found",
                "FFmpeg is still not available after attempting to download it.",
            )
            update_status("FFmpeg still not available.")
            return

    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Needed", "Please enter a YouTube URL.")
        return

    download_path = dest_var.get().strip()
    if not download_path or not os.path.isdir(download_path):
        messagebox.showwarning("Input Needed", "Please enter a valid download folder.")
        return

    threading.Thread(
        target=process_audio_download,
        args=(url, download_path, update_status),
        daemon=True,
    ).start()


video_button = ttk.Button(
    button_frame, text="Download Video", command=start_video_download
)
video_button.pack(side="left", padx=5)
audio_button = ttk.Button(
    button_frame, text="Download Audio", command=start_audio_download
)
audio_button.pack(side="left", padx=5)

# Status label.
status_var = tk.StringVar(value="Enter YouTube URL")
status_label = ttk.Label(main_frame, textvariable=status_var, foreground="blue")
status_label.pack(pady=(10, 0))

root.mainloop()
