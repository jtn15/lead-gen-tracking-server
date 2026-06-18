from flask import Flask, request, send_file
import sqlite3
import datetime
import os
import io

app = Flask(__name__)

# Transparent 1x1 pixel GIF
PIXEL = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

DB_PATH = os.environ.get('RENDER_SQLITE_PATH', 'leads.db')

def init_db():
    """Ensure the tracking table exists so the server doesn't crash if uploaded without a DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        drip_step INTEGER DEFAULT 1,
        status TEXT,
        sent_at TIMESTAMP,
        opened_at TIMESTAMP,
        clicked_at TIMESTAMP,
        replied_at TIMESTAMP,
        reply_message TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

def update_tracking(lead_id, action):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        
        # We use INSERT OR IGNORE / UPDATE logic here to ensure it logs even if the lead isn't fully synced yet
        cursor.execute("SELECT id FROM email_tracking WHERE lead_id = ?", (lead_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO email_tracking (lead_id, status) VALUES (?, 'Unknown')", (lead_id,))
            
        if action == "open":
            cursor.execute("UPDATE email_tracking SET status = 'Opened', opened_at = ? WHERE lead_id = ? AND status != 'Replied' AND status != 'Clicked'", (now, lead_id))
        elif action == "click":
            cursor.execute("UPDATE email_tracking SET status = 'Clicked', clicked_at = ? WHERE lead_id = ? AND status != 'Replied'", (now, lead_id))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Tracking error: {e}")

@app.route('/')
def index():
    return "Tracking Server is Online!"

@app.route('/track/open/<int:lead_id>')
def track_open(lead_id):
    update_tracking(lead_id, "open")
    return send_file(io.BytesIO(PIXEL), mimetype='image/gif')

@app.route('/track/click/<int:lead_id>')
def track_click(lead_id):
    url = request.args.get('url', 'http://example.com')
    update_tracking(lead_id, "click")
    return f"<html><head><meta http-equiv='refresh' content='0;url={url}'></head><body></body></html>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
