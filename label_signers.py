"""Step 2b: build a labelled wallet pool from the signers seen in the program crawl.

Usage: python3 label_signers.py
Reads  data/raw/program_txs.jsonl, data/seeds/orb_programs.csv
Writes data/raw/identity_signers.json      Helius identity for every system-owned signer
       data/interim/pool_labels.json       {address: {"class", "source"}} for wallets with a usable label
       data/interim/pool_wallets.txt       up to PER_CLASS wallets per class, for features.py

Label sources, in order:
  1. Helius identity category (mapped in build_tev.CATEGORY_TO_CLASS)
  2. sole signer of a private bot program Orb labels "Arbitrage or Sandwich Bot" -> trading_bot
     (only the operator can sign for its own private bot program; public routers are excluded)
"""
import collections
import csv
import json
import random

import helius
from build_tev import CATEGORY_TO_CLASS

PER_CLASS = 300
BOT_CATEGORY = "Arbitrage or Sandwich Bot"


def main():
    category = {r["address"]: r["category"] for r in csv.DictReader(open("data/seeds/orb_programs.csv"))}
    signers_of = collections.defaultdict(collections.Counter)
    for line in open("data/raw/program_txs.jsonl"):
        t = json.loads(line)
        for s in t["signers"]:
            signers_of[t["program"]][s] += 1

    everyone = sorted({s for c in signers_of.values() for s in c})
    owner = helius.owners(everyone)
    wallets = [a for a in everyone if owner[a] == helius.SYSTEM_PROGRAM]
    ids = helius.identities(wallets)
    json.dump(ids, open("data/raw/identity_signers.json", "w"), indent=1)

    labels = {}
    for a in wallets:
        cls = CATEGORY_TO_CLASS.get((ids.get(a) or {}).get("category"))
        if cls:
            labels[a] = {"class": cls, "source": f"helius_identity:{ids[a]['category']}"}
    for program, counter in signers_of.items():
        if category.get(program) != BOT_CATEGORY:
            continue
        # A private bot program has one dominant operator; skip programs signed by many wallets.
        top, n = counter.most_common(1)[0]
        if n / sum(counter.values()) >= 0.9 and top in wallets and top not in labels:
            labels[top] = {"class": "trading_bot", "source": f"orb_program_signer:{program}"}
    json.dump(labels, open("data/interim/pool_labels.json", "w"), indent=1)

    by_class = collections.defaultdict(list)
    for a, l in labels.items():
        by_class[l["class"]].append(a)
    rng = random.Random(42)
    pool = []
    for cls, addrs in sorted(by_class.items()):
        rng.shuffle(addrs)
        pool += addrs[:PER_CLASS]
    open("data/interim/pool_wallets.txt", "w").write("\n".join(pool) + "\n")
    print(f"{len(everyone)} signers, {len(wallets)} system-owned, {sum(1 for d in ids.values() if d.get('category'))} with a Helius category")
    print({c: len(v) for c, v in sorted(by_class.items())}, "-> pool", len(pool))


if __name__ == "__main__":
    main()
