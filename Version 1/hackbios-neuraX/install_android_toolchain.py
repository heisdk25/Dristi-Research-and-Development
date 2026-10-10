import os
import sys
import time
import shutil
import zipfile
import hashlib
import urllib.request
import subprocess

# Directories
STUDIO_DIR = r"E:\DevTools\AndroidStudio"
JDK_DIR = r"E:\DevTools\Java\jdk-17"
SDK_DIR = r"E:\Android\Sdk"
GRADLE_HOME = r"E:\Android\GradleHome"
ANDROID_USER_HOME = r"E:\Android\UserHome"
SETUP_LOGS = r"E:\Android\SetupLogs"

# URLs and Checksums
JDK_URL = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip"
JDK_SHA256 = "e53a79c3c3d86865bd7e787903884331068e71321714ffd44f145785affc7cb0"
JDK_ZIP_NAME = "OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip"

STUDIO_URL = "https://edgedl.me.gvt1.com/android/studio/ide-zips/2026.2.1.8/android-studio-rabbit1-windows.zip"
STUDIO_SHA256 = "6e83e7ce3e0a76c4e8e78d98eb5ef538cbc9fb386c745bda425fc0bacb9de6d4"
STUDIO_ZIP_NAME = "android-studio-rabbit1-windows.zip"

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest().lower()

def download_with_progress(url, dest_path, expected_sha256):
    if os.path.exists(dest_path):
        print(f"Checking existing file: {dest_path}...")
        existing_sha = sha256_file(dest_path)
        if existing_sha == expected_sha256.lower():
            print(f"[OK] File already exists and checksum matches: {dest_path}")
            return dest_path
        else:
            print(f"[WARN] Checksum mismatch on existing file ({existing_sha} != {expected_sha256}), re-downloading...")
            os.remove(dest_path)

    print(f"Downloading {url} -> {dest_path}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    
    t0 = time.time()
    last_print = t0
    bytes_read = 0
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, "wb") as out:
        total_size = int(resp.headers.get("Content-Length", 0))
        while chunk := resp.read(1024 * 1024): # 1MB chunks
            out.write(chunk)
            bytes_read += len(chunk)
            now = time.time()
            if now - last_print > 5: # Log every 5 seconds
                mb = bytes_read / (1024 * 1024)
                total_mb = total_size / (1024 * 1024) if total_size else 0
                pct = (bytes_read / total_size * 100) if total_size else 0
                elapsed = now - t0
                speed = mb / elapsed if elapsed > 0 else 0
                print(f"  Downloaded: {mb:.1f} MB / {total_mb:.1f} MB ({pct:.1f}%) at {speed:.2f} MB/s")
                last_print = now

    elapsed = time.time() - t0
    print(f"[OK] Download completed: {bytes_read / (1024 * 1024):.1f} MB in {elapsed:.1f}s")

    print(f"Verifying SHA-256 checksum...")
    actual_sha = sha256_file(dest_path)
    if actual_sha != expected_sha256.lower():
        raise ValueError(f"Checksum mismatch! Expected {expected_sha256}, got {actual_sha}")
    print(f"[PASS] Checksum verified: {actual_sha}")
    return dest_path

def set_user_env_var(name, value):
    ps_cmd = f'[Environment]::SetEnvironmentVariable("{name}", "{value}", "User")'
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    os.environ[name] = value
    print(f"  Set User Env: {name} = {value}")

def add_to_user_path(directory):
    ps_cmd = f'''
    $p = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not ($p.Split(';') -contains "{directory}")) {{
        $newP = "{directory};" + $p
        [Environment]::SetEnvironmentVariable("Path", $newP, "User")
        Write-Host "Added to User Path: {directory}"
    }} else {{
        Write-Host "Already in User Path: {directory}"
    }}
    '''
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    if directory not in os.environ.get("PATH", ""):
        os.environ["PATH"] = directory + ";" + os.environ.get("PATH", "")

def install_jdk():
    java_exe = os.path.join(JDK_DIR, "bin", "java.exe")
    javac_exe = os.path.join(JDK_DIR, "bin", "javac.exe")
    if os.path.exists(java_exe) and os.path.exists(javac_exe):
        print(f"[OK] Standalone JDK 17 already installed at {JDK_DIR}")
    else:
        print("\n--- STEP: Installing Standalone JDK 17 ---")
        zip_path = os.path.join(SETUP_LOGS, JDK_ZIP_NAME)
        download_with_progress(JDK_URL, zip_path, JDK_SHA256)

        print(f"Extracting JDK archive: {zip_path}...")
        extract_temp = os.path.join(SETUP_LOGS, "jdk_extract_temp")
        os.makedirs(extract_temp, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_temp)

        # Temurin zip typically contains a top-level folder like jdk-17.0.20.1+1
        subdirs = [os.path.join(extract_temp, d) for d in os.listdir(extract_temp) if os.path.isdir(os.path.join(extract_temp, d))]
        if subdirs and os.path.exists(os.path.join(subdirs[0], "bin", "java.exe")):
            src_jdk = subdirs[0]
        else:
            src_jdk = extract_temp

        if os.path.exists(JDK_DIR):
            shutil.rmtree(JDK_DIR)
        shutil.move(src_jdk, JDK_DIR)
        shutil.rmtree(extract_temp, ignore_errors=True)
        print(f"[OK] Extracted JDK 17 to {JDK_DIR}")

    # Verify Java
    res_java = subprocess.run([java_exe, "-version"], capture_output=True, text=True)
    res_javac = subprocess.run([javac_exe, "-version"], capture_output=True, text=True)
    print("\nVerified JDK 17:")
    print("  java -version output:", res_java.stderr.strip() or res_java.stdout.strip())
    print("  javac -version output:", res_javac.stdout.strip() or res_javac.stderr.strip())

    # Environment variables
    print("\nConfiguring JDK 17 Environment Variables:")
    set_user_env_var("JAVA_HOME", JDK_DIR)
    add_to_user_path(os.path.join(JDK_DIR, "bin"))

def install_android_studio():
    studio_exe = os.path.join(STUDIO_DIR, "bin", "studio64.exe")
    if os.path.exists(studio_exe):
        print(f"[OK] Android Studio already installed at {STUDIO_DIR}")
        return

    print("\n--- STEP: Installing Android Studio ---")
    zip_path = os.path.join(SETUP_LOGS, STUDIO_ZIP_NAME)
    download_with_progress(STUDIO_URL, zip_path, STUDIO_SHA256)

    print(f"Extracting Android Studio archive: {zip_path}...")
    extract_temp = os.path.join(SETUP_LOGS, "studio_extract_temp")
    os.makedirs(extract_temp, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_temp)

    # Zip typically contains top-level folder "android-studio"
    subdirs = [os.path.join(extract_temp, d) for d in os.listdir(extract_temp) if os.path.isdir(os.path.join(extract_temp, d))]
    src_studio = subdirs[0] if subdirs and os.path.exists(os.path.join(subdirs[0], "bin", "studio64.exe")) else extract_temp

    if os.path.exists(STUDIO_DIR):
        shutil.rmtree(STUDIO_DIR)
    shutil.move(src_studio, STUDIO_DIR)
    shutil.rmtree(extract_temp, ignore_errors=True)
    print(f"[OK] Extracted Android Studio to {STUDIO_DIR}")

def configure_android_sdk():
    print("\n--- STEP: Configuring Android SDK and Caches on E: ---")
    set_user_env_var("ANDROID_HOME", SDK_DIR)
    set_user_env_var("ANDROID_SDK_ROOT", SDK_DIR)
    set_user_env_var("GRADLE_USER_HOME", GRADLE_HOME)
    set_user_env_var("ANDROID_USER_HOME", ANDROID_USER_HOME)

    # Copy existing components from C:\Users\goswa\AppData\Local\Android\Sdk if present
    c_sdk = r"C:\Users\goswa\AppData\Local\Android\Sdk"
    if os.path.exists(c_sdk):
        print(f"Reusing compatible components from {c_sdk} to {SDK_DIR}...")
        for item in ["licenses", "platform-tools", "cmdline-tools", "ndk", "cmake"]:
            src = os.path.join(c_sdk, item)
            dst = os.path.join(SDK_DIR, item)
            if os.path.exists(src) and not os.path.exists(dst):
                print(f"  Copying {item} -> {dst}...")
                shutil.copytree(src, dst)

    # Add platform-tools to Path
    add_to_user_path(os.path.join(SDK_DIR, "platform-tools"))
    add_to_user_path(os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin"))

    # Ensure platforms/android-34 and build-tools/34.0.0 exist
    sdkmanager_bat = os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
    if os.path.exists(sdkmanager_bat):
        print("Accepting SDK licenses...")
        subprocess.run(f'echo y | "{sdkmanager_bat}" --sdk_root="{SDK_DIR}" --licenses', shell=True, env=os.environ)

        platform_34 = os.path.join(SDK_DIR, "platforms", "android-34")
        build_tools_34 = os.path.join(SDK_DIR, "build-tools", "34.0.0")

        to_install = []
        if not os.path.exists(platform_34):
            to_install.append('"platforms;android-34"')
        if not os.path.exists(build_tools_34):
            to_install.append('"build-tools;34.0.0"')

        if to_install:
            print(f"Installing required packages: {' '.join(to_install)}...")
            cmd = f'echo y | "{sdkmanager_bat}" --sdk_root="{SDK_DIR}" {" ".join(to_install)}'
            subprocess.run(cmd, shell=True, check=True, env=os.environ)
            print("[OK] Android SDK packages installed successfully.")
        else:
            print("[OK] android-34 and build-tools 34.0.0 already present.")

    # Configure local.properties for the Drishti project
    local_props_path = r"E:\HAckbios-R&D\hackbios-neuraX\android\local.properties"
    with open(local_props_path, "w", encoding="utf-8") as f:
        f.write(f"sdk.dir={SDK_DIR.replace(chr(92), '/')}\n")
    print(f"[OK] Generated {local_props_path} with sdk.dir={SDK_DIR}")

if __name__ == "__main__":
    print("=" * 80)
    print("INSTALLING ANDROID TOOLCHAIN ON E: DRIVE")
    print("=" * 80)
    for d in [STUDIO_DIR, JDK_DIR, SDK_DIR, GRADLE_HOME, ANDROID_USER_HOME, SETUP_LOGS]:
        os.makedirs(d, exist_ok=True)

    install_jdk()
    configure_android_sdk()
    install_android_studio()

    print("\n" + "=" * 80)
    print("TOOLCHAIN INSTALLATION COMPLETE!")
    print("=" * 80)
