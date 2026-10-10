import os
import sys
import time
import zipfile
import hashlib
import urllib.request
import shutil

STUDIO_DIR = r"E:\DevTools\AndroidStudio"
SETUP_LOGS = r"E:\Android\SetupLogs"
ZIP_NAME = "android-studio-rabbit1-windows.zip"
ZIP_PATH = os.path.join(SETUP_LOGS, ZIP_NAME)
URL = "https://edgedl.me.gvt1.com/android/studio/ide-zips/2026.2.1.8/android-studio-rabbit1-windows.zip"
EXPECTED_SHA256 = "6e83e7ce3e0a76c4e8e78d98eb5ef538cbc9fb386c745bda425fc0bacb9de6d4"

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(2 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest().lower()

def download():
    if os.path.exists(ZIP_PATH):
        print(f"Checking existing zip: {ZIP_PATH}...")
        cur_sha = sha256_file(ZIP_PATH)
        if cur_sha == EXPECTED_SHA256:
            print(f"[OK] Checksum verified for existing file: {cur_sha}")
            return
        else:
            print(f"[WARN] Incomplete or mismatched zip ({cur_sha} != {EXPECTED_SHA256}), re-downloading...")
            os.remove(ZIP_PATH)

    print(f"Downloading Android Studio from {URL}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(URL, headers=headers)
    t0 = time.time()
    last_print = t0
    bytes_read = 0

    with urllib.request.urlopen(req, timeout=120) as resp, open(ZIP_PATH, "wb") as out:
        total_size = int(resp.headers.get("Content-Length", 0))
        while chunk := resp.read(2 * 1024 * 1024):
            out.write(chunk)
            bytes_read += len(chunk)
            now = time.time()
            if now - last_print >= 5:
                mb = bytes_read / (1024 * 1024)
                total_mb = total_size / (1024 * 1024) if total_size else 0
                pct = (bytes_read / total_size * 100) if total_size else 0
                speed = mb / (now - t0)
                print(f"  Downloaded: {mb:.1f} MB / {total_mb:.1f} MB ({pct:.1f}%) at {speed:.2f} MB/s", flush=True)
                last_print = now

    elapsed = time.time() - t0
    print(f"[OK] Download completed: {bytes_read / (1024 * 1024):.1f} MB in {elapsed:.1f}s", flush=True)
    actual_sha = sha256_file(ZIP_PATH)
    if actual_sha != EXPECTED_SHA256:
        raise ValueError(f"Checksum mismatch! Expected {EXPECTED_SHA256}, got {actual_sha}")
    print(f"[PASS] Checksum verified: {actual_sha}", flush=True)

def extract():
    studio_exe = os.path.join(STUDIO_DIR, "bin", "studio64.exe")
    if os.path.exists(studio_exe):
        print(f"[OK] Android Studio already installed at {STUDIO_DIR}", flush=True)
        return

    print(f"Extracting Android Studio to {STUDIO_DIR}...", flush=True)
    temp_dir = os.path.join(SETUP_LOGS, "studio_temp")
    os.makedirs(temp_dir, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        z.extractall(temp_dir)

    subdirs = [os.path.join(temp_dir, d) for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
    src = subdirs[0] if subdirs and os.path.exists(os.path.join(subdirs[0], "bin", "studio64.exe")) else temp_dir

    if os.path.exists(STUDIO_DIR):
        shutil.rmtree(STUDIO_DIR)
    shutil.move(src, STUDIO_DIR)
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"[OK] Android Studio extracted successfully to {STUDIO_DIR}", flush=True)

if __name__ == "__main__":
    download()
    extract()
    studio_exe = os.path.join(STUDIO_DIR, "bin", "studio64.exe")
    print(f"studio64.exe exists: {os.path.exists(studio_exe)}", flush=True)
