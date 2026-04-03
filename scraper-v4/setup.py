import os
import subprocess
import sys
import time

VENV_DIR = ".venv"
PYTHON = sys.executable

def run(cmd, shell=True):
    print(f"\n>>> {cmd}")
    subprocess.run(cmd, shell=shell)

# ===============================
# STEP 1: CREATE VENV
# ===============================
def create_venv():
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        run(f"{PYTHON} -m venv {VENV_DIR}")
    else:
        print("Virtual environment already exists")

# ===============================
# STEP 2: INSTALL REQUIREMENTS
# ===============================
def install_requirements():
    pip_path = os.path.join(VENV_DIR, "Scripts", "pip")
    run(f"{pip_path} install --upgrade pip")
    run(f"{pip_path} install -r requirements.txt")

# ===============================
# STEP 3: START REDIS (DOCKER)
# ===============================
def start_redis():
    print("Starting Redis (Docker)...")

    # Check if Redis container exists
    result = subprocess.run("docker ps -a --filter name=redis-v4 --format {{.Names}}", shell=True, capture_output=True, text=True)

    if "redis-v4" in result.stdout:
        print("Redis container exists → starting...")
        run("docker start redis-v4")
    else:
        print("Creating new Redis container...")
        run("docker run -d -p 6379:6379 --name redis-v4 redis:7")

# ===============================
# STEP 4: START API
# ===============================
def start_api():
    python_path = os.path.join(VENV_DIR, "Scripts", "python")
    print("Starting API server...")
    subprocess.Popen(
        f"{python_path} api/app.py",
        shell=True,
        cwd=os.path.abspath(".")  # 👈 FORCE ROOT DIR
    )

# ===============================
# STEP 5: START WORKERS
# ===============================
def start_workers(count=3):
    python_path = os.path.join(VENV_DIR, "Scripts", "python")

    print(f"Starting {count} workers...")

    for i in range(count):
        subprocess.Popen(f"{python_path} worker/worker.py", shell=True)

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    create_venv()
    install_requirements()
    start_redis()

    time.sleep(3)

    start_api()
    start_workers(count=3)

    print("\n🚀 SYSTEM READY")
    print("API: http://localhost:5000")