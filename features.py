"""Step 3: behavioural features for a list of wallets, computed from on-chain data only.

Usage: python3 features.py data/interim/wallets.txt data/processed/wallet_features.jsonl

Per wallet (about 130-330 credits): recent 100 full transactions, the oldest transaction,
a capped signature count, and the funding source. Labels are NOT read here; they come
from identity lookups and are joined later, so features cannot leak the label.
"""
import collections
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import helius

PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
COUNT_PAGES = 5  # signature pages of 1000; counts above 5k are reported as capped
CATEGORY = {r["address"]: r["category"] for r in csv.DictReader(open("data/seeds/orb_programs.csv"))}
INVOKE = re.compile(r"^Program (\w+) invoke \[")


def tx_count(address):
    n, token = 0, None
    for _ in range(COUNT_PAGES):
        sigs, token = helius.transactions(address, limit=1000, full=False, token=token)
        n += len(sigs)
        if not token or len(sigs) < 1000:
            return n, False
    return n, True


def features(address):
    txs, _ = helius.transactions(address, limit=100)
    oldest, _ = helius.transactions(address, limit=1, full=False, order="asc")
    count, capped = tx_count(address)
    funding = helius.funded_by(address)

    cats, pump_ops, counterparties = collections.Counter(), collections.Counter(), set()
    failed = signer_txs = 0
    sol_delta = 0
    for tx in txs:
        meta, msg = tx["meta"], tx["transaction"]["message"]
        keys = msg["accountKeys"] + meta["loadedAddresses"]["writable"] + meta["loadedAddresses"]["readonly"]
        failed += meta["err"] is not None
        if address in keys[: msg["header"]["numRequiredSignatures"]]:
            signer_txs += 1
        if address in keys:
            i = keys.index(address)
            sol_delta += meta["postBalances"][i] - meta["preBalances"][i]
        programs = {m.group(1) for line in meta.get("logMessages") or [] if (m := INVOKE.match(line))}
        for p in programs:
            cats[CATEGORY.get(p, "Other")] += 1
        stack = []  # attribute "Instruction: X" logs to the program currently executing
        for line in meta.get("logMessages") or []:
            if m := INVOKE.match(line):
                stack.append(m.group(1))
            elif line.startswith("Program ") and line.endswith((" success", " failed")) or " failed: " in line:
                stack and stack.pop()
            elif line.startswith("Program log: Instruction: ") and stack and stack[-1] == PUMP:
                pump_ops[line.split(": ", 2)[2]] += 1
        counterparties.update(k for k in msg["accountKeys"][: msg["header"]["numRequiredSignatures"]] if k != address)

    times = [tx["blockTime"] for tx in txs if tx.get("blockTime")]
    span_h = (max(times) - min(times)) / 3600 if len(times) > 1 else None
    return {
        "address": address,
        "fetched_at": int(time.time()),
        "tx_count": count, "tx_count_capped": capped,
        "first_seen": oldest[0]["blockTime"] if oldest else None,
        "sample_size": len(txs),
        "sample_span_hours": round(span_h, 2) if span_h is not None else None,
        "sample_failed": failed,
        "sample_as_signer": signer_txs,
        "sample_sol_delta": sol_delta / 1e9,
        "sample_program_categories": dict(cats.most_common()),
        "sample_pump_instructions": dict(pump_ops.most_common(8)),
        "sample_cosigners": len(counterparties),
        "funding": funding and {k: funding.get(k) for k in ("funder", "funderName", "funderType", "amount", "timestamp", "signature")},
    }


def main(src, dst):
    wallets = [w.strip() for w in open(src) if w.strip()]
    done = set()
    if os.path.exists(dst):
        done = {json.loads(line)["address"] for line in open(dst)}
    todo = [w for w in wallets if w not in done]
    with open(dst, "a") as f, ThreadPoolExecutor(16) as pool:
        for i, row in enumerate(pool.map(_safe, todo), 1):
            if row:
                f.write(json.dumps(row) + "\n")
                f.flush()
            if i % 50 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr)


def _safe(address):
    try:
        return features(address)
    except Exception as e:  # one bad wallet must not stop the run; it is retried on the next run
        print(f"skip {address}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main(*sys.argv[1:3])
