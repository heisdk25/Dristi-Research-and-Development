import os
import subprocess

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (r.returncode, r.stdout.strip(), r.stderr.strip())
    except Exception as e:
        return (-1, "", str(e))

print("=== VERIFYING DEVELOPMENT SETUP ON E: DRIVE ===", flush=True)

java_home = r"E:\DevTools\Java\jdk-17"
java_exe = os.path.join(java_home, "bin", "java.exe")
javac_exe = os.path.join(java_home, "bin", "javac.exe")
adb_exe = r"E:\Android\Sdk\platform-tools\adb.exe"
studio_exe = r"E:\DevTools\AndroidStudio\bin\studio64.exe"
sdk_dir = r"E:\Android\Sdk"
gradle_home = r"E:\Android\GradleHome"

print(f"JAVA_HOME: {java_home} (exists: {os.path.exists(java_home)})", flush=True)
rc, out, err = run([java_exe, "-version"])
print(f"java -version:\n{err or out}", flush=True)

rc, out, err = run([javac_exe, "-version"])
print(f"javac -version:\n{out or err}", flush=True)

print(f"ANDROID_HOME: {sdk_dir} (exists: {os.path.exists(sdk_dir)})", flush=True)
rc, out, err = run([adb_exe, "version"])
print(f"ADB version:\n{out}", flush=True)

print(f"Android Studio: {studio_exe} (exists: {os.path.exists(studio_exe)})", flush=True)
print(f"Gradle User Home: {gradle_home} (exists: {os.path.exists(gradle_home)})", flush=True)
print(f"Android User Home: E:\\Android\\UserHome (exists: {os.path.exists(r'E:\Android\UserHome')})", flush=True)

build_tools_34 = os.path.join(sdk_dir, "build-tools", "34.0.0")
print(f"Build-Tools 34.0.0: {build_tools_34} (exists: {os.path.exists(build_tools_34)})", flush=True)

platforms = os.listdir(os.path.join(sdk_dir, "platforms")) if os.path.exists(os.path.join(sdk_dir, "platforms")) else []
print(f"Platforms in SDK: {platforms}", flush=True)

print("=== SETUP VERIFICATION COMPLETED ===", flush=True)
