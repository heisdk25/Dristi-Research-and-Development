import os
import sys
import shutil
import platform
import subprocess

print("=== OS & PLATFORM ===")
print("System:", platform.system())
print("Release:", platform.release())
print("Version:", platform.version())
print("Machine:", platform.machine())
print("Architecture:", platform.architecture())

print("\n=== DISK SPACE ===")
for drive in ["C:\\", "E:\\"]:
    try:
        total, used, free = shutil.disk_usage(drive)
        print(f"Drive {drive}: Total = {total/(1024**3):.2f} GB, Used = {used/(1024**3):.2f} GB, Free = {free/(1024**3):.2f} GB")
    except Exception as e:
        print(f"Drive {drive}: Error reading disk usage: {e}")

print("\n=== E: DRIVE WRITABILITY TEST ===")
test_file = r"E:\test_write_permission.tmp"
try:
    with open(test_file, "w") as f:
        f.write("OK")
    os.remove(test_file)
    print("E: drive is WRITABLE: PASS")
except Exception as e:
    print(f"E: drive write failed: {e}")

print("\n=== COMMAND AVAILABILITY ===")
for cmd in ["java", "javac", "adb", "gradle", "studio64"]:
    path = shutil.which(cmd)
    print(f"  {cmd}: {path if path else 'NOT FOUND'}")

print("\n=== EXISTING TOOLCHAIN PATHS ===")
paths_to_check = [
    r"C:\Program Files\Android\Android Studio",
    r"C:\Users\goswa\AppData\Local\Android\Sdk",
    r"C:\Users\goswa\.gradle",
    r"C:\Program Files\Java",
    r"E:\DevTools",
    r"E:\DevTools\AndroidStudio",
    r"E:\DevTools\Java\jdk-17",
    r"E:\Android",
    r"E:\Android\Sdk",
    r"E:\Android\GradleHome",
    r"E:\Android\UserHome",
    r"E:\Android\SetupLogs",
    r"E:\HAckbios-R&D\hackbios-neuraX",
    r"E:\HAckbios-R&D\hackbios-neuraX\android\gradlew.bat"
]
for p in paths_to_check:
    print(f"  {p}: {'EXISTS' if os.path.exists(p) else 'DOES NOT EXIST'}")

print("\n=== GIT STATUS ===")
try:
    repo_dir = r"E:\HAckbios-R&D\hackbios-neuraX"
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir).decode().strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=repo_dir).decode().strip()
    print(f"Git branch: {branch}")
    print(f"Git status --short:\n{status}")
except Exception as e:
    print(f"Git check error: {e}")
