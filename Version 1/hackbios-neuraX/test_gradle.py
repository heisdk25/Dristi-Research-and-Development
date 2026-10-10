import os
import subprocess

env = os.environ.copy()
env["JAVA_HOME"] = r"E:\DevTools\Java\jdk-17"
env["GRADLE_USER_HOME"] = r"E:\Android\GradleHome"
env["ANDROID_HOME"] = r"E:\Android\Sdk"
env["PATH"] = r"E:\DevTools\Java\jdk-17\bin;" + r"E:\Android\Sdk\platform-tools;" + env.get("PATH", "")

gradle_bat = r"E:\Android\GradleHome\wrapper\dists\gradle-8.11.1-bin\bpt9gzteqjrbo1mjrsomdt32c\gradle-8.11.1\bin\gradle.bat"
print(f"Testing gradle.bat: {os.path.exists(gradle_bat)}", flush=True)

# Run with stdin=DEVNULL and shell=True (proper for .bat files on Windows)
res = subprocess.run(f'"{gradle_bat}" --version --no-daemon', shell=True, stdin=subprocess.DEVNULL, env=env)
print("Returncode:", res.returncode, flush=True)
