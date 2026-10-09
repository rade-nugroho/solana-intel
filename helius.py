"""Minimal Helius client: RPC, getTransactionsForAddress, batch identity.

The API key is read from ~/.helius_key (never logged, never written to data).
"""
import json
import os
import time
import urllib.error
import urllib.request

KEY = open(os.path.expanduser("~/.helius_key")).read().strip()
RPC = "https://mainnet.helius-rpc.com/"
API = "https://api.helius.xyz/v1"
# Cloudflare rejects the default Python-urllib agent (error 1010).
HEADERS = {"Content-Type": "application/json", "User-Agent": "solana-intel-dataset/0.1", "X-Api-Key": KEY}


def _post(url, body=None, tries=6):
    """POST JSON, or GET when body is None. Returns None on 404 (normal for unknown wallets)."""
    data = None if body is None else json.dumps(body).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data, HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code != 429 and e.code < 500 or attempt == tries - 1:
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}") from None
        except OSError:  # URLError and, on Python 3.9, socket.timeout
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)


def rpc(method, params):
    res = _post(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in res:
        raise RuntimeError(f"{method}: {res['error']}")
    return res["result"]


def transactions(address, limit=100, full=True, token=None, order="desc", **filters):
    """One page of getTransactionsForAddress (newest first by default). Returns (txs, next_token)."""
    opts = {"transactionDetails": "full" if full else "signatures", "limit": limit, "sortOrder": order,
            "maxSupportedTransactionVersion": 1, "encoding": "json"}
    if token:
        opts["paginationToken"] = token
    if filters:
        opts["filters"] = filters
    res = rpc("getTransactionsForAddress", [address, opts])
    return res.get("data", []), res.get("paginationToken")


def transfers(address, token=None, **config):
    """One page (<=100) of getTransfersByAddress. Returns (rows, next_token). 10 credits."""
    config = {"limit": 100, **config}
    if token:
        config["paginationToken"] = token
    res = rpc("getTransfersByAddress", [address, config])
    return res.get("data", []), res.get("paginationToken")


def funded_by(address):
    """First incoming SOL transfer: {funder, funderName, funderType, amount, timestamp, signature} or None. 100 credits."""
    return _post(f"{API}/wallet/{address}/funded-by")


SYSTEM_PROGRAM = "11111111111111111111111111111111"


def owners(addresses):
    """{address: owner program or None if the account does not exist}. 1 credit per 100."""
    out = {}
    for i in range(0, len(addresses), 100):
        chunk = addresses[i:i + 100]
        res = rpc("getMultipleAccounts", [chunk, {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}])
        out.update({a: acc and acc["owner"] for a, acc in zip(chunk, res["value"])})
    return out


def identities(addresses):
    """Batch identity, chunked by 100 (100 credits per chunk). Returns {address: record}."""
    out = {}
    for i in range(0, len(addresses), 100):
        for rec in _post(f"{API}/wallet/batch-identity", {"addresses": addresses[i:i + 100]}) or []:
            out[rec["address"]] = rec
    return out
