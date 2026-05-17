"""EVM chain adapter — Ethereum & BSC transaction fetcher."""

import json
import time
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

CHAIN_NAMES = {
    "ethereum": {"explorer": "etherscan.io", "native": "ETH", "decimals": 18},
    "bsc": {"explorer": "bscscan.com", "native": "BNB", "decimals": 18},
}

def _rpc_call(rpc_url: str, method: str, params: list) -> dict:
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = Request(rpc_url, data=data, headers={"Content-Type": "application/json"})
    resp = urlopen(req, timeout=15)
    result = json.loads(resp.read())
    if "error" in result:
        raise Exception(f"RPC error: {result['error']}")
    return result["result"]


def get_latest_block(rpc_url: str) -> int:
    return int(_rpc_call(rpc_url, "eth_blockNumber", []), 16)


def get_native_balance(rpc_url: str, address: str, block: Optional[int] = None) -> float:
    params = [address, hex(block) if block else "latest"]
    bal_hex = _rpc_call(rpc_url, "eth_getBalance", params)
    return int(bal_hex, 16) / 1e18


def get_token_balance(rpc_url: str, token_address: str, wallet: str) -> float:
    """Get ERC-20 balance for a wallet."""
    sig = "0x70a08231"  # balanceOf(address)
    padded = wallet[2:].lower().zfill(64)
    data = sig + padded
    params = [{"to": token_address, "data": data}, "latest"]
    result = _rpc_call(rpc_url, "eth_call", params)
    if result == "0x":
        return 0.0
    return int(result, 16) / 1e18


def _decode_log(log: dict, chain: str) -> Optional[dict]:
    """Decode a Transfer event log into a normalized dict."""
    topics = log.get("topics", [])
    if len(topics) != 4:
        return None
    if topics[0] != ERC20_TRANSFER_TOPIC:
        return None
    from_addr = "0x" + topics[1][-40:]
    to_addr = "0x" + topics[2][-40:]
    value = int(log["data"], 16) / 1e18
    block = int(log["blockNumber"], 16)
    tx_hash = log["transactionHash"]

    # Skip mint/burn
    if from_addr == "0x0000000000000000000000000000000000000000":
        return None
    if to_addr == "0x0000000000000000000000000000000000000000":
        return None

    return {
        "chain": chain,
        "type": "sell" if from_addr != "0x" else "buy",
        "from": from_addr,
        "to": to_addr,
        "value": value,
        "block": block,
        "tx_hash": tx_hash,
        "explorer_url": f"https://{CHAIN_NAMES[chain]['explorer']}/tx/{tx_hash}",
    }


def get_recent_txs(rpc_url: str, wallet: str, chain: str,
                   from_block: int, to_block: int, max_tx: int = 20) -> list:
    """Get recent Transfer events involving this wallet."""
    params = [{
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "topics": [
            ERC20_TRANSFER_TOPIC,
            None,
            "0x" + "0" * 24 + wallet[2:].lower(),
            None
        ]
    }]
    try:
        logs = _rpc_call(rpc_url, "eth_getLogs", params)
    except Exception:
        logs = []

    txs = []
    for log in logs:
        tx = _decode_log(log, chain)
        if tx and tx["from"] == wallet.lower():
            tx["type"] = "sell"
            txs.append(tx)
        elif tx and tx["to"] == wallet.lower():
            tx["type"] = "buy"
            txs.append(tx)

    # Also get outgoing transfers
    params_out = [{
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "topics": [
            ERC20_TRANSFER_TOPIC,
            "0x" + "0" * 24 + wallet[2:].lower(),
            None,
            None
        ]
    }]
    try:
        logs_out = _rpc_call(rpc_url, "eth_getLogs", params_out)
    except Exception:
        logs_out = []

    for log in logs_out:
        tx = _decode_log(log, chain)
        if tx and tx["from"] == wallet.lower():
            tx["type"] = "sell"
            txs.append(tx)

    # Deduplicate by tx_hash
    seen = set()
    unique = []
    for tx in sorted(txs, key=lambda x: x["block"], reverse=True):
        if tx["tx_hash"] not in seen:
            seen.add(tx["tx_hash"])
            unique.append(tx)

    return unique[:max_tx]
