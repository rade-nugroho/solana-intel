# solana-intel

On-chain Solana data and labels for training a mass-triage model (Tev1-style decision
model: one wallet in, one triage class out). Started 2026-10-10.

## Pipeline

| Step | Script | Output | Helius cost |
|---|---|---|---|
| 0 | seeds (manual) | `data/seeds/deployers_screenshot.csv` (25 wallets), `data/seeds/orb_programs.csv` (250 programs) | - |
| 1 | `crawl_programs.py` | `data/raw/program_txs.jsonl`: sampled txs of each program (now, -7d, -30d, -90d) with signers | 10 credits / 100 tx |
| 2 | `expand.py <wallets>` | `data/processed/edges.jsonl`: SOL transfers >= 1 SOL to/from seeds; `data/interim/hop1_wallets.txt`; `data/raw/identity_hop1.json` | 10 / page, 100 / 100 identities |
| 3 | `features.py <wallets> <out>` | `data/processed/*_features.jsonl`: behaviour features per wallet | ~130-330 / wallet |
| 4 | `build_tev.py` | `data/tev/records.jsonl`, `data/tev/review_queue.jsonl`, `data/tev/instruction/{train,dev,test}.jsonl` | - |

The Helius key is read from `~/.helius_key` (mode 600) and never written to this repo.

## Provenance

| Data | Source | Notes |
|---|---|---|
| 25 deployer seeds, PnL / deploy counts | screenshot supplied by the owner, addresses re-sent as text | all 25 verified: valid base58, on-chain history; PnL figures are the screenshot's, unverified |
| 250 programs + categories | orbmarkets.io/programs (read in a browser, 2026-10-10) | all 250 names match Helius identity exactly |
| Wallet / program labels | Helius Wallet Identity API (same database as Orb) | third-party claims, stored with fetch date; not ground truth |
| Funding source | Helius `funded-by` (first incoming SOL transfer) | includes the funding signature as evidence |
| Transactions, transfers | Helius `getTransactionsForAddress`, `getTransfersByAddress`, finalized | every row carries its signature so it can be re-fetched |

## Label policy (`build_tev.py`)

* The answer is the Helius identity category mapped to a triage class.
* When behaviour contradicts the label (e.g. "Individual" that mass-deploys Pump.fun tokens),
  the wallet goes to `review_queue.jsonl` instead of training. A human sleuth decides; those
  decisions become the gold labels.
* Wallets with fewer than 5 sampled transactions are labelled `insufficient_evidence` by rule.
* Unlabelled wallets and the "Other" category are never used as negatives.
* Splits are assigned by funder cluster so related wallets never straddle train and test.

## Snapshot 2026-10-10 (about 0.2M Helius credits)

| Artifact | Size |
|---|---|
| Program crawl | 78,321 txs from 249 programs, 20,012 signers (13,963 system-owned, 1,196 with a Helius category) |
| Seed expansion | 17,500 SOL transfers >= 1 SOL; 7,430 counterparties (47 labelled); `shared_sinks.csv`: 264 receivers from >= 2 seeds, of which 233 are program accounts (pools/vaults) and 6 are unlabelled key-held wallets |
| Features | 25 seeds, 166 hop-1 wallets, 640 pool wallets |
| Tev records | 674 (train 548 / dev 76 / test 50); review queue 17 |

Classes are heavily imbalanced (individual and protocol dominate; gambling 1, trading_firm 3,
exchange 13, scam 23, trading_bot 23). Helius "Individual" mostly means "has a Pump.fun profile":
17 of them mass-deploy tokens (review queue), and the remaining `individual` rows may still hide
smaller deployers below the 3-creates-in-100-tx rule.

## Open items

* Helius Terms of Service on using API data for model training / redistribution: not yet checked.
  Do not publish the dataset until this is settled.
* Tev1 fine-tuned weights' licence is "being finalized" (model card); prefer training from
  Qwen3.5 base with the Tev1 recipe.
* Native programs (System, Token, Vote, ...) are rejected by `getTransactionsForAddress`
  ("Address is not supported") and are skipped by the crawl.
