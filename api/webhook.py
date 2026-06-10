import requests, json, os, threading
from libsql_client import create_client_sync

# ── CONFIG ───────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ADMIN_TG_ID = int(os.environ.get("ADMIN_TG_ID", "8321630022"))
ADMIN_USER  = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS  = os.environ.get("ADMIN_PASS", "admin123")
API_URL     = os.environ.get("API_URL", "https://recognition-pretty-hosting-courtesy.trycloudflare.com")
TURSO_URL   = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")
# ─────────────────────────────────────────────────────────────

def get_db():
    return create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

def db_init():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    db.close()

def db_get(key):
    try:
        db = get_db()
        rs = db.execute("SELECT v FROM kv WHERE k = ?", [key])
        db.close()
        if rs.rows:
            return json.loads(rs.rows[0][0])
    except:
        pass
    return None

def db_set(key, value):
    try:
        db = get_db()
        db.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", [key, json.dumps(value)])
        db.close()
    except Exception as e:
        print(f"db_set error: {e}")

def db_del(key):
    try:
        db = get_db()
        db.execute("DELETE FROM kv WHERE k = ?", [key])
        db.close()
    except:
        pass

def get_admin_token():
    t = db_get("ADMIN_TOKEN")
    if t:
        return t
    res = api_post("", "/api/login", {"username": ADMIN_USER, "password": ADMIN_PASS})
    if res.get("token"):
        db_set("ADMIN_TOKEN", res["token"])
        return res["token"]
    return None

# ── TELEGRAM HELPERS ─────────────────────────────────────────

def tg(method, **kwargs):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=kwargs, timeout=10)
        return r.json()
    except:
        return {}

def edit_msg(chat_id, msg_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    tg("editMessageText", **payload)

def send_msg(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    r = tg("sendMessage", **payload)
    return r.get("result", {}).get("message_id")

def delete_msg(chat_id, msg_id):
    tg("deleteMessage", chat_id=chat_id, message_id=msg_id)

# ── API HELPERS ──────────────────────────────────────────────

def api_get(token, path):
    try:
        r = requests.get(f"{API_URL}{path}", headers={"X-Token": token}, timeout=10)
        return r.json()
    except:
        return {}

def api_post(token, path, data):
    try:
        headers = {"X-Token": token} if token else {}
        r = requests.post(f"{API_URL}{path}", json=data, headers=headers, timeout=10)
        return r.json()
    except:
        return {}

def api_delete(token, path):
    try:
        r = requests.delete(f"{API_URL}{path}", headers={"X-Token": token}, timeout=10)
        return r.json()
    except:
        return {}

# ── KEYBOARDS ────────────────────────────────────────────────

def main_menu_kb():
    return {"inline_keyboard": [
        [{"text": "🔐 Login to NxtZen", "callback_data": "login"}],
        [{"text": "📝 Request ID from Admin", "callback_data": "request_id"}]
    ]}

def admin_menu_kb():
    return {"inline_keyboard": [
        [{"text": "📊 Panel Status", "callback_data": "panel_status"},
         {"text": "📋 My Numbers", "callback_data": "my_numbers"}],
        [{"text": "📨 Live SMS", "callback_data": "live_sms"},
         {"text": "🤖 Bot Config", "callback_data": "bot_config"}],
        [{"text": "⚙️ Bot ON", "callback_data": "bot_on"},
         {"text": "🔴 Bot OFF", "callback_data": "bot_off"}],
        [{"text": "♻️ Reset SMS Channel", "callback_data": "reset_sms"},
         {"text": "♻️ Reset Num Channel", "callback_data": "reset_num"}],
        [{"text": "📤 Forward Numbers", "callback_data": "forward_nums"},
         {"text": "🗂 Download Numbers", "callback_data": "dl_numbers"}],
        [{"text": "👥 My Panels", "callback_data": "my_panels"},
         {"text": "🔑 My Token", "callback_data": "my_token"}],
        [{"text": "📚 API Docs", "callback_data": "api_docs"},
         {"text": "🔄 Refresh Status", "callback_data": "refresh"}],
        [{"text": "🚪 Logout", "callback_data": "logout"}],
    ]}

def back_kb():
    return {"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "back_menu"}]]}

def bot_config_kb(configured):
    kb = [[{"text": "➕ Add / Update Bot", "callback_data": "add_bot"}]]
    if configured:
        kb.append([{"text": "🗑 Delete Bot", "callback_data": "delete_bot"}])
    kb.append([{"text": "⬅️ Back", "callback_data": "back_menu"}])
    return {"inline_keyboard": kb}

# ── HANDLERS ─────────────────────────────────────────────────

def handle_start(chat_id, msg_id=None):
    text = "<blockquote>🤖 <b>NxtZen Panel Bot</b></blockquote>\n\nWelcome! Please login to access your panel."
    if msg_id:
        edit_msg(chat_id, msg_id, text, main_menu_kb())
    else:
        send_msg(chat_id, text, main_menu_kb())

def handle_admin_menu(chat_id, msg_id, user_id):
    sess = db_get(f"sess:{user_id}") or {}
    token = sess.get("token", "")
    me = api_get(token, "/api/me")
    bot_cfg = api_get(token, "/api/user/bot")
    bot_status = "🟢 Active" if bot_cfg.get("active") == 1 else "🔴 Inactive"
    bot_configured = "✅ Configured" if bot_cfg.get("configured") else "❌ Not configured"
    text = (
        f"<blockquote>👋 <b>Welcome, {me.get('username','User')}</b></blockquote>\n\n"
        f"🤖 Bot: {bot_configured} | {bot_status}\n"
        f"🔐 Role: <b>{me.get('role','user').upper()}</b>\n\n"
        "<i>Choose an option below:</i>"
    )
    edit_msg(chat_id, msg_id, text, admin_menu_kb())

def notify_admin_new_request(requester_user_id, username, tg_name):
    if not ADMIN_TG_ID:
        return
    text = (
        "<blockquote>📝 <b>New ID Request</b></blockquote>\n\n"
        f"👤 Telegram: {tg_name}\n"
        f"🆔 Requested Username: <code>{username}</code>\n\nApprove or Reject?"
    )
    kb = {"inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve_req_{requester_user_id}"},
        {"text": "❌ Reject", "callback_data": f"reject_req_{requester_user_id}"}
    ]]}
    send_msg(ADMIN_TG_ID, text, kb)

def handle_callback(cb, user_id):
    chat_id = cb["message"]["chat"]["id"]
    msg_id  = cb["message"]["message_id"]
    data    = cb["data"]
    cb_id   = cb["id"]
    sess    = db_get(f"sess:{user_id}") or {}
    token   = sess.get("token", "")
    tg("answerCallbackQuery", callback_query_id=cb_id)

    if data.startswith("approve_req_"):
        req_uid = int(data.split("_")[2])
        req = db_get(f"pending:{req_uid}")
        if not req:
            edit_msg(chat_id, msg_id, "<blockquote>⚠️ Request not found or already handled.</blockquote>", back_kb())
            return
        admin_token = get_admin_token()
        result = api_post(admin_token, "/api/admin/users", {"username": req["username"], "password": req["password"], "role": "user"})
        if result.get("ok"):
            edit_msg(chat_id, msg_id, f"<blockquote>✅ <b>ID Created!</b>\n👤 Username: <code>{req['username']}</code></blockquote>", back_kb())
            send_msg(req_uid,
                f"<blockquote>✅ <b>Your ID has been Approved!</b></blockquote>\n\n"
                f"🆔 Username: <code>{req['username']}</code>\n"
                f"🔑 Password: <code>{req['password']}</code>\n\n"
                f"🌐 Login at: {API_URL}")
        else:
            edit_msg(chat_id, msg_id, f"<blockquote>❌ Error: {result.get('error','Unknown')}</blockquote>", back_kb())
            send_msg(req_uid, "<blockquote>❌ <b>ID Creation Failed</b></blockquote>\n\nUsername already exists. Contact admin.")
        db_del(f"pending:{req_uid}")

    elif data.startswith("reject_req_"):
        req_uid = int(data.split("_")[2])
        req = db_get(f"pending:{req_uid}")
        if not req:
            edit_msg(chat_id, msg_id, "<blockquote>⚠️ Request not found or already handled.</blockquote>", back_kb())
            return
        edit_msg(chat_id, msg_id, f"<blockquote>🚫 <b>Request Rejected</b>\n👤 {req['username']}</blockquote>", back_kb())
        send_msg(req_uid, "<blockquote>🚫 <b>Your ID Request was Rejected</b></blockquote>\n\nContact admin for more info.")
        db_del(f"pending:{req_uid}")

    elif data == "request_id":
        if db_get(f"pending:{user_id}"):
            edit_msg(chat_id, msg_id,
                "<blockquote>⏳ <b>Request Pending</b></blockquote>\n\nYour request is already submitted. Please wait for admin approval.",
                {"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "back_to_start"}]]})
            return
        db_set(f"state:{user_id}", {"state": "wait_req_username", "msg_id": msg_id})
        db_del(f"udata:{user_id}")
        edit_msg(chat_id, msg_id,
            "<blockquote>📝 <b>Request ID</b></blockquote>\n\nStep 1/2 — Enter your desired <b>Username</b>:\n\n<i>Send /cancel to cancel</i>")

    elif data == "back_to_start":
        handle_start(chat_id, msg_id)

    elif data == "login":
        db_set(f"state:{user_id}", {"state": "wait_username", "msg_id": msg_id})
        edit_msg(chat_id, msg_id, "<blockquote>🔐 <b>Login</b></blockquote>\n\nEnter your <b>username</b>:")

    elif data == "back_menu":
        if token:
            handle_admin_menu(chat_id, msg_id, user_id)
        else:
            handle_start(chat_id, msg_id)

    elif data == "logout":
        api_post(token, "/api/logout", {})
        db_del(f"sess:{user_id}")
        handle_start(chat_id, msg_id)

    elif data == "refresh":
        handle_admin_menu(chat_id, msg_id, user_id)

    elif data == "panel_status":
        panels = api_get(token, "/api/admin/panels") if sess.get("role") == "admin" else []
        if not panels:
            text = "<blockquote>📊 <b>Panel Status</b></blockquote>\n\nNo panels found."
        else:
            lines = []
            for p in panels:
                status = "🟢" if p.get("status") == "active" else "🔴"
                lines.append(f"{status} <b>{p['name']}</b> — {str(p.get('test_result',''))[:30]}")
            text = "<blockquote>📊 <b>Panel Status</b></blockquote>\n\n" + "\n".join(lines)
        edit_msg(chat_id, msg_id, text, back_kb())

    elif data == "my_numbers":
        nums = api_get(token, "/api/user/numbers")
        total = nums.get("total", 0)
        countries = nums.get("countries", [])[:8]
        lines = [f"🌍 +{c['country_code']} — {c['count']} numbers" for c in countries]
        text = f"<blockquote>📋 <b>My Numbers</b></blockquote>\n\n📊 Total: <b>{total}</b>\n\n" + "\n".join(lines)
        edit_msg(chat_id, msg_id, text, back_kb())

    elif data == "live_sms":
        sms_list = api_get(token, "/api/user/sms")
        if not isinstance(sms_list, list): sms_list = []
        lines = []
        for s in sms_list[:5]:
            lines.append(f"📱 <code>{s.get('number','')}</code>\n💬 {s.get('sms','')[:50]}\n🔑 <b>{s.get('otp','')}</b>")
        text = (f"<blockquote>📨 <b>Live SMS</b> (last {len(lines)})</blockquote>\n\n" + "\n\n".join(lines)) if lines else "<blockquote>📨 <b>Live SMS</b></blockquote>\n\nNo SMS yet."
        edit_msg(chat_id, msg_id, text, back_kb())

    elif data == "bot_config":
        cfg = api_get(token, "/api/user/bot")
        configured = cfg.get("configured", False)
        if configured:
            text = (
                "<blockquote>🤖 <b>Bot Configuration</b></blockquote>\n\n"
                f"📡 SMS Channel: <code>{cfg.get('sms_channel_id','')}</code>\n"
                f"📲 Number Channel: <code>{cfg.get('number_channel_id','')}</code>\n"
                f"👤 Admin ID: <code>{cfg.get('admin_id','')}</code>\n"
                f"Status: {'🟢 Active' if cfg.get('active')==1 else '🔴 Inactive'}"
            )
        else:
            text = "<blockquote>🤖 <b>Bot Configuration</b></blockquote>\n\nBot not configured yet."
        edit_msg(chat_id, msg_id, text, bot_config_kb(configured))

    elif data == "add_bot":
        db_set(f"state:{user_id}", {"state": "wait_new_bot_token", "msg_id": msg_id})
        db_del(f"udata:{user_id}")
        edit_msg(chat_id, msg_id, "<blockquote>➕ <b>Add / Update Bot</b></blockquote>\n\nStep 1/4 — Send your <b>Bot Token</b>:")

    elif data == "delete_bot":
        edit_msg(chat_id, msg_id, "<blockquote>🗑 <b>Delete Bot</b></blockquote>\n\nAre you sure?",
            {"inline_keyboard": [[{"text": "✅ Yes, Delete", "callback_data": "confirm_delete_bot"},
                                   {"text": "❌ Cancel", "callback_data": "bot_config"}]]})

    elif data == "confirm_delete_bot":
        api_delete(token, "/api/user/bot")
        edit_msg(chat_id, msg_id, "<blockquote>🗑 <b>Bot Deleted!</b>\n🔴 Deactivated and removed.</blockquote>", back_kb())

    elif data == "bot_on":
        cfg = api_get(token, "/api/user/bot")
        if cfg.get("configured"):
            api_post(token, "/api/user/bot", {"bot_token": cfg["bot_token"], "sms_channel_id": cfg["sms_channel_id"], "number_channel_id": cfg["number_channel_id"], "admin_id": cfg["admin_id"]})
            edit_msg(chat_id, msg_id, "<blockquote>✅ <b>Bot Activated!</b>\n🟢 SMS polling started.</blockquote>", back_kb())
        else:
            edit_msg(chat_id, msg_id, "<blockquote>❌ Bot not configured yet.</blockquote>", back_kb())

    elif data == "bot_off":
        api_delete(token, "/api/user/bot")
        edit_msg(chat_id, msg_id, "<blockquote>🔴 <b>Bot Deactivated!</b></blockquote>", back_kb())

    elif data == "reset_sms":
        db_set(f"state:{user_id}", {"state": "wait_sms_channel", "msg_id": msg_id})
        edit_msg(chat_id, msg_id, "<blockquote>♻️ <b>Reset SMS Channel</b></blockquote>\n\nSend new <b>SMS Channel ID</b>:")

    elif data == "reset_num":
        db_set(f"state:{user_id}", {"state": "wait_num_channel", "msg_id": msg_id})
        edit_msg(chat_id, msg_id, "<blockquote>♻️ <b>Reset Number Channel</b></blockquote>\n\nSend new <b>Number Channel ID</b>:")

    elif data == "forward_nums":
        db_set(f"state:{user_id}", {"state": "wait_forward_file", "msg_id": msg_id})
        edit_msg(chat_id, msg_id, "<blockquote>📤 <b>Forward Numbers</b></blockquote>\n\nSend a <b>.txt file</b>:")

    elif data == "dl_numbers":
        edit_msg(chat_id, msg_id, "<blockquote>🗂 <b>Downloading Numbers...</b></blockquote>", back_kb())
        send_numbers_file(chat_id, msg_id, token)

    elif data == "my_panels":
        panels = api_get(token, "/api/user/numbers")
        countries = panels.get("countries", [])
        text = (f"<blockquote>👥 <b>My Panels</b></blockquote>\n\n"
                f"📊 Total Numbers: <b>{panels.get('total',0)}</b>\n"
                f"🌍 Countries: <b>{len(countries)}</b>")
        edit_msg(chat_id, msg_id, text, back_kb())

    elif data == "my_token":
        edit_msg(chat_id, msg_id, f"<blockquote>🔑 <b>Your API Token</b></blockquote>\n\n<code>{token}</code>", back_kb())

    elif data == "api_docs":
        text = (
            "<blockquote>📚 <b>API Documentation</b></blockquote>\n\n"
            f"🌐 <b>Base URL:</b>\n<code>{API_URL}</code>\n\n"
            f"🔐 <b>Your Token:</b>\n<code>{token}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📥 <b>GET /api/user/numbers</b>\n"
            f"<code>curl {API_URL}/api/user/numbers \\\n  -H \"X-Token: {token}\"</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📨 <b>GET /api/user/sms</b>\n"
            f"<code>curl {API_URL}/api/user/sms \\\n  -H \"X-Token: {token}\"</code>"
        )
        edit_msg(chat_id, msg_id, text, back_kb())

    elif data == "confirm_replace":
        nd = db_get(f"udata:{user_id}") or {}
        result = api_post(token, "/api/user/bot", {"bot_token": nd.get("new_bot_token",""), "sms_channel_id": nd.get("sms_channel_id",""), "number_channel_id": nd.get("number_channel_id",""), "admin_id": nd.get("admin_id","")})
        if result.get("ok"):
            edit_msg(chat_id, msg_id, f"<blockquote>✅ <b>Bot Configured!</b>\n@{result.get('bot_name','')} is now active.</blockquote>", back_kb())
        else:
            edit_msg(chat_id, msg_id, f"<blockquote>❌ Error: {result.get('error','Unknown error')}</blockquote>", back_kb())
        db_del(f"udata:{user_id}")

    elif data == "cancel_replace":
        db_del(f"udata:{user_id}")
        handle_admin_menu(chat_id, msg_id, user_id)

def send_numbers_file(chat_id, msg_id, token):
    import io
    nums = api_get(token, "/api/user/numbers")
    countries = nums.get("countries", [])
    all_nums = []
    for c in countries:
        cc = c["country_code"]; ns = c["numbers"]; all_nums.extend(ns)
        content = "\n".join(ns).encode()
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data={"chat_id": chat_id, "caption": f"🌍 +{cc} — {len(ns)} numbers"},
            files={"document": (f"numbers_{cc}.txt", io.BytesIO(content), "text/plain")}, timeout=15)
    all_content = "\n".join(all_nums).encode()
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        data={"chat_id": chat_id, "caption": f"🌐 ALL Mixed — {len(all_nums)} numbers"},
        files={"document": ("numbers_ALL.txt", io.BytesIO(all_content), "text/plain")}, timeout=15)
    edit_msg(chat_id, msg_id, f"<blockquote>✅ Sent {len(countries)} country files + 1 mixed\n📊 Total: {len(all_nums)} numbers</blockquote>", back_kb())

def handle_message(msg, user_id):
    chat_id = msg["chat"]["id"]
    text    = msg.get("text", "")
    doc     = msg.get("document")
    state   = db_get(f"state:{user_id}") or {}
    sess    = db_get(f"sess:{user_id}") or {}
    token   = sess.get("token", "")
    msg_id  = state.get("msg_id")
    delete_msg(chat_id, msg["message_id"])

    if text == "/cancel":
        db_del(f"state:{user_id}"); db_del(f"udata:{user_id}")
        if token:
            new_mid = send_msg(chat_id, "❌ Cancelled.")
            handle_admin_menu(chat_id, new_mid, user_id)
        else:
            send_msg(chat_id, "❌ Cancelled.", main_menu_kb())
        return

    if text == "/start":
        db_del(f"state:{user_id}")
        handle_start(chat_id)
        return

    if text == "/admin" and token:
        new_mid = send_msg(chat_id, "Loading...", admin_menu_kb())
        handle_admin_menu(chat_id, new_mid, user_id)
        return

    st = state.get("state", "")

    if st == "wait_req_username" and text:
        udata = db_get(f"udata:{user_id}") or {}
        udata["req_username"] = text.strip()
        db_set(f"udata:{user_id}", udata)
        db_set(f"state:{user_id}", {"state": "wait_req_password", "msg_id": msg_id})
        if msg_id:
            edit_msg(chat_id, msg_id,
                f"<blockquote>📝 <b>Request ID</b></blockquote>\n\n✅ Username: <code>{text.strip()}</code>\n\nStep 2/2 — Enter your desired <b>Password</b>:\n\n<i>Send /cancel to cancel</i>")

    elif st == "wait_req_password" and text:
        udata = db_get(f"udata:{user_id}") or {}
        uname = udata.get("req_username",""); passw = text.strip()
        from_info = msg.get("from", {})
        tg_name = f"@{from_info.get('username')}" if from_info.get("username") else from_info.get("first_name","User")
        db_set(f"pending:{user_id}", {"username": uname, "password": passw, "tg_name": tg_name, "chat_id": chat_id})
        db_del(f"state:{user_id}"); db_del(f"udata:{user_id}")
        if msg_id:
            edit_msg(chat_id, msg_id,
                f"<blockquote>⏳ <b>Request Submitted!</b></blockquote>\n\n🆔 Username: <code>{uname}</code>\n\nPlease wait for admin approval.",
                {"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "back_to_start"}]]})
        notify_admin_new_request(user_id, uname, tg_name)

    elif st == "wait_username" and text:
        db_set(f"udata:{user_id}", {"username": text})
        db_set(f"state:{user_id}", {"state": "wait_password", "msg_id": msg_id})
        if msg_id:
            edit_msg(chat_id, msg_id, "<blockquote>🔐 <b>Login</b></blockquote>\n\nEnter your <b>password</b>:")

    elif st == "wait_password" and text:
        udata = db_get(f"udata:{user_id}") or {}
        uname = udata.get("username", "")
        result = api_post("", "/api/login", {"username": uname, "password": text})
        if result.get("token"):
            db_set(f"sess:{user_id}", {"token": result["token"], "role": result.get("role","user"), "username": result.get("username","")})
            db_del(f"state:{user_id}"); db_del(f"udata:{user_id}")
            if msg_id: handle_admin_menu(chat_id, msg_id, user_id)
        else:
            db_del(f"state:{user_id}")
            if msg_id:
                edit_msg(chat_id, msg_id, "<blockquote>❌ <b>Login Failed</b></blockquote>\n\nInvalid credentials.",
                    {"inline_keyboard": [[{"text": "🔄 Try Again", "callback_data": "login"}]]})

    elif st == "wait_new_bot_token" and text:
        me = requests.get(f"https://api.telegram.org/bot{text}/getMe", timeout=8).json()
        if not me.get("ok"):
            if msg_id: edit_msg(chat_id, msg_id, "<blockquote>❌ <b>Invalid Bot Token!</b></blockquote>\n\nSend a valid token:")
            return
        udata = db_get(f"udata:{user_id}") or {}
        udata["new_bot_token"] = text
        udata["new_bot_name"] = me["result"]["username"]
        db_set(f"udata:{user_id}", udata)
        db_set(f"state:{user_id}", {"state": "wait_new_sms_channel", "msg_id": msg_id})
        if msg_id:
            edit_msg(chat_id, msg_id,
                f"<blockquote>➕ <b>Add / Update Bot</b></blockquote>\n\n✅ Bot: @{me['result']['username']}\n\nStep 2/4 — Send <b>SMS Channel ID</b>:")

    elif st == "wait_new_sms_channel" and text:
        udata = db_get(f"udata:{user_id}") or {}
        udata["sms_channel_id"] = text.strip()
        db_set(f"udata:{user_id}", udata)
        db_set(f"state:{user_id}", {"state": "wait_new_num_channel", "msg_id": msg_id})
        if msg_id:
            edit_msg(chat_id, msg_id,
                f"<blockquote>➕ <b>Add / Update Bot</b></blockquote>\n\n✅ SMS Channel: <code>{text.strip()}</code>\n\nStep 3/4 — Send <b>Number Channel ID</b>:")

    elif st == "wait_new_num_channel" and text:
        udata = db_get(f"udata:{user_id}") or {}
        udata["number_channel_id"] = text.strip()
        db_set(f"udata:{user_id}", udata)
        db_set(f"state:{user_id}", {"state": "wait_new_admin_id", "msg_id": msg_id})
        if msg_id:
            edit_msg(chat_id, msg_id,
                f"<blockquote>➕ <b>Add / Update Bot</b></blockquote>\n\n✅ Number Channel: <code>{text.strip()}</code>\n\nStep 4/4 — Send <b>Telegram Admin ID</b>:")

    elif st == "wait_new_admin_id" and text:
        udata = db_get(f"udata:{user_id}") or {}
        udata["admin_id"] = text.strip()
        db_set(f"udata:{user_id}", udata)
        db_del(f"state:{user_id}")
        summary = (
            "<blockquote>➕ <b>Confirm Bot Setup</b></blockquote>\n\n"
            f"🤖 Bot: @{udata.get('new_bot_name','')}\n"
            f"📡 SMS Channel: <code>{udata.get('sms_channel_id','')}</code>\n"
            f"📲 Number Channel: <code>{udata.get('number_channel_id','')}</code>\n"
            f"👤 Admin ID: <code>{udata.get('admin_id','')}</code>\n\nConfirm?"
        )
        if msg_id:
            edit_msg(chat_id, msg_id, summary,
                {"inline_keyboard": [[{"text": "✅ Confirm", "callback_data": "confirm_replace"},
                                       {"text": "❌ Cancel", "callback_data": "cancel_replace"}]]})

    elif st == "wait_sms_channel" and text:
        cfg = api_get(token, "/api/user/bot")
        api_post(token, "/api/user/bot", {"bot_token": cfg.get("bot_token",""), "sms_channel_id": text.strip(), "number_channel_id": cfg.get("number_channel_id",""), "admin_id": cfg.get("admin_id","")})
        db_del(f"state:{user_id}")
        if msg_id: edit_msg(chat_id, msg_id, f"<blockquote>✅ SMS Channel updated to <code>{text.strip()}</code></blockquote>", back_kb())

    elif st == "wait_num_channel" and text:
        cfg = api_get(token, "/api/user/bot")
        api_post(token, "/api/user/bot", {"bot_token": cfg.get("bot_token",""), "sms_channel_id": cfg.get("sms_channel_id",""), "number_channel_id": text.strip(), "admin_id": cfg.get("admin_id","")})
        db_del(f"state:{user_id}")
        if msg_id: edit_msg(chat_id, msg_id, f"<blockquote>✅ Number Channel updated to <code>{text.strip()}</code></blockquote>", back_kb())

    elif st == "wait_forward_file" and doc:
        import io
        file_id = doc["file_id"]
        file_resp = tg("getFile", file_id=file_id)
        fpath = file_resp.get("result", {}).get("file_path","")
        if fpath:
            file_content = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fpath}", timeout=15)
            nums = [n.strip() for n in file_content.text.strip().split("\n") if n.strip()]
            cfg = api_get(token, "/api/user/bot")
            num_ch = cfg.get("number_channel_id","")
            content_bytes = "\n".join(nums).encode()
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": num_ch, "caption": f"📲 {len(nums)} numbers forwarded"},
                files={"document": (f"forwarded_{len(nums)}.txt", io.BytesIO(content_bytes), "text/plain")}, timeout=15)
            db_del(f"state:{user_id}")
            if msg_id: edit_msg(chat_id, msg_id, f"<blockquote>✅ <b>{len(nums)} numbers</b> forwarded!</blockquote>", back_kb())

# ── VERCEL ENTRY POINT ───────────────────────────────────────

def handler(request):
    from http.server import BaseHTTPRequestHandler
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                update = _json.loads(body)
                db_init()
                if "callback_query" in update:
                    cb = update["callback_query"]
                    handle_callback(cb, cb["from"]["id"])
                elif "message" in update:
                    msg = update["message"]
                    uid = msg.get("from", {}).get("id", 0)
                    if msg["chat"]["type"] == "private":
                        handle_message(msg, uid)
            except Exception as e:
                print(f"Handler error: {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    return Handler
