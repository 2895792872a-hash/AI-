"""Standalone sync process for Playwright — with persistent browser profile.

Uses launch_persistent_context so cookies, sessions, and logins survive restarts.
"""

import sys
import json
import os
import random
import time
import math
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "browser_profile"))
PROFILE_DIR = os.environ.get("BROWSER_PROFILE", PROFILE_DIR)
HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"


# ── Human-like behavior helpers ──

def human_delay(min_ms=200, max_ms=800):
    """Random delay to mimic human reaction time."""
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def human_scroll(page):
    """Scroll randomly to mimic human browsing."""
    if random.random() > 0.5:
        delta = random.randint(100, 400)
        page.evaluate(f"window.scrollBy(0, {delta})")
        time.sleep(random.uniform(0.3, 0.8))


def human_mouse_move(page, target_x, target_y, steps=8):
    """Move mouse along a bezier curve to target."""
    start_x = random.randint(100, 400)
    start_y = random.randint(100, 500)
    cp_x = (start_x + target_x) / 2 + random.randint(-80, 80)
    cp_y = min(start_y, target_y) - random.randint(30, 100)

    for i in range(steps + 1):
        t = i / steps
        # Quadratic bezier
        x = (1-t)**2 * start_x + 2*(1-t)*t * cp_x + t**2 * target_x
        y = (1-t)**2 * start_y + 2*(1-t)*t * cp_y + t**2 * target_y
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.01, 0.04))
    # Sometimes overshoot and correct
    if random.random() > 0.7:
        page.mouse.move(target_x + random.randint(-5, 5), target_y + random.randint(-5, 5))
        time.sleep(0.05)
        page.mouse.move(target_x, target_y)


def human_click(page, x, y):
    """Click with human-like mouse movement."""
    human_mouse_move(page, x, y)
    human_delay(50, 150)
    page.mouse.click(x, y)
    human_delay(100, 300)


def human_type(page, text: str):
    """Type text with random delays between keystrokes."""
    for char in text:
        page.keyboard.type(char, delay=random.randint(30, 120))
        if random.random() < 0.05:  # 5% chance to pause (thinking)
            time.sleep(random.uniform(0.1, 0.4))


def main():
    browser = None
    page = None

    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)

        pw = sync_playwright().start()
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS,
            viewport={"width": 1280, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-sync",
                "--disable-default-apps",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-sandbox",
                "--disable-gpu",
            ],
            ignore_default_args=["--enable-automation"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.set_default_timeout(30000)
        # Random initial delay
        human_delay(500, 2000)

        # ── Anti-detection: hide all automation fingerprints ──
        page.add_init_script("""
            // Core automation flags
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            // Plugins — real browsers have them
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
                    ];
                    plugins.item = (i) => plugins[i];
                    plugins.namedItem = (n) => plugins.find(p => p.name === n);
                    plugins.refresh = () => {};
                    return plugins;
                }
            });
            // Languages
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
            // Hardware
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            // Screen
            Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
            Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
            // Remove traces
            delete window.callPhantom;
            window.phantom = undefined;
            window.__nightmare = undefined;
            // Connection
            if (navigator.connection) {
                Object.defineProperty(navigator.connection, 'rtt', { get: () => 100 });
            }
            // Canvas fingerprint randomization
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] ^= randomInt(0, 1);
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
                return origToDataURL.apply(this, arguments);
            };
            function randomInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
            // WebGL fingerprint randomization
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
        """)

        print(json.dumps({"status": "ready", "profile": PROFILE_DIR}), flush=True)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            cmd = json.loads(line)
            action = cmd.get("action")
            step_id = cmd.get("step_id", 0)

            if action == "quit":
                print(json.dumps({"status": "bye"}), flush=True)
                break

            try:
                result = execute(page, action, cmd, browser_ctx=browser)
                result["step_id"] = step_id
                result["status"] = "completed"
                # After accessibility_click, switch to newest tab if one opened
                if action == "accessibility_click":
                    new_page = switch_to_newest_tab(browser, page)
                    if new_page != page:
                        page = new_page
                        result["switched_tab"] = True
            except Exception as e:
                result = {"step_id": step_id, "action": action, "status": "failed", "error": str(e)}

            print(json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}), flush=True)
    finally:
        if browser:
            browser.close()
        if pw:
            pw.stop()







def smart_extract(page) -> str:
    parts = []
    try:
        text = page.evaluate("() => document.body.innerText")
        if text:
            parts.append(text[:5000])
    except Exception:
        pass
    if not parts:
        return "[No content extracted]"
    return "\n".join(parts)

def extract_role_names(page) -> str:
    """Extract all interactive elements with computed role+name via JS.

    Works in ANY browser, no Playwright accessibility API needed.
    Catches <span>, <div>, SPA components via cursor:pointer detection.
    """
    js = r"""() => {
        const items = [];
        const seen = new Set();
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (seen.has(el)) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            if (rect.bottom < -100 || rect.top > window.innerHeight + 500) continue;
            const style = getComputedStyle(el);
            if (style.visibility === 'hidden' || style.display === 'none') continue;

            const tag = el.tagName.toLowerCase();
            let text = (el.textContent || '').trim().substring(0, 60).replace(/\s+/g, ' ');
            // For inputs/textarea, use placeholder/value/aria-label instead of textContent
            if (!text && (tag === 'input' || tag === 'textarea')) {
                text = (el.placeholder || el.value || el.getAttribute('aria-label') || '').trim().substring(0, 60);
            }
            // Fallback names for nameless inputs
            if (!text && (tag === 'input' || tag === 'textarea')) {
                if (rect.y < 300) text = '搜索框';  // Top-of-page empty input = search
                if (!text) text = (el.name || el.id || el.className || '').substring(0, 40);
            }
            if (!text) continue;

            // Compute role: multiple signals — no single point of failure
            let role = el.getAttribute('role') || '';
            if (!role) {
                if ((tag === 'a' && el.hasAttribute('href')) || tag === 'a') role = 'link';
                else if (tag === 'button' || el.getAttribute('type') === 'submit') role = 'button';
                else if ((tag === 'input' && (el.type === 'text' || el.type === 'search' || !el.type || el.type === ''))
                         || tag === 'textarea') role = 'textbox';
                else if (tag === 'input' && el.type === 'submit') role = 'button';
                else if (tag === 'select') role = 'combobox';
                else if (tag === 'img' && el.alt) role = 'img';
                // SPA detection: multiple signals
                else if (style.cursor === 'pointer') role = 'link';
                else if (el.hasAttribute('tabindex')) role = 'link';
                else if (el.hasAttribute('onclick')) role = 'link';
                else if (el.hasAttribute('data-url') || el.hasAttribute('data-href')
                         || el.hasAttribute('data-link') || el.hasAttribute('data-route')) role = 'link';
                // In header/nav area: short-text elements likely navigation items
                else if (text.length <= 6 && isInNavOrHeader(el)) role = 'link';
                // Inside <li> in a list: likely menu/nav item
                else if (el.closest('li') && el.closest('ul,ol,nav') && text.length <= 20) role = 'link';
            }

            if (!role) continue;

            const key = role + '|' + text;
            if (seen.has(key)) continue;
            seen.add(key);
            items.push({role, name: text, y: rect.y, x: rect.x});
        }

        // Sort by position: top-to-bottom, left-to-right
        items.sort((a, b) => {
            if (Math.abs(a.y - b.y) > 20) return a.y - b.y;
            return a.x - b.x;
        });

        return items.slice(0, 80).map((it, i) =>
            `${roleIcon(it.role)} ${it.role} "${it.name}"`
        ).join('\n');

        function roleIcon(r) { return r==='link'?'🔗':r==='button'?'🔘':r==='textbox'?'✏️':r==='combobox'?'📋':'•'; }
        function isInNavOrHeader(el) {
            let p = el;
            while (p) {
                const tag = (p.tagName||'').toLowerCase();
                if (tag === 'header' || tag === 'nav') return true;
                const cls = (p.className||'').toString();
                if (/header|navbar|top-bar|nav|banner/i.test(cls)) return true;
                const id = (p.id||'');
                if (/header|navbar|nav|top/i.test(id)) return true;
                p = p.parentElement;
                if (p && p === document.body) break;
            }
            return false;
        }
    }"""
    try:
        result = page.evaluate(js)
        return result if result else "[No interactive elements found]"
    except Exception as e:
        return f"[Extract error: {e}]"


def click_by_role_name(page, role: str, name: str) -> bool:
    """Click element by role+name. Tries click first, falls back to href navigation."""
    if not name:
        return False

    tag = 'a' if role == 'link' else ('button' if role == 'button' else '*')
    safe_name = name.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
    selector = f'{tag}:has-text("{safe_name}"):visible'

    # Strategy 0: if name has brackets/special chars, try the last word (usually the real text)
    if '[' in name or ']' in name or '(' in name:
        # Extract clean words — try longest one first
        import re
        words = re.findall(r'[一-鿿\w]+', name)
        words.sort(key=len, reverse=True)
        for word in words[:3]:
            try:
                wsel = f'{tag}:has-text("{word}"):visible'
                el = page.locator(wsel).first
                if el.count() > 0 and el.is_visible():
                    el.click(force=True, timeout=3000)
                    page.wait_for_timeout(800)
                    return True
            except Exception:
                continue

    # Strategy 1: human-like click with bezier mouse movement
    try:
        el = page.locator(selector).first
        if el.count() > 0 and el.is_visible():
            box = el.bounding_box()
            if box:
                human_click(page, box['x'] + box['width']/2, box['y'] + box['height']/2)
                human_delay(400, 1000)
                human_scroll(page)
                return True
            el.click(force=True, timeout=3000)
            page.wait_for_timeout(800)
            return True
    except Exception:
        pass

    # Strategy 2: mouse click at center
    try:
        el = page.locator(selector).first
        if el.count() > 0:
            box = el.bounding_box()
            if box:
                page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                page.wait_for_timeout(800)
                return True
    except Exception:
        pass

    # Strategy 3: if it's a link, navigate to its href directly (bypasses JS handlers)
    if role == 'link':
        try:
            href = page.locator(selector).first.get_attribute('href', timeout=2000)
            if href:
                page.goto(href, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            pass
        # Also try finding any ancestor/descendant <a> with href
        try:
            href = page.evaluate(f"""(selector) => {{
                const el = document.evaluate(
                    selector + '/ancestor-or-self::a[@href] | ' + selector + '//a[@href]',
                    document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                ).singleNodeValue;
                return el ? el.href : null;
            }}""", selector)
            if href:
                page.goto(href, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            pass

    # Strategy 4: JS — find any href recursively, navigate directly
    if role == 'link':
        try:
            href = page.evaluate(f"""(name) => {{
                const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while (node = walk.nextNode()) {{
                    if (node.textContent && node.textContent.includes(name)) {{
                        // Check this element
                        let el = node;
                        for (let i = 0; i < 5; i++) {{
                            const h = el.getAttribute('href') || el.href;
                            if (h && !h.startsWith('javascript:') && h !== window.location.href) return h;
                            el = el.parentElement;
                            if (!el) break;
                        }}
                    }}
                }}
                return null;
            }}""", name)
            if href:
                if href.startswith('/'):
                    href = page.url.split('/').slice(0, 3).join('/') + href
                page.goto(href, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            pass

    # Strategy 5: getByText
    try:
        el = page.get_by_text(name, exact=True).first
        if el.count() > 0 and el.is_visible():
            el.click(force=True, timeout=3000)
            page.wait_for_timeout(800)
            return True
    except Exception:
        pass

    return False


def find_input(page, hint: str = ""):
    """Find the main search/input field using multiple strategies."""
    # 0. If VL provided a hint, try text-based search first
    if hint:
        hint_lower = hint.lower()
        keywords = [w for w in hint_lower.replace("搜索", " search ").replace("输入", " input ").split() if len(w) > 1]
        for kw in keywords[:5]:
            try:
                el = page.locator(f"input[placeholder*='{kw}' i]").first
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box["width"] > 50:
                        return el
            except Exception:
                pass
        # Try finding near the hint text
        for t in [hint[:10], hint[:20], hint]:
            try:
                el = page.get_by_placeholder(t).first
                if el.is_visible():
                    return el
            except Exception:
                pass
    # 1. ARIA role: searchbox
    try:
        el = page.get_by_role("searchbox").first
        if el.is_visible():
            return el
    except Exception:
        pass
    # 2. ARIA role: textbox (top of page)
    try:
        boxes = page.get_by_role("textbox")
        for i in range(min(boxes.count(), 10)):
            el = boxes.nth(i)
            if el.is_visible():
                box = el.bounding_box()
                if box and box["y"] < 300 and box["width"] > 100:
                    return el
    except Exception:
        pass
    # 3. Common CSS selectors
    for s in ["input[type='search']", "input[name='q']", "input[name='keyword']",
              "input[type='text']:not([type='hidden'])", "textarea", "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox'])"]:
        try:
            el = page.locator(s).first
            if el.is_visible():
                box = el.bounding_box()
                if box and box["width"] > 80:
                    return el
        except Exception:
            continue
    raise Exception("Could not find any input field on the page")



def switch_to_newest_tab(browser_ctx, current_page):
    """If a new tab opened (target=_blank), switch to it and return new page."""
    pages = browser_ctx.pages
    if len(pages) > 1:
        newest = pages[-1]
        if newest != current_page:
            try:
                newest.bring_to_front()
                newest.wait_for_load_state('domcontentloaded', timeout=10000)
                return newest
            except Exception:
                pass
    return current_page


def execute(page, action, cmd, browser_ctx=None):
    if action == "navigate":
        try:
            resp = page.goto(cmd["url"], wait_until="networkidle", timeout=30000)
        except Exception:
            resp = page.goto(cmd["url"], wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        # If page is blank, try again with longer wait
        if "about:blank" in page.url or page.url.startswith("about:"):
            page.goto(cmd["url"], wait_until="load", timeout=30000)
            page.wait_for_timeout(3000)
        return {"action": "navigate", "url": page.url, "title": page.title()}

    elif action == "type":
        text = cmd.get("text", "")
        hint = cmd.get("hint", cmd.get("selector", ""))
        try:
            el = find_input(page, hint)
            el.click(timeout=2000)
            page.wait_for_timeout(200)
            el.fill('')
            page.wait_for_timeout(100)
            human_type(page, text)
            human_delay(200, 500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            return {"action": "type", "text": text}
        except Exception:
            pass
        # Fallback: keyboard type
        try:
            page.keyboard.type(text, delay=50)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            return {"action": "type", "text": text}
        except Exception:
            pass
        # Ultimate fallback: navigate to search URL directly
        from urllib.parse import quote
        for pattern in ["/search?q={}", "/search?keyword={}", "/s?q={}", "/s?wd={}", "/all?keyword={}", "//search.jd.com/Search?keyword={}&enc=utf-8"]:
            try:
                search_url = page.url.split('/')[0] + '//' + page.url.split('/')[2] + pattern.format(quote(text))
                page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(1000)
                return {"action": "type", "text": text, "navigated_to": search_url}
            except Exception:
                continue
        raise Exception(f"Type failed: {e}")

    elif action == "extract":
        roles = extract_role_names(page)
        content = smart_extract(page)
        combined = "=== PAGE CONTENT ===\n" + content[:3000] + "\n\n=== INTERACTIVE ELEMENTS ===\n" + roles[:1500]
        return {"action": "extract", "dom": "", "text": combined[:8000]}

    elif action == "accessibility_click":
        role = cmd.get("role", "")
        name = cmd.get("name", "")
        # Textbox: use find_input directly — much more reliable than name matching
        if role == "textbox":
            try:
                el = find_input(page, "")
                el.click(timeout=3000)
                page.wait_for_timeout(1000)
                return {"action": "accessibility_click", "role": role, "name": name}
            except Exception as e:
                raise Exception(f"Cannot find textbox: {e}")
        ok = click_by_role_name(page, role, name)
        if ok:
            page.wait_for_timeout(1000)
            return {"action": "accessibility_click", "role": role, "name": name}
        raise Exception(f"Click by role='{role}' name='{name}' failed")

    elif action == "scroll":
        delta = 500 if cmd.get("direction") != "up" else -500
        page.evaluate(f"window.scrollBy(0, {delta})")
        return {"action": "scroll"}

    elif action == "screenshot":
        import base64
        img = page.screenshot(full_page=cmd.get("full_page", False))
        return {"action": "screenshot", "image_base64": base64.b64encode(img).decode()}

    elif action == "get_url":
        return {"action": "get_url", "url": page.url}

    else:
        raise Exception(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
