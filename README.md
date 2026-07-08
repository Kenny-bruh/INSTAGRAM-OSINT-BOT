# INSTAGRAM-OSINT-BOT
Next‑Gen OSINT Bot for Instagram – multifunctional, private, and secure. Supports phone/vehicle/Aadhaar/Telegram/leak lookups. Includes credit system, gift codes, Telegram admin panel. Developed by @kewaire_ &amp; @kzr0x.


```markdown
# 🕵️‍♂️ Next‑Gen OSINT Bot for Instagram

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Channel](https://img.shields.io/badge/Telegram-@Api_wallah-blue.svg)](https://t.me/Api_wallah)
[![Instagram](https://img.shields.io/badge/Instagram-@kewaire_-E4405F.svg)](https://instagram.com/kewaire_)

> A powerful, fully automated OSINT (Open Source Intelligence) bot that operates through Instagram DMs and groups. Designed for ethical investigations, it provides instant access to phone number details, vehicle records, Aadhaar‑linked family info, Telegram user lookups, data leak checks, and much more – all with human‑like behavior to stay undetected.

---

## ✨ Features

- **📱 Phone Lookup** – Fetch name, address, carrier, circle, email, father's name, and more.
- **🚗 Vehicle Info** – Retrieve RC details: owner, registration, insurance, fuel type, RTO.
- **🆔 Aadhaar / Ration** – Get family members, state, district, scheme, and card details.
- **📡 Telegram OSINT** – Convert phone ↔ Telegram user ID; get user info from either.
- **🔍 Data Leak Check** – Search for breached accounts via email or username.
- **👤 Instagram ID** – Convert any Instagram username to its numeric user ID.
- **💳 Credit System** – Free credits for new users (10); admin‑controlled on/off, add/remove, gift codes.
- **👥 Group & DM** – Responds in both one‑on‑one DMs and group chats (must be a member).
- **⏱️ Human‑Like Delays** – Random response delays (30s‑6min) and polling intervals (20‑40s) to avoid automation flags.
- **🛡️ Admin Panel (Telegram)** – Full control via Telegram: manage credits, broadcast, stats, admins, gift codes, and system toggle.
- **🗑️ Auto‑Delete** – Telegram admin messages can auto‑delete after a configurable time.
- **📊 Persistent DB** – SQLite stores users, credits, gift codes, and activity logs.
- **🎨 Clean Output** – Emoji‑rich, organised, and external credits stripped – only your branding appears.

---

## 🛠️ Tech Stack

| Component      | Technology |
|----------------|------------|
| Language       | Python 3.10+ |
| Instagram API  | `instagrapi` |
| HTTP Client    | `requests` with automatic retries |
| Database       | SQLite3 |
| Admin Interface | Telegram Bot API |
| Concurrency    | `threading` + `Queue` |

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/instagram-osint-bot.git
cd instagram-osint-bot

# Install dependencies
pip install -r requirements.txt
```

requirements.txt

```
instagrapi
requests
urllib3
```

---

⚙️ Configuration

Edit the script and replace the following values:

🔑 Instagram Cookies

Extract your session cookies using a browser extension (Cookie‑Editor) and update:

```python
cookies = {
    "ds_user_id": "YOUR_DS_USER_ID",
    "csrftoken": "YOUR_CSRFTOKEN",
    "sessionid": "YOUR_SESSIONID",
    "mid": "YOUR_MID",
    "ig_did": "YOUR_IG_DID",
    "rur": "YOUR_RUR",
    "dpr": "2",
    "wd": "360x624",
    "datr": "YOUR_DATR"
}
```

🤖 Telegram Admin Panel

```python
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
ADMINS = ["TELEGRAM_USER_ID_1", "TELEGRAM_USER_ID_2"]   # Numeric IDs
```

⏱️ Human‑Like Delays (Optional)

```python
MIN_RESPONSE_DELAY = 30      # seconds
MAX_RESPONSE_DELAY = 360     # up to 6 minutes
MIN_POLL_INTERVAL = 20
MAX_POLL_INTERVAL = 40
```

---

▶️ Running the Bot

```bash
python bot.py
```

After successful login, the bot will start polling and respond to commands with natural delays.

---

🤖 User Commands (Instagram DM / Group)

Command Description
/start, /help Show available commands and credit info.
/num <phone> Fetch detailed information about a phone number.
/vehicle <RC> Retrieve vehicle registration details (RC number).
/aadhar <12-digit> Get Aadhaar‑linked ration card family details.
/username <ig_user> Get the numeric Instagram ID of a username.
/teleid <phone> Look up Telegram user info from a phone number.
/teleuser <userid> Get phone number from a Telegram user ID.
/leak <email/username> Check if the email/username appears in known data breaches.
/credit Check your remaining credits.
/buy Get the admin contact link to purchase credits.
/redeem <gift_code> Redeem a gift code for free credits.

💡 Each search command (/num, /vehicle, /aadhar, /username, /teleid, /teleuser, /leak) costs 1 credit.
New users start with 10 free credits.

---

🔧 Admin Commands (Telegram)

Only users whose numeric IDs are listed in ADMINS can execute these commands via Telegram:

Command Effect
/crediton Enable the credit system (each search costs 1 credit).
/creditoff Disable the credit system (all searches free).
/addcredit <user_id> <amount> Add credits to a user.
/removecredit <user_id> <amount> Remove credits from a user.
/setusermap @username <instagram_id> Map an Instagram username to its numeric ID (for future lookups).
/stats Display all users with their credits and last activity time.
/giftcode <amount> <code> Generate a gift code (e.g., /giftcode 50 HELLO).
/broadcast <message> Send a broadcast DM to all registered users.
/addadmin <telegram_id> Add a new Telegram admin.
/removeadmin <telegram_id> Remove a Telegram admin.
/listadmins List all current Telegram admins.
/help Show the admin help menu.

---

🌐 Third‑Party APIs

Service Endpoint
Phone Number https://num-to-info-eight.vercel.app/api/search?mobile={number}
Vehicle Info https://vehicle-eight-vert.vercel.app/api?rc={rc}
Aadhaar/Ration https://aadhar-to-ration-api-abhaysingh.vercel.app//api/family?id={aadhar}
Telegram ID from Number https://tgchatid.vercel.app/api/lookup?number={number}
Telegram Number from ID https://abhigyan-codes-tg-to-number-api.onrender.com/@abhigyan_codes/userid={userid}
Data Leak https://leakosintprobynoneusr.onrender.com/raavan/v34/query={query}/key=NONE-UsrX-0DXA77CQDA7wFmpmWCAIOSHfdzrIfw5z

Note: All external developer credits are automatically stripped from responses.

---

🔐 Security & Ethical Use

· Privacy – All user data is stored locally in credits.db. No external logging or data sharing.
· Ethical OSINT – This tool is intended for educational purposes and authorised investigations only.
    Do not use for stalking, harassment, or any illegal activity.
· Compliance – The bot mimics human behaviour to reduce the risk of Instagram rate‑limiting, but heavy usage may still lead to temporary blocks. Use responsibly.

---

🤝 Contributing

Contributions, bug reports, and feature requests are welcome. Please open an issue or submit a pull request.

---

📜 License

This project is licensed under the MIT License – see the LICENSE file for details.

---

🙏 Credits

· Developer – @kewaire_ (Instagram) · @kzr0x (Telegram)
· Telegram Channel – @Api_wallah – For API updates and support.
· Libraries – instagrapi · requests
· Open‑Source Community – For the amazing tools and APIs that make this possible.

---

Built with ❤️ for the OSINT community.
Stay curious, stay ethical. 🔍

```
