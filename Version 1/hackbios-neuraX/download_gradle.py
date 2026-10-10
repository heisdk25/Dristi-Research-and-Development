import os
import sys
import time
import zipfile
import urllib.request
import shutil

dist_dir = r"E:\Android\GradleHome\wrapper\dists\gradle-8.11.1-bin\bpt9gzteqjrbo1mjrsomdt32c"
os.makedirs(dist_dir, exist_ok=True)
dest_zip = os.path.join(dist_dir, "gradle-8.11.1-bin.zip")
ok_file = os.path.join(dist_dir, "gradle-8.11.1-bin.zip.ok")
lck_file = os.path.join(dist_dir, "gradle-8.11.1-bin.zip.lck")
part_file = os.path.join(dist_dir, "gradle-8.11.1-bin.zip.part")

# Clean lock and part files if present
for f in [lck_file, part_file]:
    if os.path.exists(f):
        try:
            os.remove(f)
        except Exception:
            pass

url = "https://services.gradle.org/distributions/gradle-8.11.1-bin.zip"
print(f"Downloading Gradle 8.11.1 from {url} -> {dest_zip}...")
headers = {"User-Agent": "Mozilla/5.0"}
req = urllib.request.Request(url, headers=headers)

t0 = time.time()
bytes_read = 0
last_print = t0

with urllib.request.urlopen(req, timeout=60) as resp, open(dest_zip, "wb") as out:
    total_size = int(resp.headers.get("Content-Length", 0))
    while chunk := resp.read(1024 * 1024):
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

print(f"[OK] Downloaded Gradle 8.11.1: {bytes_read / (1024 * 1024):.1f} MB in {time.time() - t0:.1f}s", flush=True)

# Extract
print("Extracting Gradle 8.11.1 into wrapper directory...", flush=True)
with zipfile.ZipFile(dest_zip, 'r') as z:
    z.extractall(dist_dir)

# Create .ok marker file for Gradle wrapper
with open(ok_file, "w") as f:
    f.write("")

print(f"[OK] Gradle 8.11.1 provisioned successfully at {dist_dir}!", flush=True)
