import os
import glob
import subprocess
import time

java_exe = r"E:\DevTools\Java\jdk-17\bin\java.exe"
gradle_home = r"E:\Android\GradleHome\wrapper\dists\gradle-8.11.1-bin\bpt9gzteqjrbo1mjrsomdt32c\gradle-8.11.1"
cli_jar = os.path.join(gradle_home, "lib", "gradle-gradle-cli-main-8.11.1.jar")

env = os.environ.copy()
env["JAVA_HOME"] = r"E:\DevTools\Java\jdk-17"
env["GRADLE_USER_HOME"] = r"E:\Android\GradleHome"
env["ANDROID_HOME"] = r"E:\Android\Sdk"

cmd = [
    java_exe,
    f"-Dorg.gradle.appname=gradle",
    "-classpath", cli_jar,
    "org.gradle.launcher.GradleMain",
    "--version"
]

print("Launching GradleMain directly...", flush=True)
t0 = time.time()
res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
elapsed = time.time() - t0
print(f"Elapsed: {elapsed:.2f}s, Returncode: {res.returncode}", flush=True)
print("STDOUT:\n" + res.stdout)
print("STDERR:\n" + res.stderr)
