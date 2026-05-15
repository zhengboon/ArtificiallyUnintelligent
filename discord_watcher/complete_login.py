"""
One-shot script to finish setting up config.json when cmd_login()'s
URL auto-detection fails.

Usage:
    python complete_login.py <channel_url>

E.g.:
    python complete_login.py https://discord.com/channels/1493037912751734878/1493037913322033237

Opens Chromium with the SAME persistent profile (so your Discord login
is still there from the failed run_login.bat run), navigates to that URL,
reads channel list from the sidebar, saves config.json. Closes when done.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
PROFILE_DIR = HERE / "profile"
CONFIG_PATH = HERE / "config.json"

SERVER_URL_RE = re.compile(r"discord\.com/channels/(\d+)(?:/(\d+))?")


def main():
    if len(sys.argv) != 2:
        print("usage: python complete_login.py <discord channel url>")
        sys.exit(1)
    url = sys.argv[1].strip()
    m = SERVER_URL_RE.search(url)
    if not m:
        print(f"URL doesn't match the expected pattern: {url}")
        sys.exit(1)
    server_id = m.group(1)
    print(f"server_id: {server_id}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print(f"navigating to {url}")
        page.goto(url, wait_until="domcontentloaded")
        print("waiting 5s for Discord to render the sidebar...")
        page.wait_for_timeout(5000)

        # Same sidebar query the original cmd_login uses.
        channels = page.evaluate(
            """(server_id) => {
                const anchors = document.querySelectorAll(`a[href^='/channels/${server_id}/']`);
                const out = [];
                const seen = new Set();
                for (const a of anchors) {
                    const m = a.href.match(/\\/channels\\/\\d+\\/(\\d+)/);
                    if (!m) continue;
                    const cid = m[1];
                    if (seen.has(cid)) continue;
                    seen.add(cid);
                    const name = (a.innerText || a.textContent || '').trim().split('\\n')[0];
                    const aria = a.getAttribute('aria-label') || '';
                    const isVoice = aria.toLowerCase().includes('(voice');
                    out.push({id: cid, name, isVoice});
                }
                return out;
            }""",
            server_id,
        )

        text_channels = [c for c in channels if not c["isVoice"] and c["name"]]
        print(f"\nDiscovered {len(text_channels)} text channels:")
        for c in text_channels:
            print(f"  #{c['name']:30s}  ({c['id']})")

        if not text_channels:
            print("\nNo channels found — make sure you're logged in AND the URL is a channel inside the server.")
            print("If you see a Discord login screen in the Chromium window, log in there now and re-run.")
            input("Press Enter to close...")
            ctx.close()
            sys.exit(2)

        # Save config in the same format cmd_login does.
        cfg = {
            "server_id": server_id,
            "server_url": f"https://discord.com/channels/{server_id}",
            "channels": [
                {"id": c["id"], "name": c["name"], "last_seen_msg_id": None}
                for c in text_channels
            ],
            "last_msg_seq": 0,
            "last_msg_seq_date": None,
        }
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"\nSaved config: {CONFIG_PATH}")
        ctx.close()


if __name__ == "__main__":
    main()
