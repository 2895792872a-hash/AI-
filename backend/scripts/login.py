"""Open a VISIBLE browser to log into websites. Saves auth to storage_state.json."""

import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser_profile"))
STATE_FILE = os.path.join(PROFILE_DIR, "auth.json")
os.makedirs(PROFILE_DIR, exist_ok=True)

target = sys.argv[1] if len(sys.argv) > 1 else "bilibili.com"
url = f"https://{target}" if "://" not in target else target

print(f"""Login: {url}
Profile: {PROFILE_DIR}
State: {STATE_FILE}

Log in, then press Enter to save and close.""")

with sync_playwright() as pw:
    browser = pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1280, "height": 800},
        args=["--no-proxy-server", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto(url, wait_until="domcontentloaded")

    input("\nPress Enter when done logging in... ")

    # Export cookies + storage to JSON
    state = browser.storage_state()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    browser.close()
    print(f"Auth saved to {STATE_FILE}")
