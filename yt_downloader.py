import subprocess
import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure that the yt-dlp module is installed.
def install_if_missing(package, package_name=None):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or package])

install_if_missing("yt_dlp", "yt-dlp")

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
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        return False

# --- Helper Functions ---

def get_video_urls(playlist_url):
    """
    Uses yt-dlp to fetch a flat JSON of the playlist and returns a list of video URLs.
    """
    try:
        command = [sys.executable, "-m", "yt_dlp", '--flat-playlist', '-J', playlist_url]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video_urls = []
        for entry in data.get('entries', []):
            video_id = entry.get('id')
            if video_id:
                video_urls.append(f"https://www.youtube.com/watch?v={video_id}")
        return video_urls
    except Exception as e:
        messagebox.showerror("Error", f"Error retrieving playlist videos:\n{e}")
        return []

def download_video(url, download_path, status_callback):
    """
    Downloads a single video as MP4 using yt-dlp.
    """
    try:
        format_selector = "bestvideo[ext=mp4]+bestaudio/best"
        available, ffmpeg_loc = get_ffmpeg_location()
        command = [
            sys.executable, "-m", "yt_dlp",
            '--newline',
            '-f', format_selector,
            '-o', os.path.join(download_path, '%(title)s.%(ext)s'),
            '--merge-output-format', 'mp4'
        ]
        if ffmpeg_loc:
            command.extend(['--ffmpeg-location', ffmpeg_loc])
        command.append(url)
        
        status_callback(f"Starting video download: {url}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, creationflags=creation_flags)
        for line in process.stdout:
            print(line.strip())
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
    """
    try:
        available, ffmpeg_loc = get_ffmpeg_location()
        command = [
            sys.executable, "-m", "yt_dlp",
            '--newline',
            '--extract-audio',
            '--audio-format', 'mp3',
            '-o', os.path.join(download_path, '%(title)s.%(ext)s')
        ]
        if ffmpeg_loc:
            command.extend(['--ffmpeg-location', ffmpeg_loc])
        command.append(url)
        
        status_callback(f"Starting audio download: {url}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, creationflags=creation_flags)
        for line in process.stdout:
            print(line.strip())
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

def download_playlist_concurrently(video_urls, download_path, download_func, status_callback):
    total_videos = len(video_urls)
    completed = 0
    max_workers = os.cpu_count() or 4
    status_callback(f"Found {total_videos} items. Using {max_workers} threads...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(download_func, url, download_path, status_callback): url for url in video_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception as exc:
                status_callback(f"Exception for {url}: {exc}")
            with progress_lock:
                completed += 1
                status_callback(f"Downloaded {completed}/{total_videos}")
    status_callback("Playlist download completed!")

def process_video_download(url, download_path, status_callback):
    if "playlist" in url.lower():
        status_callback("Fetching playlist information...")
        video_urls = get_video_urls(url)
        if not video_urls:
            status_callback("No videos found in playlist.")
            return
        download_playlist_concurrently(video_urls, download_path, download_video, status_callback)
    else:
        download_video(url, download_path, status_callback)

def process_audio_download(url, download_path, status_callback):
    if "playlist" in url.lower():
        status_callback("Fetching playlist information...")
        video_urls = get_video_urls(url)
        if not video_urls:
            status_callback("No videos found in playlist.")
            return
        download_playlist_concurrently(video_urls, download_path, download_audio, status_callback)
    else:
        download_audio(url, download_path, status_callback)

# --- GUI Setup with Notebook (Tabs) ---

root = tk.Tk()
root.title("YouTube Downloader (Video & Audio)")
root.geometry("500x200")
root.resizable(False, False)

notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill='both', padx=10, pady=10)

# Video Tab
video_frame = ttk.Frame(notebook, padding=10)
notebook.add(video_frame, text="Video")

video_url_label = ttk.Label(video_frame, text="YouTube URL:")
video_url_label.pack(anchor="w", pady=(0, 5))

video_url_entry = ttk.Entry(video_frame, width=80)
video_url_entry.pack(anchor="w", pady=(0, 10))
video_url_entry.focus()

video_status = tk.StringVar(value="Enter a URL and click Download.")
video_status_label = ttk.Label(video_frame, textvariable=video_status, foreground="blue")
video_status_label.pack(anchor="w", pady=(10, 0))

def update_video_status(message):
    root.after(0, video_status.set, message)

def start_video_download():
    available, ffmpeg_loc = get_ffmpeg_location()
    if not available:
        base_dir = os.path.abspath(".")
        try:
            download_and_extract_ffmpeg(base_dir)
        except Exception as e:
            messagebox.showerror("FFmpeg Not Found",
                                 f"FFmpeg is not available and could not be downloaded automatically.\n{e}")
            return
        available, ffmpeg_loc = get_ffmpeg_location()
        if not available:
            messagebox.showerror("FFmpeg Not Found",
                                 "FFmpeg is still not available after attempting to download it. "
                                 "Please install FFmpeg manually or ensure it's in your PATH.")
            return
    url = video_url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Needed", "Please enter a YouTube URL for Video.")
        return
    download_path = filedialog.askdirectory(title="Select Download Folder for Video")
    if not download_path:
        return
    threading.Thread(
        target=process_video_download, args=(url, download_path, update_video_status), daemon=True
    ).start()

video_download_button = ttk.Button(video_frame, text="Download Video", command=start_video_download)
video_download_button.pack(pady=(0, 10))

# Audio Tab
audio_frame = ttk.Frame(notebook, padding=10)
notebook.add(audio_frame, text="Audio")

audio_url_label = ttk.Label(audio_frame, text="YouTube URL:")
audio_url_label.pack(anchor="w", pady=(0, 5))

audio_url_entry = ttk.Entry(audio_frame, width=80)
audio_url_entry.pack(anchor="w", pady=(0, 10))
audio_url_entry.focus()

audio_status = tk.StringVar(value="Enter a URL and click Download.")
audio_status_label = ttk.Label(audio_frame, textvariable=audio_status, foreground="blue")
audio_status_label.pack(anchor="w", pady=(10, 0))

def update_audio_status(message):
    root.after(0, audio_status.set, message)

def start_audio_download():
    available, ffmpeg_loc = get_ffmpeg_location()
    if not available:
        base_dir = os.path.abspath(".")
        try:
            download_and_extract_ffmpeg(base_dir)
        except Exception as e:
            messagebox.showerror("FFmpeg Not Found",
                                 f"FFmpeg is not available and could not be downloaded automatically.\n{e}")
            return
        available, ffmpeg_loc = get_ffmpeg_location()
        if not available:
            messagebox.showerror("FFmpeg Not Found",
                                 "FFmpeg is still not available after attempting to download it. "
                                 "Please install FFmpeg manually or ensure it's in your PATH.")
            return
    url = audio_url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Needed", "Please enter a YouTube URL for Audio.")
        return
    download_path = filedialog.askdirectory(title="Select Download Folder for Audio")
    if not download_path:
        return
    threading.Thread(
        target=process_audio_download, args=(url, download_path, update_audio_status), daemon=True
    ).start()

audio_download_button = ttk.Button(audio_frame, text="Download Audio", command=start_audio_download)
audio_download_button.pack(pady=(0, 10))

root.mainloop()
