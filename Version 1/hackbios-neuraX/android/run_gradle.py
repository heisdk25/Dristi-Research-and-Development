import os
import sys
import subprocess

android_dir = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:] if len(sys.argv) > 1 else ["--version"]

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
    "-Xmx64m",
    "-Xms64m",
    "-Dorg.gradle.appname=gradlew",
    "-classpath",
    wrapper_jar,
    "org.gradle.wrapper.GradleWrapperMain"
] + args

print(f"Executing Gradle: {' '.join(args)}", flush=True)
print(f"  JAVA_HOME = {env['JAVA_HOME']}", flush=True)
print(f"  GRADLE_USER_HOME = {env['GRADLE_USER_HOME']}", flush=True)
print(f"  ANDROID_HOME = {env['ANDROID_HOME']}", flush=True)
print(f"  Wrapper JAR = {wrapper_jar}", flush=True)

res = subprocess.run(cmd, cwd=android_dir, env=env, stdin=subprocess.DEVNULL)
sys.exit(res.returncode)
