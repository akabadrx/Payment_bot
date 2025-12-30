import os, time, subprocess, socket
from datetime import datetime, timezone
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== CONFIG ======
SHEET_NAME = os.getenv("LEADER_SHEET_NAME", "BotLeaderLock")  # Google Sheet
SHEET_TAB  = os.getenv("LEADER_SHEET_TAB", "Sheet1")          # usually "Sheet1"
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")

# Unique name for this computer
INSTANCE_NAME = os.getenv("Badr", socket.gethostname())

# Timing (seconds)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))  # leader writes every 60s
STALE_AFTER        = int(os.getenv("STALE_AFTER", "180"))        # if no update for 3 min, leader is dead
CHECK_EVERY        = int(os.getenv("CHECK_EVERY", "30"))         # how often to check leadership

BOT_COMMAND = os.getenv("BOT_COMMAND", "python newbot.py")
# =====================

def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def get_sheet():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    try:
        ws = sh.worksheet(SHEET_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TAB, rows=10, cols=5)
        ws.update("A1:C1", [["leader_id","heartbeat_utc","note"]])
    return ws

def read_lock(ws):
    vals = ws.get_values("A2:C2")
    if vals and len(vals[0]) > 0:
        row = vals[0]
    else:
        row = []
    leader_id = row[0] if len(row) > 0 and row[0] else ""
    heartbeat = row[1] if len(row) > 1 and row[1] else ""
    note = row[2] if len(row) > 2 and row[2] else ""
    return leader_id, heartbeat, note

def write_lock(ws, leader_id, heartbeat, note=""):
    ws.update("A2:C2", [[leader_id, heartbeat, note]])

def is_stale(heartbeat):
    if not heartbeat:
        return True
    dt = parse_iso(heartbeat)
    if not dt:
        return True
    age = (datetime.now(timezone.utc) - dt).total_seconds()
    return age > STALE_AFTER

def start_bot():
    print(f"[{INSTANCE_NAME}] 🚀 Starting bot process…")
    return subprocess.Popen(BOT_COMMAND, shell=True)

def stop_bot(proc):
    if proc and proc.poll() is None:
        print(f"[{INSTANCE_NAME}] ⛔ Stopping bot process…")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as e:
            print(f"[{INSTANCE_NAME}] Error stopping bot: {e}")

def main():
    print(f"Cluster runner up. INSTANCE_NAME={INSTANCE_NAME}")
    ws = None
    while not ws:
        try:
            ws = get_sheet()
            print(f"[{INSTANCE_NAME}] ✅ Connected to Google Sheet: {SHEET_NAME}")
        except Exception as e:
            print(f"[{INSTANCE_NAME}] ❌ Failed to connect to sheet: {e}")
            time.sleep(10)

    bot_proc = None
    i_am_leader = False
    last_hb = 0.0

    while True:
        try:
            leader_id, heartbeat, note = read_lock(ws)
            print(f"[{INSTANCE_NAME}] Current leader={leader_id}, heartbeat={heartbeat}, note={note}")

            leader_alive = not is_stale(heartbeat)

            if i_am_leader:
                if leader_id != INSTANCE_NAME:
                    print(f"[{INSTANCE_NAME}] ⚠️ Lost leadership to {leader_id}")
                    i_am_leader = False
                    stop_bot(bot_proc)
                    bot_proc = None
                else:
                    now = time.time()
                    if now - last_hb >= HEARTBEAT_INTERVAL:
                        hb = utc_now_iso()
                        print(f"[{INSTANCE_NAME}] ❤️ Sending heartbeat {hb}")
                        try:
                            write_lock(ws, INSTANCE_NAME, hb, "leader alive")
                            print(f"[{INSTANCE_NAME}] ✅ Heartbeat written.")
                        except Exception as e:
                            print(f"[{INSTANCE_NAME}] ❌ Failed to write heartbeat: {e}")
                        last_hb = now
                    if bot_proc and bot_proc.poll() is not None:
                        print(f"[{INSTANCE_NAME}] 💥 Bot crashed; restarting.")
                        bot_proc = start_bot()

            else:
                if not leader_id or not leader_alive:
                    print(f"[{INSTANCE_NAME}] 🟢 Attempting to become leader…")
                    hb = utc_now_iso()
                    try:
                        write_lock(ws, INSTANCE_NAME, hb, "taking leadership")
                    except Exception as e:
                        print(f"[{INSTANCE_NAME}] ❌ Failed to write leadership claim: {e}")
                        time.sleep(CHECK_EVERY)
                        continue

                    new_leader, _, _ = read_lock(ws)
                    if new_leader == INSTANCE_NAME:
                        print(f"[{INSTANCE_NAME}] 🏆 Became leader!")
                        i_am_leader = True
                        last_hb = time.time()
                        if bot_proc is None:
                            bot_proc = start_bot()
                    else:
                        print(f"[{INSTANCE_NAME}] Lost race, leader is {new_leader}")

                else:
                    if bot_proc is not None:
                        stop_bot(bot_proc)
                        bot_proc = None
                    print(f"[{INSTANCE_NAME}] Standby (leader {leader_id} alive).")

            time.sleep(CHECK_EVERY)

        except Exception as e:
            print(f"[{INSTANCE_NAME}] ❌ Error in loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
