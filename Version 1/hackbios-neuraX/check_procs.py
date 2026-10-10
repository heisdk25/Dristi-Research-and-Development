import psutil

for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = " ".join(p.info['cmdline'] or [])
        if any(x in cmd.lower() for x in ['powershell', 'install_android', 'sdkmanager', 'java']):
            print(f"{p.info['name']} [PID {p.info['pid']}]: {cmd[:140]}")
    except Exception:
        pass
