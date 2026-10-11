"""Public tracking server (deploy to Render). Records email opens/clicks; the desktop app pulls them via /events.

Secret: set the TRACKING_SECRET env var, or upload tracking_secret.txt next to this file (same text as the app's tracking_secret.txt).
Optional: DATA_DIR (where tracking_events.db lives; Render's free disk is wiped on redeploy, the app keeps its own copy).
"""
import datetime
import hashlib
import hmac
import io
import os
import sqlite3
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, redirect, request, send_file

app = Flask(__name__)

# Transparent 1x1 pixel GIF
PIXEL = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_secret():
    """TRACKING_SECRET env var wins; otherwise read tracking_secret.txt uploaded next to this file."""
    value = os.environ.get("TRACKING_SECRET", "").strip()
    if value:
        return value
    try:
        with open(os.path.join(HERE, "tracking_secret.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


SECRET = _load_secret()
DB_PATH = os.path.join(os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__))), "tracking_events.db")
MAX_EVENTS_PER_PULL = 1000
MAX_USER_AGENT = 200


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL,"
        " kind TEXT NOT NULL, ts TEXT NOT NULL, user_agent TEXT)")
    return conn


def _sign(kind, lead_id, url=""):
    message = f"{kind}|{lead_id}|{url}".encode("utf-8")
    return hmac.new(SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()[:32]


def _valid(kind, lead_id, signature, url=""):
    return bool(SECRET) and hmac.compare_digest(_sign(kind, lead_id, url), signature or "")


def _record(lead_id, kind):
    conn = _db()
    try:
        conn.execute("INSERT INTO events (lead_id, kind, ts, user_agent) VALUES (?,?,?,?)",
                     (lead_id, kind, datetime.datetime.now().isoformat(timespec="seconds"),
                      request.headers.get("User-Agent", "")[:MAX_USER_AGENT]))
        conn.commit()
    finally:
        conn.close()


@app.route("/track/open/<int:lead_id>")
def track_open(lead_id):
    if _valid("open", lead_id, request.args.get("s")):
        _record(lead_id, "open")
    response = send_file(io.BytesIO(PIXEL), mimetype="image/gif")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.route("/track/click/<int:lead_id>")
def track_click(lead_id):
    url = request.args.get("url", "")
    if urlparse(url).scheme not in ("http", "https") or not _valid("click", lead_id, request.args.get("s"), url):
        abort(400)
    _record(lead_id, "click")
    return redirect(url, code=302)


@app.route("/events")
def events():
    token = request.headers.get("X-Tracking-Token", "")
    if not SECRET or not hmac.compare_digest(SECRET, token):
        abort(403)
    after = request.args.get("after", 0, type=int)
    conn = _db()
    try:
        rows = conn.execute("SELECT id, lead_id, kind, ts FROM events WHERE id > ? ORDER BY id LIMIT ?",
                            (after, MAX_EVENTS_PER_PULL)).fetchall()
        max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
    finally:
        conn.close()
    return jsonify(events=[{"id": r[0], "lead_id": r[1], "kind": r[2], "ts": r[3]} for r in rows], max_id=max_id)


@app.route("/")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
