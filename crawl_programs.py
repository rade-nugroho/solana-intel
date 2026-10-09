"""Step 1: sample transactions of every seed program and collect their signers.

For each program, one page of up to PER_WINDOW full transactions is taken ending at
each of several points in time, so the sample is not just the last few seconds.
Output (one slim row per transaction; the signature lets anyone re-fetch it):
  data/raw/program_txs.jsonl   {program, signature, slot, block_time, signers, err}
"""
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import helius

PER_WINDOW = 100
AGES_DAYS = [0, 7, 30, 90]
OUT = "data/raw/program_txs.jsonl"


def signers(tx):
    keys = tx["transaction"]["message"]["accountKeys"]
    return keys[: tx["transaction"]["message"]["header"]["numRequiredSignatures"]]


def sample(program, now):
    rows, seen = [], set()
    for age in AGES_DAYS:
        filters = {"blockTime": {"lte": now - age * 86400}} if age else {}
        try:
            txs, _ = helius.transactions(program, limit=PER_WINDOW, **filters)
        except (RuntimeError, OSError) as e:  # e.g. native programs: "Address is not supported"; timeouts
            print(f"skip {program}: {e}", file=sys.stderr)
            return program, rows
        for tx in txs:
            sig = tx["transaction"]["signatures"][0]
            if sig in seen:
                continue
            seen.add(sig)
            rows.append({"program": program, "signature": sig, "slot": tx["slot"],
                         "block_time": tx["blockTime"], "signers": signers(tx),
                         "err": tx["meta"]["err"] is not None})
    return program, rows


def main():
    done = set()
    if os.path.exists(OUT):  # resume: programs already sampled are skipped
        done = {json.loads(line)["program"] for line in open(OUT)}
    programs = [r["address"] for r in csv.DictReader(open("data/seeds/orb_programs.csv")) if r["address"] not in done]
    now = int(time.time())
    total = 0
    with open(OUT, "a") as f, ThreadPoolExecutor(16) as pool:
        for i, (program, rows) in enumerate(pool.map(lambda p: sample(p, now), programs), 1):
            for row in rows:
                f.write(json.dumps(row) + "\n")
            total += len(rows)
            print(f"[{i}/{len(programs)}] {program[:8]} {len(rows)} tx (total {total})", file=sys.stderr)


if __name__ == "__main__":
    main()
