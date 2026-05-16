# Discord watcher — two-piece setup

Two pieces working together:

| Piece | Trigger | What it captures | ToS risk |
|---|---|---|---|
| **`notif_listener.py`** | always-on, polls Windows every 5 sec | Real-time toast notifications from Discord (titles + truncated bodies, only for unmuted channels) | **Zero** — reads Windows notifications via the official UserNotificationListener API. Never touches Discord's servers. |
| **`watcher.py`** | Task Scheduler, every 6 hours | Full message content from every channel (including muted ones) via a real Chromium browser session | Low (account automation against Discord ToS — at 6 h interval, indistinguishable from a human checking in) |

Output for both goes into `D:\hackerverse\info_<YYYY-MM-DD>\` with different filename prefixes:
- `notif_<timestamp>_<id>.md` — single notification (real-time)
- `msg_<NNN>.md` — batch of polled messages (every 6 h)

## Prerequisites (one-time, you do these)

1. **Enable Windows notification access:**
   - Settings → Privacy & security → Notifications → **"Let apps access your notifications"** = On
2. **Unmute channels in Discord** that you want the listener to capture:
   - In each channel: right-click → Notification Settings → **"All Messages"**
   - Channels stay muted = nothing for the listener to catch; the 6-hour poll will still grab them
3. **Run `run_login.bat` once** to log into Discord in the Playwright Chromium session (see "First-run setup" below)

---

## First-run setup

### A. Log Playwright into Discord

Double-click **`run_login.bat`** in this folder.

1. Chromium opens to `discord.com/login`
2. Log in normally
3. Click any channel inside the **BH2026ROBOVERSE** server, wait for messages to render
4. Come back to the terminal and press **Enter**
5. It prints the discovered channels and closes Chromium
6. Session is saved to `profile/` — won't need to re-login until Discord boots you

### B. Start the notification listener

Double-click **`run_listener.bat`**.

- On first run, Windows pops a permission dialog asking if Python can access your notifications. **Click Yes**.
- The listener runs hidden (no console window). Check `logs/notif_listener.log` to confirm it's alive.
- Send yourself a Discord message from another device and confirm a `notif_*.md` file shows up in today's `info_<date>/` folder.

### C. Test a manual poll

Double-click **`run_poll.bat`** to do one polling cycle right now.

- First poll baselines every channel — nothing is saved.
- Run it a second time after a new message has been posted to confirm capture.

---

## Scheduling (after manual test works)

Open an **admin PowerShell** and run **both** of these:

### Notification listener — at logon

```powershell
$action = New-ScheduledTaskAction `
  -Execute "D:\hackerverse\discord_watcher\run_listener.bat" `
  -WorkingDirectory "D:\hackerverse\discord_watcher"

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:UserName

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "RoboVerseDiscordNotifListener" `
  -Action $action -Trigger $trigger -Settings $settings `
  -RunLevel Highest `
  -Description "Background listener for Discord Windows toasts."
```

### Playwright poll — every 6 hours

```powershell
$action = New-ScheduledTaskAction `
  -Execute "D:\hackerverse\discord_watcher\run_poll.bat" `
  -WorkingDirectory "D:\hackerverse\discord_watcher"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
  -RepetitionInterval (New-TimeSpan -Hours 6)

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "RoboVerseDiscordPoll" `
  -Action $action -Trigger $trigger -Settings $settings `
  -Description "Poll the BrainHack 2026 RoboVerse Discord every 6 hours."
```

Disable later:
```powershell
Unregister-ScheduledTask -TaskName "RoboVerseDiscordNotifListener" -Confirm:$false
Unregister-ScheduledTask -TaskName "RoboVerseDiscordPoll" -Confirm:$false
```

Inspect / run manually:
```powershell
Get-ScheduledTask | Where-Object TaskName -like "RoboVerseDiscord*"
Start-ScheduledTask -TaskName "RoboVerseDiscordPoll"
```

---

## Control panel (localhost dashboard)

Double-click **`run_server.bat`** to launch a tiny Flask app at
**http://localhost:5050/**. Browser-viewable dashboard with:

- buttons to trigger `login` / `poll` / `scrape`
- live log of whatever's currently running
- "notes" — you and Claude can both leave messages here (shared, two-way)
- history of recent runs

Why bother:

- **You see progress** without staring at a terminal
- **Claude triggers runs** via `curl http://localhost:5050/api/run/scrape` from PowerShell
- **Single source of truth** in `server_state.json` — both sides see the same view

The server stays running until you close the terminal (or Ctrl+C). Only
binds to 127.0.0.1, no network exposure.

Endpoints (for the curious / scripting):

| Method | Path | What |
|---|---|---|
| GET | `/` | the dashboard |
| GET | `/api/status` | full state JSON |
| POST | `/api/run/<cmd>` | trigger `login` \| `poll` \| `scrape` (409 if one's running) |
| POST | `/api/cancel` | terminate the running subprocess |
| POST | `/api/note` | body: `{"text": "...", "from": "user|claude"}` |
| POST | `/api/notes/clear` | wipe the notes list |
| GET | `/api/logs/raw` | tail of `logs/watcher.log` |

## Full-history scrape (audit mode)

Double-click **`run_scrape.bat`** for a one-shot dump of every message
currently visible in each channel — not just new ones since the last poll.

- Output: `D:\hackerverse\info_<today>_scrape\<channel_name>.md` — one file per channel.
- The script visits each channel, scrolls all the way up (Discord lazy-loads older messages page by page), then extracts everything.
- **Slower than `poll`** — ~30 s of scrolling per channel plus Discord's load latency. Plan for ~5 min total.
- Use this when Claude (or any reviewer) needs to cross-check the repo docs against the source-of-truth Discord content. `poll` is for routine updates; `scrape` is for audits.
- Same Playwright session as the others — re-run `run_login.bat` if Discord boots you out.

---

## Files

| Path | What |
|---|---|
| `watcher.py` | Playwright tool with 3 modes: `login`, `poll`, `scrape` |
| `notif_listener.py` | Windows toast listener (always on) |
| `config.json` | server_id, channels, last-seen msg id per channel |
| `profile/` | Playwright user-data dir (Discord cookies for the polled session) |
| `logs/watcher.log` | one line per poll |
| `logs/notif_listener.log` | every Discord toast we see |
| `run_login.bat` | first-run / re-login wrapper |
| `run_poll.bat` | what Task Scheduler invokes every 6 h (incremental) |
| `run_scrape.bat` | manual full-history dump for audits |
| `run_listener.bat` | what Task Scheduler invokes at logon |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Listener doesn't save anything | Confirm "Let apps access your notifications" is On; confirm Discord channel is unmuted; check `logs/notif_listener.log` for "Permission denied" |
| Listener saves notifications from other apps | Shouldn't — the script filters `app_name == "Discord"`. Check the log to confirm. If you see other apps' messages in `notif_*.md`, the filter broke. |
| `Not logged in — session expired` in poll log | Run `run_login.bat` again to re-auth Playwright |
| `no messages rendered after 8s` in poll log | Discord slow that run; will pick up new messages on the next 6 h cycle |
| Polling Chromium window won't close itself | `taskkill /F /IM chrome.exe` (careful — closes any other Chrome too) |
| Discord shows a "suspicious activity" check on your account | Stop the poll task (`Unregister-ScheduledTask ...`) for a few days. The listener is safe to keep running. Re-login manually in the desktop app. |

---

## Privacy

- `profile/` contains your Discord session cookies. **Do not commit it to git.** Don't share that folder.
- `config.json` contains the BH2026ROBOVERSE server ID (harmless on its own, but it identifies the server you're scraping).
- `logs/*.log` contain notification titles + bodies. Be aware before sharing logs.
- The dated `info_*/` folders contain everything captured. Standard care.
