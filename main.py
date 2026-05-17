"""Main wallet scanner — run by GitHub Actions every 30 min.
Scans each wallet on BOTH Ethereum and BSC.
Also checks for Telegram commands (/add, /remove, /list, /help)."""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.chains.evm import get_latest_block, get_recent_txs, CHAIN_NAMES
from src.analyzer import analyze_wallet, load_state, save_state
from src.notifier import init as tg_init, send_alert, send_summary
from src.notifier import process_commands

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config", "wallets.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def main():
    config = load_config()
    state = load_state()

    bot_token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    settings = config["settings"]
    rpc_urls = config["rpc"]
    wallets = config.get("wallets", [])

    tg_init(bot_token)

    # --- 1. Komutları işle (ekle/sil/listele) ---
    config = process_commands(config)
    wallets = config.get("wallets", [])
    if config != load_config():
        save_config(config)

    # --- 2. Hiç cüzdan yoksa uyar ve çık ---
    if not wallets:
        send_message(chat_id, "⚠️ Henüz cüzdan eklenmemiş. /add 0xadres ile ekle.")
        return

    # --- 3. Tüm cüzdanları tara ---
    chains_to_scan = [("ethereum", rpc_urls["ethereum"]),
                      ("bsc", rpc_urls["bsc"])]

    alert_count = 0
    summary_lines = []
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for wallet in wallets:
        wallet_lower = wallet.lower().strip()
        for chain, rpc in chains_to_scan:
            latest = get_latest_block(rpc)
            last_scan = state.get("last_scans", {}).get(chain, latest - 2000)
            from_block = max(last_scan, latest - 2000)
            wallet_key = f"{chain}:{wallet_lower}"

            try:
                new_txs = get_recent_txs(
                    rpc, wallet_lower, chain,
                    from_block, latest,
                    max_tx=settings["max_tx_per_wallet"]
                )
            except Exception as e:
                print(f"[{chain.upper()}] {wallet_lower[:10]}... hata: {e}")
                continue

            if not new_txs:
                continue

            print(f"[{chain.upper()}] {wallet_lower[:10]}... → {len(new_txs)} yeni tx")

            history = state.get("tx_history", {}).get(wallet_key, [])
            analysis = analyze_wallet(wallet_lower, chain, new_txs, history)

            # Merge new txs into history
            existing_hashes = {t["tx_hash"] for t in history}
            for tx in new_txs:
                if tx["tx_hash"] not in existing_hashes:
                    history.insert(0, tx)
            history = history[:100]

            if wallet_key not in state.setdefault("tx_history", {}):
                state["tx_history"][wallet_key] = []
            state["tx_history"][wallet_key] = history

            if analysis["signal"] in ("strong_buy", "buy"):
                alert_count += 1
                send_alert(chat_id, wallet_lower, chain, analysis)

            short = f"{wallet_lower[:6]}...{wallet_lower[-4:]}"
            score = analysis["score"]
            sig = analysis["signal"]
            chain_icon = "🔷" if chain == "ethereum" else "🟡"
            summary_lines.append(
                f"{chain_icon} {short}: skor {score:.3f} | {sig.upper()} | "
                f"{analysis.get('new_txs_24h', 0)} yeni tx"
            )

    # --- 4. Son scan bloklarını güncelle ---
    for chain, rpc in chains_to_scan:
        try:
            state.setdefault("last_scans", {})[chain] = get_latest_block(rpc)
        except Exception:
            pass

    save_state(state)

    # --- 5. Özet gönder ---
    send_summary(chat_id, summary_lines, alert_count, now_ts)
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    main()
