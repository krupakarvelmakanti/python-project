import http.server
import socketserver
import webbrowser
import threading
import datetime
import time
import json
import os
import hashlib
from urllib.parse import parse_qs, urlparse

print("STARTING APP...")

DATA_FILE = "data.json"

users = {}
usage_log = []
timetable = []

# -------- PASSWORD --------
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

# -------- LOAD / SAVE --------
def load_data():
    global users, usage_log, timetable

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": {}, "usage": [], "tasks": []}, f)

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

            users = data.get("users", {})
            usage_log = data.get("usage", [])

            raw_tasks = data.get("tasks", [])
            timetable = []

            for t in raw_tasks:
                if isinstance(t, dict) and "task" in t and "day" in t and "time" in t:
                    timetable.append(t)
                else:
                    print(" Skipped bad task:", t)

    except Exception as e:
        print("LOAD ERROR:", e)
        users, usage_log, timetable = {}, [], []

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "users": users,
                "usage": usage_log,
                "tasks": timetable
            }, f, indent=4)
    except Exception as e:
        print("SAVE ERROR:", e)

# -------- AI --------
def get_ai():
    if len(usage_log) < 2:
        return "Add more data for insights."

    hrs = [x["hours"] for x in usage_log if isinstance(x.get("hours"), (int, float))]
    if len(hrs) < 2:
        return "Need valid usage data."

    avg = round(sum(hrs)/len(hrs), 2)
    trend = hrs[-1] - hrs[-2]

    msg = f"Average: {avg} hrs | "

    if avg > 7:
        msg += "⚠️ Reduce usage | "
    if trend > 1:
        msg += "📈 Increasing usage | "
    if avg < 4:
        msg += "✅ Good habit | "

    return msg

# -------- ALARM --------
def alarm_runner():
    while True:
        try:
            now = datetime.datetime.now()
            day = now.strftime("%a")
            cur_time = now.strftime("%H:%M")

            for t in timetable:
                if (isinstance(t, dict) and 
                    t.get("day") == day and 
                    t.get("time") == cur_time and 
                    t.get("task")):
                    print(" ALARM:", t["task"])
        except:
            pass

        time.sleep(20)

# -------- HTML --------
def page(content):
    return """<!DOCTYPE html>
<html>
<head>
<title>Smart Life Manager</title>

<style>
body {
    font-family: Arial;
    background: linear-gradient(120deg, #89f7fe, #66a6ff);
    text-align: center;
    margin: 0;
    padding: 20px;
}

h1 { color:#0d6efd; }

.container {
    display:flex;
    flex-wrap:wrap;
    justify-content:center;
    gap:20px;
    max-width: 1200px;
    margin: 0 auto;
}

.card {
    background:white;
    padding:20px;
    width:300px;
    border-radius:15px;
    box-shadow:0 5px 15px rgba(0,0,0,0.2);
}

input, button {
    width:90%;
    padding:8px;
    margin:5px 0;
    box-sizing: border-box;
}

button {
    background:#0d6efd;
    color:white;
    border:none;
    border-radius:5px;
    cursor: pointer;
}

button:hover {
    background:#0b5ed7;
}

table {
    width:100%;
    margin-top:10px;
    border-collapse: collapse;
}

th, td {
    padding:8px;
    border:1px solid #ddd;
    text-align:left;
}

th {
    background:#f8f9fa;
}

.ai {
    background:#e7f1ff;
    padding:20px;
    margin:20px auto;
    max-width:600px;
    border-radius:10px;
}
</style>

</head>
<body>

<h1> DIGITAL DETOX TRACKER</h1>

""" + content + """

</body>
</html>
"""

# -------- SERVER --------
class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

class Handler(http.server.BaseHTTPRequestHandler):
    def parse_path(self):
        parsed = urlparse(self.path)
        return parsed.path

    def is_authenticated(self):
        cookie_user = self.get_cookie_user()
        return cookie_user is not None and cookie_user in users

    def get_cookie_user(self):
        cookie = self.headers.get('Cookie', '')
        if 'user=' in cookie:
            return cookie.split('user=')[1].split(';')[0]
        return None

    def set_auth_cookie(self, username):
        self.send_header('Set-Cookie', f'user={username}; Path=/; Max-Age=3600')

    def do_GET(self):
        try:
            path = self.parse_path()
            
            if path == "/dashboard" and not self.is_authenticated():
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return

            if path == "/dashboard":
                # Build alarms table
                alarms_html = ""
                for t in timetable:
                    alarms_html += f"<tr><td>{t.get('day', 'N/A')}</td><td>{t.get('time', 'N/A')}</td><td>{t.get('task', 'N/A')}</td></tr>"
                
                if alarms_html == "":
                    alarms_html = "<tr><td colspan='3'>No tasks added yet</td></tr>"

                # Build usage table
                usage_html = ""
                for u in usage_log[-10:]:
                    usage_html += f"<tr><td>{u.get('date', 'N/A')}</td><td>{u.get('hours', 0):.1f}</td></tr>"
                
                if usage_html == "":
                    usage_html = "<tr><td colspan='2'>No usage data yet</td></tr>"

                content = f"""
                <div class="container">

                    <div class="card">
                        <h3> Add Timetable</h3>
                        <form method="POST" action="/add_task">
                            <input name="task" placeholder="Task (e.g. Drink water)" required>
                            <input name="day" placeholder="Mon" required>
                            <input name="time" placeholder="HH:MM (e.g. 09:00)" required>
                            <button>Add</button>
                        </form>
                    </div>

                    <div class="card">
                        <h3> Screen Usage</h3>
                        <form method="POST" action="/add_usage">
                            <input name="hours" type="number" step="0.1" placeholder="Hours (e.g. 6.5)" min="0" max="24" required>
                            <button>Add</button>
                        </form>
                    </div>

                </div>

                <div class="container">

                    <div class="card">
                        <h3> Timetable</h3>
                        <table>
                            <tr><th>Day</th><th>Time</th><th>Task</th></tr>
                            {alarms_html}
                        </table>
                    </div>

                    <div class="card">
                        <h3> Recent Usage</h3>
                        <table>
                            <tr><th>Date</th><th>Hours</th></tr>
                            {usage_html}
                        </table>
                    </div>

                </div>

                <div class="ai">
                     AI Suggestion:<br>
                    {get_ai()}
                </div>
                """

            else:
                content = """
                <div class="container">
                    <div class="card" style="max-width:400px; margin: auto;">
                        <h3> Login / Signup</h3>
                        <form method="POST" action="/auth">
                            <input name="u" placeholder="Username" required>
                            <input name="p" type="password" placeholder="Password" required>
                            <button>Login / Signup</button>
                        </form>
                        <p style="font-size:12px; color:#666;">
                            Auto-creates account if new user
                        </p>
                    </div>
                </div>
                """

            html = page(content)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        except Exception as e:
            print("GET ERROR:", e)
            self.send_error(500, f"Internal server error: {str(e)}")

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(length).decode()
            data = parse_qs(post_data)

            path = self.parse_path()

            if path == "/auth":
                u = data.get('u', [''])[0].strip()
                p = hash_password(data.get('p', [''])[0])

                if u:
                    if u not in users:
                        users[u] = p
                        save_data()
                        print(f"New user created: {u}")

                    if users.get(u) == p:
                        self.send_response(303)
                        self.send_header("Location", "/dashboard")
                        self.set_auth_cookie(u)
                        self.end_headers()
                        return
                    else:
                        self.send_response(303)
                        self.send_header("Location", "/")
                        self.end_headers()
                        return

            elif path == "/add_task":
                task = data.get('task', [''])[0].strip()
                day = data.get('day', [''])[0].strip().upper()
                time_val = data.get('time', [''])[0].strip()

                if task and day and time_val:
                    timetable.append({
                        "task": task,
                        "day": day[:3],
                        "time": time_val
                    })
                    save_data()
                    print(f"Added task: {task} on {day} at {time_val}")

                self.send_response(303)
                self.send_header("Location", "/dashboard")
                self.end_headers()
                return

            elif path == "/add_usage":
                try:
                    hours = float(data.get('hours', ['0'])[0])
                    if 0 <= hours <= 24:
                        usage_log.append({
                            "date": datetime.date.today().strftime("%Y-%m-%d"),
                            "hours": hours
                        })
                        save_data()
                        print(f"Added usage: {hours} hours")
                except ValueError:
                    print("Invalid hours value")

                self.send_response(303)
                self.send_header("Location", "/dashboard")
                self.end_headers()
                return

            else:
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()

        except Exception as e:
            print("POST ERROR:", e)
            self.send_response(303)
            self.send_header("Location", "/dashboard")
            self.end_headers()

# -------- MAIN --------
if __name__ == "__main__":
    load_data()
    print(" Data loaded")

    threading.Thread(target=alarm_runner, daemon=True).start()
    print(" Alarm runner started")

    with ThreadingServer(("0.0.0.0", 0), Handler) as httpd:
        port = httpd.server_address[1]
        url = f"http://localhost:{port}"
        
        print(f" Running at {url}")
        webbrowser.open(url)
        print("Press Ctrl+C to stop")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n Server stopped")