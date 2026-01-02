import requests
import os
import subprocess
import sys
import time

# --- CONFIG ---
CURRENT_VERSION = "1.0.0"
VERSION_URL = "https://your-server.com/version.txt"       # 🔁 Replace with your real URL
EXE_URL     = "https://your-server.com/forexbot.exe"       # 🔁 Replace with your real URL
EXE_NAME    = "forexbot.exe"
TMP_EXE     = "forexbot_new.exe"

# --- VERSION CHECK ---
def get_latest_version():
    try:
        response = requests.get(VERSION_URL)
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Could not fetch version info: {e}")
        return None

# --- DOWNLOAD EXE ---
def download_new_version():
    try:
        print("[INFO] Downloading update...")
        response = requests.get(EXE_URL, stream=True)
        with open(TMP_EXE, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print("[INFO] Download complete.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download update: {e}")
        return False

# --- REPLACE FILE ---
def replace_and_restart():
    try:
        if os.path.exists(EXE_NAME):
            os.rename(EXE_NAME, f"old_{EXE_NAME}")
        os.rename(TMP_EXE, EXE_NAME)
        print("[INFO] Bot updated. Restarting...")
        subprocess.Popen([EXE_NAME], shell=True)
        sys.exit()
    except Exception as e:
        print(f"[ERROR] Failed to replace or restart: {e}")
        return False

# --- MAIN ---
def main():
    print(f"[START] Forex Bot Updater v{CURRENT_VERSION}")
    latest = get_latest_version()

    if latest and latest > CURRENT_VERSION:
        print(f"[UPDATE] New version available: {latest}")
        if download_new_version():
            time.sleep(1)
            replace_and_restart()
    else:
        print("[INFO] You're already running the latest version.")
        subprocess.Popen([EXE_NAME], shell=True)
        sys.exit()

if __name__ == "__main__":
    main()
