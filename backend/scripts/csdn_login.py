"""打开CSDN首页，等待手动登录。登录成功后按回车保存。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright

PROFILE = os.path.join(os.path.dirname(__file__), "..", "browser_profile")
os.makedirs(PROFILE, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE,
        headless=False,
        viewport={"width": 1280, "height": 720},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto("https://www.csdn.net")
    print("浏览器已打开CSDN首页，请手动登录。")
    print("登录完成后回到终端按 Enter 保存...")
    input()
    browser.close()
    print("登录态已保存！")
