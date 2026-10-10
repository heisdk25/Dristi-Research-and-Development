import os
import sys
import time
import tarfile
import tempfile
import paramiko

# Ensure UTF-8 output encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VULTR_IP = "65.20.74.192"
VULTR_USER = "root"
VULTR_PASS = "_2vC)A=Xd@(eZxSj"

LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {VULTR_IP} as {VULTR_USER}...", flush=True)
    client.connect(VULTR_IP, username=VULTR_USER, password=VULTR_PASS, timeout=20)
    print("SSH connection established successfully!\n", flush=True)
    return client

def run_cmd(client, command, check=True):
    print(f"=== [EXEC] {command} ===", flush=True)
    stdin, stdout, stderr = client.exec_command(command, get_pty=True)
    output_lines = []
    for line in iter(stdout.readline, ""):
        try:
            print(line, end="", flush=True)
        except Exception:
            print(line.encode("ascii", "replace").decode(), end="", flush=True)
        output_lines.append(line)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0 and check:
        err = stderr.read().decode(errors="replace")
        if err:
            print(f"ERROR: {err}", flush=True)
        raise RuntimeError(f"Command failed with exit code {exit_code}: {command}")
    return exit_code, "".join(output_lines)


def create_bundle_tar():
    tar_path = os.path.join(tempfile.gettempdir(), "drishti_deploy.tar.gz")
    print(f"Creating project bundle archive: {tar_path}...")
    
    files_to_pack = [
        ("docker-compose.yml", "docker-compose.yml"),
        ("Caddyfile", "Caddyfile"),
        ("token-server/main.py", "token-server/main.py"),
        ("token-server/requirements.txt", "token-server/requirements.txt"),
        ("token-server/Dockerfile", "token-server/Dockerfile"),
        ("token-server/.dockerignore", "token-server/.dockerignore"),
        ("agent/drishti_agent.py", "agent/drishti_agent.py"),
        ("agent/conversation_logger.py", "agent/conversation_logger.py"),
        ("agent/requirements.txt", "agent/requirements.txt"),
        ("agent/Dockerfile", "agent/Dockerfile"),
        ("agent/.dockerignore", "agent/.dockerignore"),
    ]
    
    with tarfile.open(tar_path, "w:gz") as tar:
        for local_rel, arcname in files_to_pack:
            full_path = os.path.join(LOCAL_ROOT, local_rel)
            if os.path.exists(full_path):
                tar.add(full_path, arcname=arcname)
                print(f"  + Added {local_rel} -> {arcname}")
            else:
                print(f"  ! Warning: {full_path} does not exist")
                
    return tar_path

def upload_bundle_and_env(client, tar_path):
    sftp = client.open_sftp()
    
    # 1. Upload tarball
    remote_tar = "/tmp/drishti_deploy.tar.gz"
    print(f"\nUploading bundle to {remote_tar}...")
    sftp.put(tar_path, remote_tar)
    print("Bundle uploaded successfully.")
    
    # 2. Extract tarball to /opt/drishti
    run_cmd(client, "mkdir -p /opt/drishti")
    run_cmd(client, "tar -xzf /tmp/drishti_deploy.tar.gz -C /opt/drishti")
    run_cmd(client, "rm -f /tmp/drishti_deploy.tar.gz")
    
    # 3. Create /opt/drishti/.env from local agent/.env
    local_env_path = os.path.join(LOCAL_ROOT, "agent", ".env")
    if os.path.exists(local_env_path):
        with open(local_env_path, "r", encoding="utf-8") as f:
            env_content = f.read()
        remote_env = "/opt/drishti/.env"
        print("Uploading production environment configuration to /opt/drishti/.env...")
        with sftp.file(remote_env, "w") as rf:
            rf.write(env_content)
        sftp.chmod(remote_env, 0o600)
        print("Environment configuration written securely.")
        
    sftp.close()

def setup_server_and_deploy(client):
    # Step 1: Check Docker
    code, out = run_cmd(client, "docker --version", check=False)
    if code != 0:
        print("\nInstalling Docker and dependencies...")
        run_cmd(client, "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y ca-certificates curl gnupg lsb-release ufw")
        run_cmd(client, "install -m 0755 -d /etc/apt/keyrings")
        run_cmd(client, "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc")
        run_cmd(client, "chmod a+r /etc/apt/keyrings/docker.asc")
        run_cmd(client, 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null')
        run_cmd(client, "apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin")
        run_cmd(client, "systemctl enable --now docker")

    # Step 2: Configure UFW firewall
    print("\nConfiguring firewall rules...")
    run_cmd(client, "ufw default deny incoming", check=False)
    run_cmd(client, "ufw default allow outgoing", check=False)
    run_cmd(client, "ufw allow 22/tcp", check=False)
    run_cmd(client, "ufw allow 8000/tcp", check=False)
    run_cmd(client, "ufw allow 80/tcp", check=False)
    run_cmd(client, "ufw allow 443/tcp", check=False)
    run_cmd(client, "ufw --force enable", check=False)

    # Step 3: Launch Docker containers
    print("\nBuilding and starting Drishti containers via Docker Compose...")
    run_cmd(client, "cd /opt/drishti && docker compose down --remove-orphans", check=False)
    run_cmd(client, "cd /opt/drishti && docker compose up -d --build")

    # Step 4: Health check
    print("\nVerifying health check...")
    time.sleep(5)
    for attempt in range(12):
        code, out = run_cmd(client, "curl -s http://localhost:8000/health", check=False)
        if "healthy" in out:
            print("\n>>> SUCCESS: Drishti Token Server is HEALTHY! <<<")
            break
        print(f"Waiting for services to become healthy (attempt {attempt + 1}/12)...")
        time.sleep(5)

    # Step 5: Check running containers
    run_cmd(client, "cd /opt/drishti && docker compose ps")
    run_cmd(client, "cd /opt/drishti && docker compose logs --tail 30")

if __name__ == "__main__":
    client = get_ssh_client()
    tar_path = create_bundle_tar()
    try:
        upload_bundle_and_env(client, tar_path)
        setup_server_and_deploy(client)
    finally:
        if os.path.exists(tar_path):
            os.remove(tar_path)
        client.close()
