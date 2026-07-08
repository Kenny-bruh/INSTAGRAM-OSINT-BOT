#!/usr/bin/env python3
import requests
import time
import threading
import random
from queue import Queue
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import traceback
import sqlite3
import re
import string
from collections import deque
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from instagrapi import Client

# ================= TELEGRAM CONFIG =================
TELEGRAM_TOKEN = "8771725190:AAGg7ZmwnzyIBfD6SNEh6U3McKz7IGblEH4"
ADMINS = ["5146838953", "8520202700"]

# ================= INSTAGRAM COOKIES (your fresh ones) =================
cookies = {
    "ds_user_id": "23820856996",
    "csrftoken": "mNEui0hpbe3X377y0VjMLw",
    "sessionid": "23820856996%3ApukMAvqrlOkbqa%3A10%3AAYgCeJtvx3t1aNT0_1qPtCPchJKgv2aAfxoF6qGXeQ",
    "mid": "afShqQABAAFsYNnIINUjQVYPYJYJ",
    "ig_did": "D9740B7D-8F1A-4F37-8654-C5FBD188806A",
    "rur": "RCD\\05423820856996\\0541809175955:01febad004bfc2250fdd14b9e66259699dcc43781b27182096bc43695efa7e227b8634d",
    "dpr": "2",
    "wd": "360x624",
    "datr": "qKH0aSxaCigQ5O6TFdHECbmz"
}

cl = Client()
cl.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
cl.set_settings({"cookies": cookies})

def login_instagram():
    try:
        cl.login_by_sessionid(cookies["sessionid"])
        print("✅ Logged in using cookies")
        return True
    except Exception as e:
        print(f"Login failed: {e}")
        return False

if not login_instagram():
    exit(1)

print(f"Logged in as: {cl.username} (ID: {cl.user_id})")

# ================= HUMAN‑LIKE DELAYS =================
MIN_RESPONSE_DELAY = 30      # 30 seconds
MAX_RESPONSE_DELAY = 360     # 6 minutes
MIN_POLL_INTERVAL = 20
MAX_POLL_INTERVAL = 40

# ================= DATABASE =================
DB_FILE = "credits.db"
DEFAULT_CREDITS = 10
TZ = ZoneInfo("Asia/Kolkata")
API_TIMEOUT = 15
WORKER_COUNT = 1

message_queue = Queue()
telegram_queue = Queue()
last_processed_msg_ids = deque(maxlen=200)

session = requests.Session()
_retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
_adapter = HTTPAdapter(max_retries=_retry)
session.mount("https://", _adapter)
session.mount("http://", _adapter)
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_seen TEXT,
                    last_command TEXT,
                    credits INTEGER DEFAULT 10
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS telegram_admins (
                    user_id TEXT PRIMARY KEY
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS username_map (
                    username TEXT PRIMARY KEY,
                    instagram_id TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gift_codes (
                    code TEXT PRIMARY KEY,
                    amount INTEGER,
                    used_by TEXT,
                    used_at TEXT,
                    created_at TEXT
                )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('credit_system', 'on')")
    for admin_id in ADMINS:
        c.execute("INSERT OR IGNORE INTO telegram_admins (user_id) VALUES (?)", (admin_id,))
    c.execute("DELETE FROM telegram_admins WHERE rowid NOT IN (SELECT MIN(rowid) FROM telegram_admins GROUP BY user_id)")
    conn.commit()
    conn.close()
init_db()

# ---------- Helper functions ----------
def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def is_credit_system_on():
    return get_setting('credit_system', 'on') == 'on'

def set_credit_system(state):
    set_setting('credit_system', state)

def is_telegram_admin(telegram_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM telegram_admins WHERE user_id = ?", (str(telegram_id),))
    row = c.fetchone()
    conn.close()
    return row is not None

def add_telegram_admin(telegram_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO telegram_admins (user_id) VALUES (?)", (str(telegram_id),))
    conn.commit()
    conn.close()

def remove_telegram_admin(telegram_id):
    if str(telegram_id) in ADMINS:
        return False
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM telegram_admins WHERE user_id = ?", (str(telegram_id),))
    conn.commit()
    conn.close()
    return True

def get_all_telegram_admins():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM telegram_admins")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def set_username_map(username, instagram_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO username_map (username, instagram_id) VALUES (?, ?)",
              (username.lstrip('@'), str(instagram_id)))
    conn.commit()
    conn.close()

def get_instagram_id_from_username(username):
    username = username.lstrip('@')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT instagram_id FROM username_map WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def ensure_user(user_id, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    now = datetime.now(TZ).isoformat()
    if row is None:
        c.execute("INSERT INTO users (user_id, username, first_seen, last_command, credits) VALUES (?, ?, ?, ?, ?)",
                  (str(user_id), username, now, now, DEFAULT_CREDITS))
        conn.commit()
        credits = DEFAULT_CREDITS
    else:
        credits = row[0]
        c.execute("UPDATE users SET username = ?, last_command = ? WHERE user_id = ?", (username, now, str(user_id)))
        conn.commit()
    conn.close()
    return credits

def get_user_credits(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else DEFAULT_CREDITS

def consume_credit(user_id):
    if not is_credit_system_on():
        return True
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    if not row or row[0] <= 0:
        conn.close()
        return False
    new_credits = row[0] - 1
    c.execute("UPDATE users SET credits = ? WHERE user_id = ?", (new_credits, str(user_id)))
    conn.commit()
    conn.close()
    return True

def add_credits(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    if row:
        new_credits = row[0] + amount
        c.execute("UPDATE users SET credits = ? WHERE user_id = ?", (new_credits, str(user_id)))
    else:
        c.execute("INSERT INTO users (user_id, username, first_seen, last_command, credits) VALUES (?, ?, ?, ?, ?)",
                  (str(user_id), "", datetime.now(TZ).isoformat(), datetime.now(TZ).isoformat(), DEFAULT_CREDITS + amount))
    conn.commit()
    conn.close()

def remove_credits(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    if row:
        new_credits = max(0, row[0] - amount)
        c.execute("UPDATE users SET credits = ? WHERE user_id = ?", (new_credits, str(user_id)))
    conn.commit()
    conn.close()

def create_gift_code(amount, custom_code=None):
    code = custom_code.upper() if custom_code else ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO gift_codes (code, amount, created_at) VALUES (?, ?, ?)",
              (code, amount, datetime.now(TZ).isoformat()))
    conn.commit()
    conn.close()
    return code

def redeem_gift_code(user_id, code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT amount, used_by FROM gift_codes WHERE code = ?", (code.upper(),))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Invalid code"
    amount, used_by = row
    if used_by:
        conn.close()
        return False, "Code already used"
    c.execute("UPDATE gift_codes SET used_by = ?, used_at = ? WHERE code = ?",
              (str(user_id), datetime.now(TZ).isoformat(), code.upper()))
    conn.commit()
    add_credits(user_id, amount)
    conn.close()
    return True, amount

def get_all_users_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, credits, last_command FROM users ORDER BY last_command DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def resolve_instagram_id(username_or_id):
    username_or_id = str(username_or_id).lstrip('@')
    if username_or_id.isdigit():
        return username_or_id
    mapped = get_instagram_id_from_username(username_or_id)
    if mapped:
        return mapped
    try:
        return str(cl.user_id_from_username(username_or_id))
    except:
        return None

def get_instagram_user_id_by_username(username):
    username = username.lstrip('@')
    mapped = get_instagram_id_from_username(username)
    if mapped:
        return mapped
    try:
        return str(cl.user_id_from_username(username))
    except:
        pass
    return None

# ================= API LOOKUPS (only working APIs) =================
def get_number_info(number):
    """Only the new working API from your friend"""
    url = f"https://num-to-info-eight.vercel.app/api/search?mobile={number}"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 200 and resp.text.strip():
            try:
                data = resp.json()
                # If the response has 'data' array, format nicely
                if isinstance(data, dict) and 'data' in data:
                    results = data['data']
                    if results:
                        # Take first result (you can modify to show all)
                        info = results[0]
                        formatted = f"📱 **Number:** {info.get('mobile', number)}\n"
                        formatted += f"👤 **Name:** {info.get('name', 'N/A')}\n"
                        formatted += f"👨 **Father's Name:** {info.get('fname', 'N/A')}\n"
                        formatted += f"🏠 **Address:** {info.get('address', 'N/A')}\n"
                        formatted += f"📧 **Email:** {info.get('email', 'N/A')}\n"
                        formatted += f"🌐 **Circle:** {info.get('circle', 'N/A')}\n"
                        return {"status": "success", "result": formatted}
                    else:
                        return {"error": "No information found for this number"}
                else:
                    return data
            except:
                return {"raw": resp.text}
    except Exception as e:
        print(f"Number API error: {e}")
        return {"error": "Number API temporarily unavailable. Try again later."}
    return {"error": "Number API failed."}

def get_vehicle_info(rc):
    url = f"https://vehicle-eight-vert.vercel.app/api?rc={rc}"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            try:
                return resp.json()
            except:
                return {"raw": resp.text}
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_aadhar_info_text(aadhar):
    url = f"https://aadhar-to-ration-api-abhaysingh.vercel.app//api/family?id={aadhar}"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code != 200:
            return f"❌ HTTP {resp.status_code}"
        html = resp.text
        def extract(label):
            pattern = rf'{re.escape(label)}\s*:\s*([^<]+)'
            match = re.search(pattern, html)
            return match.group(1).strip() if match else None
        lines = []
        lines.append(f"🏷️ Aadhaar / Ration ID: {aadhar}\n")
        state = extract("State")
        district = extract("District")
        card_no = extract("Card No")
        scheme = extract("Scheme")
        if state: lines.append(f"🏛️ State        : {state}")
        if district: lines.append(f"📍 District     : {district}")
        if card_no: lines.append(f"🆔 Card No      : {card_no}")
        if scheme: lines.append(f"📝 Scheme       : {scheme}")
        if any([state, district, card_no, scheme]): lines.append("")
        info_labels = ["Central Repository", "Duplicate Aadhaar", "FPS Category", "IMPDS Transaction"]
        info_found = False
        for label in info_labels:
            val = extract(label)
            if val:
                if not info_found:
                    lines.append("ℹ️ Additional Info")
                    info_found = True
                emoji = "✅" if "Yes" in val or "Allowed" in val else "❌"
                lines.append(f"  {emoji} {label}: {val}")
        if info_found: lines.append("")
        members = re.findall(r'<div class="line">├\s*👤\s*([^<]+)</div>', html)
        if not members:
            members = re.findall(r'<div class="line">├\s*([^<]+)</div>', html)
            members = [m.strip() for m in members if m.strip() and not any(x in m for x in ['State','District','Card No','Scheme','Central','Duplicate','FPS','IMPDS'])]
        if members:
            lines.append(f"👨‍👩‍👧‍👦 Family Members ({len(members)})")
            for m in members:
                lines.append(f"  👤 {m}")
        lines.append("")
        lines.append("🔧 Dev: @ui.piyush___ • Next Gen")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_telegram_id_from_number(number):
    url = f"https://tgchatid.vercel.app/api/lookup?number={number}"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_telegram_number_from_userid(userid):
    url = f"https://abhigyan-codes-tg-to-number-api.onrender.com/@abhigyan_codes/userid={userid}"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_leak_info(query):
    url = f"https://leakosintprobynoneusr.onrender.com/raavan/v34/query={query}/key=NONE-UsrX-0DXA77CQDA7wFmpmWCAIOSHfdzrIfw5z"
    try:
        resp = session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            try:
                return resp.json()
            except:
                return {"raw": resp.text}
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def sanitize_api_response(data):
    if isinstance(data, dict):
        for key in list(data.keys()):
            if key.lower() in ['credit', 'developer', 'api_developer', 'channel', 'powered_by', 'developed_by']:
                del data[key]
        for key, value in data.items():
            if isinstance(value, dict):
                data[key] = sanitize_api_response(value)
            elif isinstance(value, list):
                data[key] = [sanitize_api_response(item) if isinstance(item, dict) else item for item in value]
    return data

# ================= MESSAGING (supports both DM and group) =================
def is_group_thread(thread_id):
    try:
        thread = cl.direct_thread(thread_id)
        return thread.is_group
    except:
        return False

def send_instagram_message(user_id, thread_id, text):
    if user_id == cl.user_id:
        return
    time.sleep(random.uniform(1, 3))
    if thread_id and is_group_thread(thread_id):
        cl.direct_send(text, [thread_id])
    else:
        cl.direct_send(text, [user_id])

def send_instagram_json(user_id, thread_id, data, query=None):
    if user_id == cl.user_id:
        return
    cleaned = sanitize_api_response(data)
    # Special formatting for number info (which is already a formatted string)
    if isinstance(cleaned, dict) and cleaned.get("status") == "success" and "result" in cleaned:
        # Result is already formatted text, send as is
        send_instagram_message(user_id, thread_id, cleaned["result"])
        return
    if isinstance(cleaned, (dict, list)):
        formatted = json.dumps(cleaned, ensure_ascii=False, indent=2)
    else:
        formatted = str(cleaned)
    if query:
        header = f"🔍 Query: {query}\n━━━━━━━━━━━━━━━━━━━━\n"
        formatted = header + formatted
    formatted += "\n\n🔧 Dev: @ui.piyush___ • Next Gen"
    send_instagram_message(user_id, thread_id, formatted)

# ================= COMMAND HANDLER =================
ALLOWED_COMMANDS = {"/start","/help","/num","/vehicle","/aadhar","/username","/teleid","/teleuser","/leak","/credit","/buy","/redeem"}

def send_help_message(user_id, thread_id):
    credits_on = is_credit_system_on()
    credit_line = f"🎁 New users get {DEFAULT_CREDITS} free credits!\n• Each search costs 1 credit\n" if credits_on else "💰 Credit system is currently **OFF** – all searches are free!\n"
    credit_cmd = "▪ /credit – check your credits\n" if credits_on else ""
    intro = (
        "┏━━✨ Next Gen Osint Bot (Instagram) ✨━━┓\n\n"
        "👋 Hey! I’m your OSINT copilot—fast, precise & private.\n\n"
        f"{credit_line}"
        "——— 🔎 Available Commands ———\n"
        "▪ /num <phone> – mobile number details\n"
        "▪ /vehicle <RC> – vehicle info\n"
        "▪ /aadhar <12-digit> – Aadhaar/ration lookup\n"
        "▪ /username <ig_user> – get numeric user ID\n"
        "▪ /teleid <phone> – Telegram user info from number\n"
        "▪ /teleuser <userid> – Telegram number from user ID\n"
        "▪ /leak <query> – leakosint search\n"
        f"{credit_cmd}"
        "▪ /buy – purchase credits\n"
        "▪ /redeem <code> – redeem gift code\n\n"
        "🔧 Dev: @ui.piyush___ • Next Gen Team\n"
        "🌐 Stay Safe • Respect Privacy"
    )
    send_instagram_message(user_id, thread_id, intro)

def handle_instagram_command(user_id, username, thread_id, text_raw):
    if user_id == cl.user_id:
        return
    text = text_raw.strip()
    if not text:
        return
    # Aadhar 12-digit
    if text.isdigit() and len(text) == 12:
        ensure_user(user_id, username)
        if is_credit_system_on() and not consume_credit(user_id):
            send_instagram_message(user_id, thread_id, "❌ No credits left! Use /buy to purchase or contact admin @ui.piyush___")
            return
        result = get_aadhar_info_text(text)
        send_instagram_message(user_id, thread_id, result)
        return
    if not text.startswith('/'):
        return
    token = text.split()[0] if text else ""
    cmd = token.split("@")[0].lower()
    if cmd not in ALLOWED_COMMANDS:
        return
    ensure_user(user_id, username)

    # HUMAN DELAY
    delay = random.randint(MIN_RESPONSE_DELAY, MAX_RESPONSE_DELAY)
    print(f"⏳ Delaying response to {username} (group: {bool(thread_id)}) for {delay} seconds...")
    time.sleep(delay)

    # Update last_command
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET last_command = ? WHERE user_id = ?", (datetime.now(TZ).isoformat(), str(user_id)))
    conn.commit()
    conn.close()

    if cmd in ("/start", "/help"):
        send_help_message(user_id, thread_id)
        return
    if cmd == "/credit":
        if not is_credit_system_on():
            send_instagram_message(user_id, thread_id, "ℹ️ Credit system is currently OFF. All searches are free!")
        else:
            bal = get_user_credits(user_id)
            send_instagram_message(user_id, thread_id, f"📊 Your credits: {bal}\n💸 Each search costs 1 credit.\n👉 To buy more, use /buy")
        return

    def check_credits():
        if is_credit_system_on() and not consume_credit(user_id):
            send_instagram_message(user_id, thread_id, "❌ No credits left! Use /buy to purchase or contact admin @ui.piyush___")
            return False
        return True

    if cmd == "/username":
        parts = text.split()
        if len(parts) == 2:
            if not check_credits(): return
            target = parts[1]
            ig_id = get_instagram_user_id_by_username(target)
            if ig_id:
                send_instagram_message(user_id, thread_id, f"🔍 Instagram ID for @{target}\n━━━━━━━━━━━━━━━━━━━━\n🆔 {ig_id}\n\n🔧 Dev: @ui.piyush___")
            else:
                send_instagram_message(user_id, thread_id, f"❌ Could not find ID for @{target}")
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /username <instagram_username>")
        return

    if cmd == "/num":
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            if not check_credits(): return
            data = get_number_info(parts[1])
            # get_number_info returns a dict; send_instagram_json handles formatting
            send_instagram_json(user_id, thread_id, data, query=parts[1])
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /num 9997451964")
        return

    if cmd == "/vehicle":
        parts = text.split()
        if len(parts) == 2:
            if not check_credits(): return
            rc = parts[1].upper()
            data = get_vehicle_info(rc)
            if isinstance(data, dict) and "details" in data:
                lines = [f"🚗 Vehicle: {rc}", ""]
                details = data["details"]
                emoji_map = {
                    "Owner Name": "👤", "Father's Name": "👨", "Registration Date": "📅",
                    "Vehicle Class": "🚙", "Maker Model": "🏭", "Model Name": "📱",
                    "Fuel Type": "⛽", "Fuel Norms": "🌿", "Fitness Upto": "✅",
                    "Insurance Company": "🛡️", "Insurance Expiry": "⏰", "Insurance Upto": "⏰",
                    "Financier Name": "🏦", "Address": "📍", "City Name": "🏙️",
                    "Phone": "📞", "Registered RTO": "🏢", "Owner Serial No": "🔢"
                }
                for key, val in details.items():
                    emoji = emoji_map.get(key, "•")
                    lines.append(f"{emoji} {key}: {val}")
                result = "\n".join(lines) + "\n\n🔧 Dev: @ui.piyush___ • Next Gen"
                send_instagram_message(user_id, thread_id, result)
            else:
                send_instagram_json(user_id, thread_id, data, query=rc)
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /vehicle BR06PE8167")
        return

    if cmd == "/aadhar":
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 12:
            if not check_credits(): return
            result = get_aadhar_info_text(parts[1])
            send_instagram_message(user_id, thread_id, result)
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /aadhar 123456789012")
        return

    if cmd == "/teleid":
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            if not check_credits(): return
            send_instagram_json(user_id, thread_id, get_telegram_id_from_number(parts[1]), query=parts[1])
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /teleid 6884112825")
        return

    if cmd == "/teleuser":
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            if not check_credits(): return
            send_instagram_json(user_id, thread_id, get_telegram_number_from_userid(parts[1]), query=parts[1])
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /teleuser 6292384591")
        return

    if cmd == "/leak":
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            if not check_credits(): return
            send_instagram_json(user_id, thread_id, get_leak_info(parts[1]), query=parts[1])
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /leak user@example.com")
        return

    if cmd == "/buy":
        buy_msg = "💳 **Credit Purchase**\n\n1 credit = ₹5\nMinimum 10 credits (₹50)\n\n📩 To buy credits, contact the admin directly:\n[Click here to message admin](tg://resolve?domain=ui_piyush___&text=HELLO%20SIR%20I%20WANT%20TO%20BUY%20CREDITS)"
        send_instagram_message(user_id, thread_id, buy_msg)
        return

    if cmd == "/redeem":
        parts = text.split()
        if len(parts) == 2:
            success, result = redeem_gift_code(user_id, parts[1])
            if success:
                send_instagram_message(user_id, thread_id, f"🎉 Gift code redeemed! You received {result} credits.\n📊 New balance: {get_user_credits(user_id)} credits.")
            else:
                send_instagram_message(user_id, thread_id, f"❌ {result}")
        else:
            send_instagram_message(user_id, thread_id, "❌ Usage: /redeem <gift_code>")
        return

# ================= POLLING =================
def instagram_poller():
    last_processed = {}
    while True:
        try:
            threads = cl.direct_threads(amount=20)
            for thread in threads:
                if len(thread.users) == 1 and thread.users[0].pk == cl.user_id:
                    continue
                tid = thread.id
                for msg in thread.messages:
                    if msg.user_id == cl.user_id:
                        continue
                    if msg.id in last_processed_msg_ids:
                        continue
                    if tid in last_processed and last_processed[tid] >= msg.timestamp:
                        continue
                    if msg.text:
                        try:
                            username = cl.user_info(msg.user_id).username
                        except:
                            username = "unknown"
                        message_queue.put({
                            "user_id": msg.user_id,
                            "username": username,
                            "thread_id": tid,
                            "text": msg.text
                        })
                        last_processed[tid] = msg.timestamp
                        last_processed_msg_ids.append(msg.id)
            sleep_time = random.randint(MIN_POLL_INTERVAL, MAX_POLL_INTERVAL)
            time.sleep(sleep_time)
        except Exception as e:
            print(f"Instagram poll error: {e}")
            time.sleep(60)

def instagram_worker():
    while True:
        dm = message_queue.get()
        if dm is None:
            break
        try:
            handle_instagram_command(dm["user_id"], dm["username"], dm["thread_id"], dm["text"])
        except Exception as e:
            traceback.print_exc()
        finally:
            message_queue.task_done()

# ================= TELEGRAM ADMIN PANEL =================
def send_telegram_message(chat_id, text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        session.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram send error: {e}")

def handle_telegram_command(chat_id, text):
    if not is_telegram_admin(chat_id):
        send_telegram_message(chat_id, "❌ You are not authorized.")
        return
    parts = text.strip().split()
    cmd = parts[0].lower() if parts else ""

    if cmd == "/crediton":
        set_credit_system("on")
        send_telegram_message(chat_id, "✅ Credit system ON (1 credit per search).")
        return
    if cmd == "/creditoff":
        set_credit_system("off")
        send_telegram_message(chat_id, "✅ Credit system OFF (free).")
        return
    if cmd in ("/addcredit", "/givecredit") and len(parts) == 3:
        target = parts[1]
        try:
            amount = int(parts[2])
        except:
            send_telegram_message(chat_id, "❌ Amount must be a number.")
            return
        if target.isdigit():
            add_credits(target, amount)
            send_telegram_message(chat_id, f"✅ Added {amount} credits to {target}.")
        else:
            send_telegram_message(chat_id, "❌ Use numeric user ID.")
        return
    if cmd == "/removecredit" and len(parts) == 3:
        target = parts[1]
        try:
            amount = int(parts[2])
        except:
            send_telegram_message(chat_id, "❌ Amount must be a number.")
            return
        if target.isdigit():
            remove_credits(target, amount)
            send_telegram_message(chat_id, f"✅ Removed {amount} credits from {target}.")
        else:
            send_telegram_message(chat_id, "❌ Use numeric user ID.")
        return
    if cmd == "/setusermap" and len(parts) == 3:
        username = parts[1].lstrip('@')
        ig_id = parts[2]
        if ig_id.isdigit():
            set_username_map(username, ig_id)
            send_telegram_message(chat_id, f"✅ Mapped @{username} to Instagram ID {ig_id}")
        else:
            send_telegram_message(chat_id, "❌ Instagram ID must be numeric.")
        return
    if cmd == "/stats":
        users = get_all_users_stats()
        if not users:
            send_telegram_message(chat_id, "📊 No users yet.")
            return
        msg = "📊 **User Statistics**\n\n"
        for uid, uname, cred, last in users:
            uname_display = f"@{uname}" if uname else f"ID:{uid}"
            msg += f"👤 {uname_display} | 💰 {cred} credits | 🕒 {last[:16]}\n"
            if len(msg) > 3800:
                send_telegram_message(chat_id, msg, parse_mode="Markdown")
                msg = ""
        if msg:
            send_telegram_message(chat_id, msg, parse_mode="Markdown")
        return
    if cmd == "/giftcode" and len(parts) == 3:
        try:
            amount = int(parts[1])
            code = parts[2].upper()
            create_gift_code(amount, code)
            send_telegram_message(chat_id, f"✅ Gift code created: `{code}` for {amount} credits.", parse_mode="Markdown")
        except Exception as e:
            send_telegram_message(chat_id, f"❌ Error: {e}")
        return
    if cmd == "/broadcast" and len(parts) >= 2:
        msg_text = " ".join(parts[1:])
        users = get_all_users_stats()
        sent = 0
        for uid, _, _, _ in users:
            try:
                send_instagram_message(uid, None, f"📢 **Broadcast from admin**\n\n{msg_text}")
                sent += 1
                time.sleep(0.5)
            except:
                pass
        send_telegram_message(chat_id, f"✅ Broadcast sent to {sent} users.")
        return
    if cmd == "/addadmin" and len(parts) == 2:
        new_admin = parts[1]
        if new_admin.isdigit():
            add_telegram_admin(new_admin)
            send_telegram_message(chat_id, f"✅ Added {new_admin} as admin.")
        else:
            send_telegram_message(chat_id, "❌ Usage: /addadmin <numeric_id>")
        return
    if cmd == "/removeadmin" and len(parts) == 2:
        rem_admin = parts[1]
        if rem_admin.isdigit():
            if remove_telegram_admin(rem_admin):
                send_telegram_message(chat_id, f"✅ Removed admin {rem_admin}.")
            else:
                send_telegram_message(chat_id, "❌ Cannot remove default admin.")
        else:
            send_telegram_message(chat_id, "❌ Invalid ID.")
        return
    if cmd == "/listadmins":
        admins = get_all_telegram_admins()
        send_telegram_message(chat_id, f"👥 Admins: {', '.join(admins)}")
        return
    if cmd == "/help":
        help_text = (
            "🔧 **Admin Commands**\n"
            "/crediton – enable credits\n"
            "/creditoff – disable credits\n"
            "/addcredit <user_id> <amount>\n"
            "/removecredit <user_id> <amount>\n"
            "/setusermap @username <instagram_id>\n"
            "/stats – detailed user stats\n"
            "/giftcode <amount> <code> – create gift code\n"
            "/broadcast <msg>\n"
            "/addadmin <id>\n"
            "/removeadmin <id>\n"
            "/listadmins"
        )
        send_telegram_message(chat_id, help_text)
        return
    send_telegram_message(chat_id, "Unknown command. Use /help")

def telegram_poller():
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 20, "offset": last_update_id + 1}
            resp = session.get(url, params=params, timeout=25)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message")
                    if msg and msg.get("text"):
                        telegram_queue.put((msg["chat"]["id"], msg["text"]))
            time.sleep(1)
        except Exception as e:
            print(f"Telegram poll error: {e}")
            time.sleep(5)

def telegram_worker():
    while True:
        chat_id, text = telegram_queue.get()
        if chat_id is None:
            break
        try:
            handle_telegram_command(chat_id, text)
        except Exception as e:
            traceback.print_exc()
        finally:
            telegram_queue.task_done()

# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=instagram_poller, daemon=True).start()
    threading.Thread(target=instagram_worker, daemon=True).start()
    threading.Thread(target=telegram_poller, daemon=True).start()
    threading.Thread(target=telegram_worker, daemon=True).start()
    print("✅ Instagram OSINT Bot started with new number API only")
    print(f"   - Response delay: {MIN_RESPONSE_DELAY}–{MAX_RESPONSE_DELAY} seconds (random)")
    print(f"   - Polling interval: {MIN_POLL_INTERVAL}–{MAX_POLL_INTERVAL} seconds")
    print("   - Supports both DMs and group chats")
    print("   - Telegram admin panel active")
    while True:
        time.sleep(60)