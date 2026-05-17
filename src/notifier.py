"""Telegram notification sender and command processor."""

import json
from urllib.request import Request, urlopen

BOT_TOKEN = None


def _get_url(method: str):
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def init(token: str):
    global BOT_TOKEN
    BOT_TOKEN = token


def send_message(chat_id: str, text: str):
    """Send a Telegram message. Max 4096 chars."""
    if not BOT_TOKEN:
        print("Telegram token ayarlanmamış")
        return
    url = _get_url("sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f"Telegram hatası: {e}")
        return None


def get_pending_updates(last_update_id: int = 0) -> list:
    """Get pending messages (commands) sent to the bot."""
    if not BOT_TOKEN:
        return []
    url = _get_url("getUpdates") + f"?offset={last_update_id + 1}&timeout=5"
    try:
        resp = urlopen(url, timeout=10)
        data = json.loads(resp.read())
        return data.get("result", [])
    except Exception:
        return []


def process_commands(config: dict) -> dict:
    """Check for pending commands and process them. Returns updated config."""
    updates = get_pending_updates(config.get("last_update_id", 0))
    if not updates:
        return config

    chat_id = config["telegram"]["chat_id"]
    wallets = config["wallets"]
    max_update = config.get("last_update_id", 0)
    changes = False

    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id > max_update:
            max_update = update_id

        msg = update.get("message", {})
        text = (msg.get("text") or "").strip()
        sender_id = str(msg.get("chat", {}).get("id", ""))

        # Only process commands from the authorized chat
        if sender_id != chat_id:
            continue

        if text.startswith("/add"):
            parts = text.split()
            if len(parts) < 2:
                send_message(chat_id, "⚠️ Kullanım: /add 0xadres")
                continue
            addr = parts[1].strip().lower()
            if not addr.startswith("0x") or len(addr) != 42:
                send_message(chat_id, "⚠️ Geçersiz adres formatı")
                continue
            if addr in wallets:
                send_message(chat_id, f"ℹ️ {addr[:10]}... zaten listede")
            else:
                wallets.append(addr)
                send_message(chat_id, f"✅ {addr[:10]}... eklendi ({len(wallets)} cüzdan)")
                changes = True

        elif text.startswith("/remove") or text.startswith("/sil"):
            parts = text.split()
            if len(parts) < 2:
                send_message(chat_id, "⚠️ Kullanım: /remove 0xadres")
                continue
            addr = parts[1].strip().lower()
            if addr in wallets:
                wallets.remove(addr)
                send_message(chat_id, f"🗑️ {addr[:10]}... silindi ({len(wallets)} cüzdan)")
                changes = True
            else:
                send_message(chat_id, f"❌ {addr[:10]}... listede bulunamadı")

        elif text == "/list":
            if not wallets:
                send_message(chat_id, "📭 Hiç cüzdan yok")
            else:
                lines = [f"<b>📋 Cüzdanlar ({len(wallets)}):</b>"]
                for i, w in enumerate(wallets, 1):
                    lines.append(f"{i}. <code>{w}</code>")
                send_message(chat_id, "\n".join(lines))

        elif text == "/help" or text == "/start":
            help_text = (
                "<b>🤖 Wallet Tracker Bot</b>\n\n"
                "<b>Komutlar:</b>\n"
                "/add 0x... — Cüzdan ekle\n"
                "/remove 0x... — Cüzdan sil\n"
                "/list — Tüm cüzdanları listele\n"
                "/status — Bot durumu\n"
                "/help — Bu mesaj\n\n"
                "Bot her 30 dk'da cüzdanları tarar ve "
                "önemli hareketlerde bildirim gönderir."
            )
            send_message(chat_id, help_text)

        elif text == "/status":
            status = (
                f"<b>📊 Bot Durumu</b>\n"
                f"📋 Cüzdan: {len(wallets)}\n"
                f"⏱️ Tarama: Her 30 dk\n"
                f"🔷 Ethereum: active\n"
                f"🟡 BSC: active"
            )
            send_message(chat_id, status)

    if changes:
        config["wallets"] = wallets
    config["last_update_id"] = max_update
    return config


def send_alert(chat_id: str, wallet: str, chain: str, analysis: dict):
    """Send a formatted alert about wallet activity."""
    emoji_map = {"strong_buy": "🚨", "buy": "🟢", "hold": "⚪", "skip": "⚫"}
    emoji = emoji_map.get(analysis.get("signal", "hold"), "⚪")
    chain_emoji = {"ethereum": "🔷", "bsc": "🟡"}
    ce = chain_emoji.get(chain, "⛓️")

    text = (
        f"{emoji} <b>Wallet Analizi</b>\n"
        f"{ce} {chain.upper()}\n"
        f"📍 <code>{wallet[:10]}...{wallet[-6:]}</code>\n"
        f"──────────────\n"
        f"📊 <b>Skor:</b> {analysis.get('score', 0):.3f}\n"
        f"📈 <b>Sinyal:</b> {analysis.get('signal', 'hold').upper()}\n"
        f"💬 <b>Sebep:</b> {analysis.get('reason', '-')}\n"
        f"──────────────\n"
        f"🔄 <b>İşlem:</b> {analysis.get('tx_count', 0)}\n"
        f"🟢 Alım: {analysis.get('buys', 0)} | 🔴 Satım: {analysis.get('sells', 0)}\n"
        f"📦 Alım: {analysis.get('buy_volume', 0):.2f}\n"
        f"📤 Satım: {analysis.get('sell_volume', 0):.2f}\n"
        f"🆕 Son 24s: {analysis.get('new_txs_24h', 0)} tx"
    )
    return send_message(chat_id, text)


def send_summary(chat_id: str, summary_lines: list, alert_count: int, timestamp: str):
    """Send scan summary report."""
    if not summary_lines:
        send_message(chat_id,
                     f"<b>📋 Tarama — {timestamp}</b>\n──────────────\n"
                     f"Hiçbir cüzwanda yeni işlem yok.")
        return

    text = f"<b>📋 Tarama — {timestamp}</b>\n──────────────\n"
    text += "\n".join(summary_lines)
    text += f"\n──────────────\n🚨 {alert_count} alert"
    send_message(chat_id, text)
