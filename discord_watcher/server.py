"""
Local control panel for the Discord watcher.

A Flask app that exposes:
  - A browser dashboard at http://localhost:5050/ — humans use this to
    watch progress + trigger actions + leave notes.
  - REST endpoints — Claude uses these from PowerShell (curl) to drive
    the same actions and read state from the other side.

Shared state lives in `server_state.json` so both sides see the same view.

Endpoints:
  GET  /                  → dashboard HTML (auto-refreshes ~1.5s)
  GET  /api/status        → JSON state
  POST /api/run/<cmd>     → trigger one of: login | poll | scrape
                            (409 if a command is already running)
  POST /api/cancel        → kill the running watcher subprocess
  POST /api/note          → body: {text, from} — both sides leave notes
  GET  /api/logs/raw      → last N lines of logs/watcher.log

Run with:
  python server.py            # binds 127.0.0.1:5050
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

HERE = Path(__file__).parent
WATCHER_PY = HERE / "watcher.py"
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
STATE_FILE = HERE / "server_state.json"
SERVER_LOG = LOG_DIR / "server.log"

PORT = 5050

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(SERVER_LOG, encoding="utf-8"),
    ],
)
log = logging.getLogger("server")


# ---------------------------------------------------------------------------
# State (persisted to JSON so both sides see the same thing)
# ---------------------------------------------------------------------------
state_lock = threading.RLock()
current_proc: subprocess.Popen | None = None
current_log_buf: deque = deque(maxlen=400)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_state() -> dict:
    return {
        "current_action": None,    # {cmd, started_at, log_lines, pid}
        "history": [],             # list of finished actions, newest first
        "notes": [],               # list of {text, at, from}
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.exception("state file corrupt; resetting")
    return empty_state()


def save_state(s: dict) -> None:
    STATE_FILE.write_text(json.dumps(s, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------
def _runner_thread(cmd: str) -> None:
    """Spawn the watcher subprocess and stream stdout into state."""
    global current_proc
    log.info("starting watcher subprocess: %s", cmd)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(WATCHER_PY), cmd],
            cwd=str(HERE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        log.exception("failed to start subprocess")
        with state_lock:
            s = load_state()
            s["current_action"] = None
            s["history"].insert(0, {
                "cmd": cmd, "started_at": now_iso(), "ended_at": now_iso(),
                "exit_code": -1, "error": str(e), "log_lines": [],
            })
            s["history"] = s["history"][:30]
            save_state(s)
        return

    with state_lock:
        current_proc = proc
        s = load_state()
        s["current_action"] = {
            "cmd": cmd,
            "started_at": now_iso(),
            "pid": proc.pid,
        }
        save_state(s)
    current_log_buf.clear()

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        current_log_buf.append(line)
        # Persist a rolling window of recent log lines into state every line —
        # the dashboard polls /api/status to see them.
        with state_lock:
            s = load_state()
            if s.get("current_action"):
                s["current_action"]["log_lines"] = list(current_log_buf)[-80:]
                save_state(s)

    proc.wait()
    log.info("watcher subprocess exited code=%s", proc.returncode)

    with state_lock:
        s = load_state()
        cur = s.get("current_action") or {"cmd": cmd, "started_at": now_iso()}
        cur["ended_at"] = now_iso()
        cur["exit_code"] = proc.returncode
        cur["log_lines"] = list(current_log_buf)[-120:]
        s["history"].insert(0, cur)
        s["history"] = s["history"][:30]
        s["current_action"] = None
        save_state(s)
        current_proc = None


def start_runner(cmd: str) -> tuple[bool, str]:
    """Spawn the runner thread. Returns (ok, message)."""
    if cmd not in {"login", "poll", "scrape"}:
        return False, f"unknown command '{cmd}'"
    with state_lock:
        s = load_state()
        if s.get("current_action"):
            return False, "another command is already running"
        s["current_action"] = {"cmd": cmd, "started_at": now_iso(), "log_lines": []}
        save_state(s)
    threading.Thread(target=_runner_thread, args=(cmd,), daemon=True).start()
    return True, f"started '{cmd}'"


def cancel_runner() -> tuple[bool, str]:
    global current_proc
    with state_lock:
        if not current_proc:
            return False, "nothing running"
        try:
            current_proc.terminate()
        except Exception as e:
            return False, f"terminate failed: {e}"
    return True, "cancellation requested"


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML, port=PORT)


@app.route("/api/status")
def api_status():
    return jsonify(load_state())


@app.route("/api/run/<cmd>", methods=["POST"])
def api_run(cmd: str):
    ok, msg = start_runner(cmd)
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 409)


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    ok, msg = cancel_runner()
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 409)


@app.route("/api/note", methods=["POST"])
def api_note():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    sender = (payload.get("from") or "user").strip() or "user"
    if not text:
        return jsonify({"error": "empty"}), 400
    with state_lock:
        s = load_state()
        s["notes"].insert(0, {"text": text, "at": now_iso(), "from": sender})
        s["notes"] = s["notes"][:50]
        save_state(s)
    return jsonify({"ok": True})


@app.route("/api/notes/clear", methods=["POST"])
def api_notes_clear():
    with state_lock:
        s = load_state()
        s["notes"] = []
        save_state(s)
    return jsonify({"ok": True})


@app.route("/api/logs/raw")
def api_logs_raw():
    """Tail of watcher.log so the dashboard can show it."""
    p = LOG_DIR / "watcher.log"
    if not p.exists():
        return jsonify({"lines": []})
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"lines": lines})


# ---------------------------------------------------------------------------
# Dashboard HTML (single page, vanilla JS, polls /api/status)
# ---------------------------------------------------------------------------
DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>discord_watcher — control</title>
<style>
  body { font: 14px/1.45 ui-monospace, 'Cascadia Mono', Consolas, monospace;
         max-width: 1000px; margin: 1.2rem auto 4rem; padding: 0 1rem;
         color: #1a1a1a; background: #fafafa; }
  h1 { font-size: 1.3rem; margin: 0 0 0.4rem; }
  h2 { font-size: 1rem; margin: 1.4rem 0 0.4rem; color: #555; text-transform: uppercase; letter-spacing: 0.05em; }
  button { font-family: inherit; font-size: 0.95rem; padding: 0.45rem 0.9rem;
           border: 1px solid #ccc; background: #fff; cursor: pointer;
           border-radius: 4px; margin: 0.2rem 0.3rem 0.2rem 0; }
  button:hover { background: #f0f0f0; }
  button.primary { background: #2962ff; color: white; border-color: #2962ff; }
  button.danger  { background: #e53935; color: white; border-color: #e53935; }
  pre { background: #1e1e1e; color: #e1e1e1; padding: 0.8rem 1rem;
        font-size: 12.5px; line-height: 1.4; border-radius: 4px;
        max-height: 320px; overflow: auto; white-space: pre-wrap; }
  .card { background: white; border: 1px solid #e0e0e0; border-radius: 4px;
          padding: 0.8rem 1rem; margin: 0.4rem 0; }
  .idle { color: #888; }
  .running { background: #fff8e1; border-color: #f0c400; }
  .ok { color: #2e7d32; }
  .fail { color: #c62828; }
  input[type=text] { width: 70%; padding: 0.45rem; border: 1px solid #ccc;
                     border-radius: 4px; font-family: inherit; }
  .note { background: #f0f7ff; border-left: 4px solid #2962ff; padding: 0.5rem 0.75rem;
          margin: 0.3rem 0; border-radius: 0 4px 4px 0; }
  .note .meta { font-size: 0.85em; color: #666; }
  .from-claude { border-left-color: #6a3eff; background: #f4eeff; }
  .from-user   { border-left-color: #2962ff; background: #eef4ff; }
  .history-row { padding: 0.3rem 0; border-bottom: 1px dashed #ddd; }
  .history-row:last-child { border-bottom: none; }
  .small { font-size: 0.85em; color: #666; }
</style>
</head><body>

<h1>discord_watcher — control panel</h1>
<div class="small">localhost:{{ port }} · refreshes every 1.5s</div>

<h2>Actions</h2>
<div>
  <button class="primary" onclick="run('login')">login (first-run / re-auth)</button>
  <button class="primary" onclick="run('poll')">poll (new msgs only)</button>
  <button class="primary" onclick="run('scrape')">scrape (full history)</button>
  <button class="danger"  onclick="cancel()">cancel running</button>
</div>

<h2>Current</h2>
<div id="current" class="card idle">idle</div>

<h2>Live log (current run)</h2>
<pre id="livelog">(nothing running)</pre>

<h2>Notes (you ↔ Claude)</h2>
<div>
  <input id="note-text" type="text" placeholder="leave a note — Claude reads via /api/status">
  <button onclick="postNote()">post</button>
  <button onclick="clearNotes()">clear all</button>
</div>
<div id="notes"></div>

<h2>Recent runs</h2>
<div id="history" class="card"></div>

<script>
const escape = s => { const d = document.createElement('div'); d.innerText = s ?? ''; return d.innerHTML; };

async function refresh() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();

    const cur = document.getElementById('current');
    const livelog = document.getElementById('livelog');
    if (s.current_action) {
      cur.className = 'card running';
      cur.innerHTML = `<b>${escape(s.current_action.cmd)}</b> running` +
        ` &middot; started ${escape(s.current_action.started_at)}` +
        (s.current_action.pid ? ` &middot; pid ${s.current_action.pid}` : '');
      livelog.innerText = (s.current_action.log_lines || []).join('\n') || '(starting...)';
    } else {
      cur.className = 'card idle';
      cur.innerText = 'idle — nothing running';
      livelog.innerText = '(nothing running)';
    }

    document.getElementById('notes').innerHTML = (s.notes || []).map(n => {
      const cls = (n.from || 'user').toLowerCase() === 'claude' ? 'from-claude' : 'from-user';
      return `<div class="note ${cls}"><div class="meta">${escape(n.from || 'user')} · ${escape(n.at)}</div>${escape(n.text)}</div>`;
    }).join('') || '<div class="small">(no notes yet)</div>';

    document.getElementById('history').innerHTML = (s.history || []).slice(0, 8).map(h => {
      const ok = h.exit_code === 0;
      return `<div class="history-row"><b>${escape(h.cmd)}</b> · ${escape(h.started_at)} → ${escape(h.ended_at)} · <span class="${ok ? 'ok' : 'fail'}">exit ${escape(h.exit_code)}</span></div>`;
    }).join('') || '<div class="small">no runs yet</div>';
  } catch (e) {
    console.error(e);
  }
}

async function run(cmd) {
  const r = await fetch(`/api/run/${cmd}`, { method: 'POST' });
  if (r.status === 409) {
    const j = await r.json(); alert(j.message);
  }
  refresh();
}
async function cancel() {
  await fetch('/api/cancel', { method: 'POST' });
  refresh();
}
async function postNote() {
  const t = document.getElementById('note-text').value.trim();
  if (!t) return;
  await fetch('/api/note', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ text: t, from: 'user' })
  });
  document.getElementById('note-text').value = '';
  refresh();
}
async function clearNotes() {
  await fetch('/api/notes/clear', { method: 'POST' });
  refresh();
}
document.getElementById('note-text').addEventListener('keydown', e => {
  if (e.key === 'Enter') postNote();
});

setInterval(refresh, 1500);
refresh();
</script>
</body></html>
"""


def main():
    if not STATE_FILE.exists():
        save_state(empty_state())
    log.info("starting discord_watcher control panel on http://localhost:%d/", PORT)
    log.info("state file: %s", STATE_FILE)
    log.info("watcher script: %s", WATCHER_PY)
    # threaded=True so the runner thread can update state while requests flow
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
