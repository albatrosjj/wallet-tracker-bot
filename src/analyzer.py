"""Transaction analysis — P&L, timing, scoring."""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"tx_history": {}, "last_scans": {}}


def save_state(state: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def analyze_wallet(wallet: str, chain: str, new_txs: list,
                   all_history: list, price_usd: float = 0.0) -> dict:
    """Analyze a wallet's recent activity and produce a score."""
    if not all_history and not new_txs:
        return {"score": 0.5, "signal": "hold", "reason": "yeterli veri yok"}

    all_txs = all_history + new_txs

    # Recent tx volume (last 30 days estimate by block count)
    recent = [t for t in all_txs if t.get("block", 0) > 0]
    if not recent:
        return {"score": 0.5, "signal": "hold", "reason": "işlem yok"}

    # Buy/sell ratio
    buys = [t for t in recent if t["type"] == "buy"]
    sells = [t for t in recent if t["type"] == "sell"]
    total_buys = sum(t["value"] for t in buys)
    total_sells = sum(t["value"] for t in sells)

    # Activity score (30%)
    tx_count = len(recent)
    activity_score = min(tx_count / 20, 1.0) * 0.3

    # Volume score (30%)
    total_volume = total_buys + total_sells
    volume_score = min(total_volume / 10_000, 1.0) * 0.3

    # Net flow score (40%)
    if total_buys + total_sells > 0:
        net_ratio = (total_sells - total_buys) / (total_buys + total_sells)
        # Negative net ratio = more buys = bullish
        flow_score = max(0, (1 - net_ratio) * 0.4)
    else:
        flow_score = 0.2

    score = round(activity_score + volume_score + flow_score, 3)

    new_count = len(new_txs)
    total_vol_24h = sum(t["value"] for t in new_txs) if new_txs else 0

    # Signal
    if score >= 0.7 and new_count >= 2:
        signal = "strong_buy"
        reason = f"yüksek aktivite ({new_count} yeni işlem, {total_vol_24h:.2f} token)"
    elif score >= 0.5 and new_count >= 1:
        signal = "buy"
        reason = f"pozitif hareket ({new_count} yeni işlem)"
    elif score >= 0.3:
        signal = "hold"
        reason = "nötr, takipte"
    else:
        signal = "skip"
        reason = "düşük aktivite"

    return {
        "score": score,
        "signal": signal,
        "reason": reason,
        "tx_count": tx_count,
        "buys": len(buys),
        "sells": len(sells),
        "buy_volume": round(total_buys, 2),
        "sell_volume": round(total_sells, 2),
        "new_txs_24h": new_count,
    }
