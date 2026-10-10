import os
import sys
import subprocess
import time

android_dir = r"E:\HAckbios-R&D\hackbios-neuraX\android"
log_dir = r"E:\Android\SetupLogs"
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "assembleDebug.log")

target_task = sys.argv[1] if len(sys.argv) > 1 else "assembleDebug"
if target_task == "test":
    target_task = "testDebugUnitTest"
    log_file = os.path.join(log_dir, "testDebugUnitTest.log")

env = os.environ.copy()
env["JAVA_HOME"] = r"E:\DevTools\Java\jdk-17"
env["GRADLE_USER_HOME"] = r"E:\Android\GradleHome"
env["ANDROID_HOME"] = r"E:\Android\Sdk"
env["ANDROID_SDK_ROOT"] = r"E:\Android\Sdk"
env["PATH"] = r"E:\DevTools\Java\jdk-17\bin;" + r"E:\Android\Sdk\platform-tools;" + env.get("PATH", "")

java_exe = os.path.join(env["JAVA_HOME"], "bin", "java.exe")
wrapper_jar = os.path.join(android_dir, "gradle", "wrapper", "gradle-wrapper.jar")

cmd = [
    java_exe,
    "-Xmx2048m",
    "-Dorg.gradle.appname=gradlew",
    "-classpath",
    wrapper_jar,
    "org.gradle.wrapper.GradleWrapperMain",
    target_task,
    "--console=plain",
    "--stacktrace",
    "--no-daemon"
]

print(f"Starting Drishti Build: {target_task}")
print(f"Logging directly to: {log_file}")
sys.stdout.flush()

t0 = time.time()
with open(log_file, "w", encoding="utf-8") as f:
    f.write(f"=== Drishti Build Start: {time.ctime()} ===\n")
    f.write(f"Task: {target_task}\n")
    f.write(f"Command: {' '.join(cmd)}\n\n")
    f.flush()
    
    proc = subprocess.Popen(
        cmd,
        cwd=android_dir,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in iter(proc.stdout.readline, ''):
        f.write(line)
        f.flush()
        # Print high-level progress to console
        if any(keyword in line for keyword in ["> Task", "BUILD", "FAILURE", "Exception", "Finished", "download"]):
            print(line.strip(), flush=True)

    proc.stdout.close()
    return_code = proc.wait()
    elapsed = time.time() - t0
    f.write(f"\n=== Build Finished with code {return_code} in {elapsed:.1f}s ===\n")
    f.flush()

print(f"Build completed with return code {return_code} in {elapsed:.1f}s")
sys.exit(return_code)
