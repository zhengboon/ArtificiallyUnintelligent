"""
RoboVerse Discord watcher.

Two modes:
  python watcher.py login    # first-run: opens visible Chromium, you log in
                             # and navigate to the BH2026ROBOVERSE server.
                             # Saves session + auto-discovers channels.
  python watcher.py poll     # poll mode: opens visible Chromium, polls each
                             # channel, writes new messages to the dated
                             # info folder. This is what Task Scheduler runs.

State is kept in config.json (server_id, channels, last_seen msg id per
channel) and the Playwright profile dir (Discord session cookies).

Output: D:\\hackerverse\\info_<YYYY-MM-DD>\\msg_<NNN>.md
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeout
from rich.console import Console
from rich.logging import RichHandler

# --- paths
HERE = Path(__file__).parent
PROFILE_DIR = HERE / "profile"
CONFIG_PATH = HERE / "config.json"
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "watcher.log"

INFO_ROOT = Path(r"D:\hackerverse")  # dated info dirs land here

# --- logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True, show_path=False),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("watcher")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        "server_id": None,
        "server_url": None,
        "channels": [],       # [{id, name, last_seen_msg_id}]
        "last_msg_seq": 0,    # global counter for msg_<NNN>.md filenames within a day
        "last_msg_seq_date": None,  # YYYY-MM-DD this counter belongs to
    }


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Output file naming — continue per-day numbering
# ---------------------------------------------------------------------------
def next_msg_path(cfg: dict) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    info_dir = INFO_ROOT / f"info_{today}"
    info_dir.mkdir(exist_ok=True)

    # Reset counter if it's a new day, or scan existing files to continue.
    if cfg.get("last_msg_seq_date") != today:
        existing = sorted(info_dir.glob("msg_*.md"))
        if existing:
            m = re.search(r"msg_(\d+)\.md", existing[-1].name)
            cfg["last_msg_seq"] = int(m.group(1)) if m else 0
        else:
            cfg["last_msg_seq"] = 0
        cfg["last_msg_seq_date"] = today

    cfg["last_msg_seq"] += 1
    return info_dir / f"msg_{cfg['last_msg_seq']:03d}.md"


# ---------------------------------------------------------------------------
# Login + discovery
# ---------------------------------------------------------------------------
SERVER_URL_RE = re.compile(r"discord\.com/channels/(\d+)(?:/(\d+))?")


def cmd_login() -> None:
    cfg = load_config()
    log.info("Opening Chromium. Log in to Discord, then navigate to the "
             "BH2026ROBOVERSE server (any channel in it), then come back "
             "to this terminal and press Enter.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://discord.com/login")

        input("\n>>> Press Enter once you're on a channel inside the "
              "BH2026ROBOVERSE server... ")

        # Try to read the current URL from the active page; user may have
        # changed pages, so iterate over all pages.
        server_id = None
        cur_url = None
        for pg in ctx.pages:
            m = SERVER_URL_RE.search(pg.url)
            if m:
                server_id = m.group(1)
                cur_url = pg.url
                page = pg
                break

        if not server_id:
            log.error("Could not detect server URL. Are you on a channel "
                      "inside the server? URL should look like "
                      "https://discord.com/channels/<server>/<channel>")
            ctx.close()
            sys.exit(1)

        cfg["server_id"] = server_id
        cfg["server_url"] = f"https://discord.com/channels/{server_id}"
        log.info(f"Detected server_id = {server_id}")

        # Discover channels from the sidebar.
        # Sidebar links look like /channels/SERVER_ID/CHANNEL_ID. Voice
        # channels live in containers that have a 'voice' role indicator;
        # we filter by inspecting siblings.
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
                    // Try to read the channel name from the link text.
                    const name = (a.innerText || a.textContent || '').trim().split('\\n')[0];
                    // Detect voice channels by presence of a sibling with aria-label containing 'voice'.
                    const aria = a.getAttribute('aria-label') || '';
                    const isVoice = aria.toLowerCase().includes('(voice');
                    out.push({id: cid, name, isVoice});
                }
                return out;
            }""",
            server_id,
        )

        text_channels = [c for c in channels if not c["isVoice"] and c["name"]]
        log.info(f"Discovered {len(text_channels)} text channels:")
        for c in text_channels:
            log.info(f"  #{c['name']:30s}  ({c['id']})")

        # Merge with existing channel state (preserve last_seen if known).
        prev = {c["id"]: c for c in cfg.get("channels", [])}
        cfg["channels"] = [
            {
                "id": c["id"],
                "name": c["name"],
                "last_seen_msg_id": prev.get(c["id"], {}).get("last_seen_msg_id"),
            }
            for c in text_channels
        ]
        save_config(cfg)
        log.info(f"Saved config: {CONFIG_PATH}")
        ctx.close()


# ---------------------------------------------------------------------------
# Message extraction (DOM, runs in the page context)
# ---------------------------------------------------------------------------
MESSAGE_SCRAPER_JS = r"""
() => {
    // Find every message item currently rendered in the chat list.
    const items = document.querySelectorAll('li[id^="chat-messages-"]');
    const out = [];
    let lastAuthor = null;  // for grouped messages where author header is hidden
    let lastTimestamp = null;
    for (const li of items) {
        const m = li.id.match(/chat-messages-\d+-(\d+)/);
        if (!m) continue;
        const msgId = m[1];

        // Author — only present on the first message of a group.
        const authorEl = li.querySelector('[class*="username_"]');
        const author = authorEl ? authorEl.innerText.trim() : null;
        if (author) lastAuthor = author;

        // Timestamp (the <time> element with a datetime attribute).
        const timeEl = li.querySelector('time[datetime]');
        const iso = timeEl ? timeEl.getAttribute('datetime') : null;
        if (iso) lastTimestamp = iso;

        // Content body.
        const contentEl = li.querySelector('[id^="message-content-"]');
        let content = '';
        if (contentEl) {
            // Replace emoji <img alt=":smile:"> with their alt text.
            const clone = contentEl.cloneNode(true);
            for (const img of clone.querySelectorAll('img[alt]')) {
                img.replaceWith(document.createTextNode(img.alt));
            }
            content = clone.innerText.trim();
        }

        // Attachments (download links, image filenames).
        const atts = [];
        for (const a of li.querySelectorAll('a[href]')) {
            const href = a.getAttribute('href') || '';
            if (href.includes('cdn.discordapp.com') || href.includes('media.discordapp.net')) {
                atts.push(href);
            }
        }
        // Embedded image previews.
        for (const img of li.querySelectorAll('img[src]')) {
            const src = img.getAttribute('src') || '';
            if (src.includes('cdn.discordapp.com') || src.includes('media.discordapp.net')) {
                if (!atts.includes(src)) atts.push(src);
            }
        }

        out.push({
            id: msgId,
            author: lastAuthor || '(unknown)',
            timestamp: lastTimestamp,
            content,
            attachments: atts,
        });
    }
    return out;
}
"""


def poll_channel(page, channel: dict, server_id: str) -> list[dict]:
    """Navigate to a channel and return list of new messages since last poll."""
    url = f"https://discord.com/channels/{server_id}/{channel['id']}"
    log.info(f"  -> #{channel['name']}")
    page.goto(url, wait_until="domcontentloaded")

    # Wait for chat to render. We try a few selectors; Discord changes them.
    try:
        page.wait_for_selector('li[id^="chat-messages-"]', timeout=8000)
    except PWTimeout:
        log.warning(f"     no messages rendered after 8s, skipping")
        return []

    # Give late renders a moment.
    page.wait_for_timeout(1500)

    # Scroll to bottom to ensure we have the latest.
    try:
        page.evaluate(
            """() => {
                const scroller = document.querySelector('[class*="scroller-"], [data-list-id="chat-messages"]');
                if (scroller) scroller.scrollTop = scroller.scrollHeight;
            }"""
        )
        page.wait_for_timeout(500)
    except Exception:
        pass

    msgs = page.evaluate(MESSAGE_SCRAPER_JS)
    if not msgs:
        return []

    last_seen = channel.get("last_seen_msg_id")
    if last_seen is None:
        # First poll for this channel — just record the latest, don't dump
        # the whole channel history. (User has already pasted everything
        # up to today manually.)
        channel["last_seen_msg_id"] = msgs[-1]["id"]
        log.info(f"     first poll; baseline msg_id={msgs[-1]['id']} (no save)")
        return []

    last_seen_int = int(last_seen)
    new = [m for m in msgs if int(m["id"]) > last_seen_int]
    if new:
        channel["last_seen_msg_id"] = new[-1]["id"]
        log.info(f"     {len(new)} new message(s)")
    return new


# ---------------------------------------------------------------------------
# Save new messages
# ---------------------------------------------------------------------------
def fmt_message(channel_name: str, m: dict) -> str:
    ts = m.get("timestamp") or "(no timestamp)"
    author = m.get("author") or "(unknown)"
    content = m.get("content") or "(no text)"
    atts = m.get("attachments") or []

    lines = [
        f"**#{channel_name}** — `{m['id']}` — {author} — {ts}",
        "",
        content,
    ]
    if atts:
        lines.append("")
        lines.append("Attachments:")
        for a in atts:
            lines.append(f"- {a}")
    return "\n".join(lines)


def cmd_poll() -> None:
    cfg = load_config()
    if not cfg.get("server_id"):
        log.error("No server configured. Run `python watcher.py login` first.")
        sys.exit(2)

    server_id = cfg["server_id"]
    n_channels = len(cfg.get("channels", []))
    log.info(f"Polling {n_channels} channels on server {server_id}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Detect login state: if Discord redirects to /login we're stuck.
        page.goto(f"https://discord.com/channels/{server_id}", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        if "/login" in page.url:
            log.error("Not logged in — session expired. Run `python watcher.py login` "
                      "to re-authenticate.")
            ctx.close()
            sys.exit(3)

        all_new: list[tuple[str, dict]] = []
        for ch in cfg["channels"]:
            try:
                msgs = poll_channel(page, ch, server_id)
            except Exception as e:
                log.exception(f"     error polling #{ch['name']}: {e}")
                continue
            for m in msgs:
                all_new.append((ch["name"], m))

        ctx.close()

    if not all_new:
        log.info("No new messages this poll.")
        save_config(cfg)
        return

    # Write one combined .md file for this poll batch.
    out_path = next_msg_path(cfg)
    header = (
        f"# Discord poll @ {datetime.now(timezone.utc).isoformat()}\n\n"
        f"{len(all_new)} new message(s) across {len(set(c for c,_ in all_new))} channel(s).\n\n"
        "---\n\n"
    )
    body = "\n\n---\n\n".join(fmt_message(name, m) for name, m in all_new)
    out_path.write_text(header + body + "\n", encoding="utf-8")
    log.info(f"Wrote {len(all_new)} messages -> {out_path}")
    save_config(cfg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["login", "poll"], help="login = first-run bootstrap; poll = run a single poll cycle")
    args = ap.parse_args()
    t0 = time.time()
    try:
        if args.mode == "login":
            cmd_login()
        elif args.mode == "poll":
            cmd_poll()
    except KeyboardInterrupt:
        log.warning("Interrupted by user.")
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)
    log.info(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
