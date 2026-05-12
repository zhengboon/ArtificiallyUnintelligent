"""
RoboVerse Discord notification listener.

Watches Windows toast notifications via the UserNotificationListener API
and saves any *new* Discord notification into the dated info folder.

Zero Discord ToS risk: this never talks to Discord's servers. It only reads
notifications your own Windows machine has received and is displaying.

Caveats:
- Only catches notifications that Discord actually emits. Muted channels =
  silent = nothing to catch.
- Notification bodies are truncated by Discord (~100-200 chars typical).
- Run via `run_listener.bat`. Stays alive in the background forever.

Output: D:\\hackerverse\\info_<YYYY-MM-DD>\\notif_<ts>_<id>.md
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from winsdk.windows.ui.notifications.management import UserNotificationListener
from winsdk.windows.ui.notifications import (
    NotificationKinds,
    UserNotificationListenerAccessStatus,
)

HERE = Path(__file__).parent
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "notif_listener.log"

INFO_ROOT = Path(r"D:\hackerverse")
POLL_SEC = 5  # how often we ask Windows for the current notification list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("notif")


def today_info_dir() -> Path:
    d = INFO_ROOT / f"info_{datetime.now().strftime('%Y-%m-%d')}"
    d.mkdir(exist_ok=True)
    return d


def save_notification(notif_id: int, app: str, title: str, body: str) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = today_info_dir() / f"notif_{ts}_{notif_id}.md"
    content = (
        f"# Notification @ {datetime.now(timezone.utc).isoformat()}\n\n"
        f"**App:** {app}\n"
        f"**Title:** {title}\n\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def extract_text(notif) -> tuple[str, str]:
    """Pull (title, body) out of a UserNotification's ToastGeneric binding."""
    try:
        visual = notif.notification.visual
        toast = visual.get_binding("ToastGeneric")
        if toast is None:
            return ("", "")
        texts = [t.text for t in toast.get_text_elements()]
        if not texts:
            return ("", "")
        return (texts[0], "\n".join(texts[1:]))
    except Exception:
        return ("", "")


def app_name(notif) -> str:
    try:
        return notif.app_info.display_info.display_name or "(unknown)"
    except Exception:
        return "(unknown)"


async def request_permission(listener) -> bool:
    status = await listener.request_access_async()
    if status == UserNotificationListenerAccessStatus.ALLOWED:
        return True
    log.error(
        "Permission denied. Enable: Settings -> Privacy & security -> "
        "Notifications -> 'Let apps access your notifications' = On"
    )
    return False


async def main() -> None:
    listener = UserNotificationListener.get_current()
    if not await request_permission(listener):
        sys.exit(1)
    log.info("Notification listener started. Watching for Discord toasts.")

    # Baseline existing notifications so we don't dump everything that's
    # currently in the Action Center on startup.
    seen: set[int] = set()
    bootstrap = await listener.get_notifications_async(NotificationKinds.TOAST)
    for n in bootstrap:
        seen.add(n.id)
    log.info(f"Baselined {len(seen)} existing toast notification(s).")

    saved_count = 0
    while True:
        try:
            notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception:
            log.exception("get_notifications_async failed; retrying after sleep")
            await asyncio.sleep(POLL_SEC * 2)
            continue

        for n in notifs:
            if n.id in seen:
                continue
            seen.add(n.id)
            app = app_name(n)
            if app != "Discord":
                # Other apps' toasts: ignore.
                continue
            title, body = extract_text(n)
            path = save_notification(n.id, app, title, body)
            saved_count += 1
            log.info(f"  saved -> {path.name}  ({title[:60]})")

        await asyncio.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by user.")
