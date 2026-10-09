"""Step 2: one hop out from seed wallets along native SOL flows of >= MIN_SOL.

Usage: python3 expand.py data/interim/seed_wallets.txt
Writes:
  data/processed/edges.jsonl       one row per transfer {seed, direction, counterparty, sol, signature, slot, block_time}
  data/interim/hop1_wallets.txt    counterparties ranked by SOL moved (top TOP_N per seed) plus funders
  data/raw/identity_hop1.json      Helius identity for every counterparty seen
"""
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import helius

SOL = "So11111111111111111111111111111111111111111"
MIN_SOL = 1
PAGES = {"out": 5, "in": 2}
TOP_N = 20


def flows(seed):
    rows = []
    for direction, pages in PAGES.items():
        token = None
        for _ in range(pages):
            data, token = helius.transfers(seed, token=token, direction=direction, mint=SOL,
                                           filters={"amount": {"gte": MIN_SOL * 10**9}})
            for t in data:
                other = t["toUserAccount"] if direction == "out" else t["fromUserAccount"]
                if other and other != seed:
                    rows.append({"seed": seed, "direction": direction, "counterparty": other,
                                 "sol": int(t["amount"]) / 1e9, "signature": t["signature"],
                                 "slot": t["slot"], "block_time": t["blockTime"]})
            if not token or len(data) < 100:
                break
    return rows


def main(src):
    seeds = [w.strip() for w in open(src) if w.strip()]
    edges = [e for rows in ThreadPoolExecutor(8).map(flows, seeds) for e in rows]
    with open("data/processed/edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")

    hop1 = []
    for seed in seeds:
        moved = collections.Counter()
        for e in edges:
            if e["seed"] == seed:
                moved[e["counterparty"]] += e["sol"]
        hop1 += [a for a, _ in moved.most_common(TOP_N)]
    for line in open("data/processed/seed_features.jsonl"):
        funding = json.loads(line)["funding"]
        if funding and funding["funder"]:
            hop1.append(funding["funder"])
    hop1 = [a for a in dict.fromkeys(hop1) if a not in seeds]
    # Only key-held wallets: pools, vaults and authorities are program-owned and say nothing about the operator.
    owner = helius.owners(hop1)
    hop1 = [a for a in hop1 if owner[a] == helius.SYSTEM_PROGRAM]
    open("data/interim/hop1_wallets.txt", "w").write("\n".join(hop1) + "\n")

    everyone = sorted({e["counterparty"] for e in edges} | set(hop1))
    ids = helius.identities(everyone)
    json.dump(ids, open("data/raw/identity_hop1.json", "w"), indent=1)
    print(f"{len(edges)} edges, {len(everyone)} counterparties ({len(ids)} labelled), {len(hop1)} hop-1 wallets")


if __name__ == "__main__":
    main(sys.argv[1])
