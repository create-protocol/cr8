# Create Protocol — Phase 1 Status

_Auto-generated at 2026-08-23T23:32:47Z. Source: `scripts/build_status.py`._
_Machine-readable: [`status.json`](./status.json)._

## Network

- **Chain:** `arbitrum-sepolia`
- **RPC:** `https://sepolia-rollup.arbitrum.io/rpc`
- **Tip block:** _unset_

## Deployed contracts

| Contract | Address |
|---|---|
| `AgentDeposit` | _unset_ |
| `Cr8UsdMint`   | _unset_ |
| `LucidlyAdapter` | _unset_ |
| `USDC` | _unset_ |

## Registry state

| Metric | Value |
|---|---|
| Registered agents | _unset_ |
| Deposited USDC (smallest unit) | _unset_ |
| Parked syUSD (smallest unit) | _unset_ |
| Last event block | _unset_ |

## Build

- **Status:** `green`

---

_Values shown as `unset` indicate the relevant contract has not been deployed on Arbitrum Sepolia yet. Once a deployment lands, the address goes into the GitHub Action env block (`CR8_AGENT_DEPOSIT_ADDR`, `CR8_CR8USD_MINT_ADDR`, `CR8_LUCIDLY_ADAPTER_ADDR`) and the next run picks it up automatically._

_Update cadence: every 10 minutes via GitHub Action (`.github/workflows/status.yml`). Each refresh commits to `research/depin-benchmark`; history is the trend line._
