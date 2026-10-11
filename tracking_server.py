from flask import Flask, request, send_file
import sqlite3
import datetime
import os
import io

app = Flask(__name__)

# Transparent 1x1 pixel GIF
PIXEL = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")

def update_tracking(lead_id, action):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        
        if action == "open":
            cursor.execute("UPDATE email_tracking SET status = 'Opened', opened_at = ? WHERE lead_id = ? AND status != 'Replied'", (now, lead_id))
        elif action == "click":
            cursor.execute("UPDATE email_tracking SET status = 'Clicked', clicked_at = ? WHERE lead_id = ? AND status != 'Replied'", (now, lead_id))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Tracking error: {e}")

@app.route('/track/open/<int:lead_id>')
def track_open(lead_id):
    update_tracking(lead_id, "open")
    return send_file(io.BytesIO(PIXEL), mimetype='image/gif')

@app.route('/track/click/<int:lead_id>')
def track_click(lead_id):
    url = request.args.get('url', 'http://example.com')
    update_tracking(lead_id, "click")
    # Redirect to the actual URL
    return f"<html><head><meta http-equiv='refresh' content='0;url={url}'></head><body></body></html>"

if __name__ == '__main__':
    # This server should ideally run on a public VPS
    app.run(host='0.0.0.0', port=5000)
