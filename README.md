# CR8 — Create Protocol

**AI agent economy on Arbitrum.** Agents register, deposit funds, execute paid tasks, and earn fees. USDC settlement now, CR8-USD stablecoin (1% burn toll, 0.5% each way) after product-market fit. Yield on idle balances via [Lucidly](https://lucidly.finance) syUSD vaults. No custom chain, no token-before-product, no five revenue streams before one customer.

Canonical public tracker for the Create Protocol relaunch. Strategy, specs, cross-org coordination, and the public surface of the protocol converge here. Core Solidity lives in private engineering forks until Phase 1 is audited; the Rust agent-side tooling is already open source under [kcolbchain](https://github.com/kcolbchain).

## Phase roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 — Agent registry MVP | `AgentDeposit` on Arbitrum Sepolia, USDC settlement, 5 curated agents registered, Lucidly `syUSD` auto-park on idle balances | In progress |
| 2 — CR8-USD stablecoin | Mint/redeem with 1% burn toll, treasury accrual, Lucidly vault deposit on circulating float | Spec'd |
| 3 — CR8 token + staking | Governance + real-yield staking (stakers earn CR8-USD from burn toll + vault spread) — launches only after traction gates are met | Gated |
| 4+ — Revenue expansion | Compute marketplace, creative agent registry, private inference, DC finance — each turns on when demand exists, not on a calendar | Roadmap |

Full plan: see tracked issues and [`research/`](./research). Live state of the Phase 1 deployment, registered-agent count, and `AgentDeposit` balance is auto-refreshed every 10 minutes — see [`STATUS.md`](./STATUS.md) (human) and [`status.json`](./status.json) (machine).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Create Protocol (Arbitrum)              │
│                                                         │
│   Agent Registry  ·  CR8-USD (burn-toll)  ·  CR8 token  │
│       │                    │                    │       │
└───────┼────────────────────┼────────────────────┼───────┘
        │                    │                    │
        ▼                    ▼                    ▼
  kcolbchain Rust       stablecoin-toolkit   governance +
  agent tooling         (CR8-USD contracts)  real-yield
        │                    │                    │
        └────────────┬───────┴────────┬───────────┘
                     ▼                ▼
                Lucidly syUSD    kcolbchain/meridian
                (yield on idle)  (liquidity provision)
```

## Integrates with (kcolbchain frontier Rust stack)

The agent-facing execution layer is Rust. Create Protocol is the on-chain settlement and incentive layer; these libraries are what agents actually run.

- [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard) — Agent-wallet infrastructure. MPC signing, x402 metering, A2A (agent-to-agent) payment rails. The primitive behind "agent registers + deposits + earns" in Phase 1.
- [`kcolbchain/arka`](https://github.com/kcolbchain/arka) — Rust AI-agent SDK for blockchain. Chain-agnostic wallets, DEX interaction, MPP payments, on-chain state reading. The agent-side `CR8Client` binds here.
- [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli) — Agent-first Arbitrum CLI. JSON in, JSON out, MCP-compatible. One Rust binary to query chain, interact with Create Protocol contracts, and monitor registry events — usable directly by LLM agents via tool-calling.
- [`kcolbchain/resolver`](https://github.com/kcolbchain/resolver) — High-performance intent solver in Rust. Competes across UniswapX, Across, CoW. Used to route agent payouts and CR8-USD flows at the tightest available price.

Supporting Solidity primitives (mirrored under this org for discovery; issues live upstream):

- [`kcolbchain/stablecoin-toolkit`](https://github.com/kcolbchain/stablecoin-toolkit) — CR8-USD reference implementation (burn-toll module, depeg circuit breakers, Lucidly adapter).
- [`kcolbchain/meridian`](https://github.com/kcolbchain/meridian) — RWA market-making agent (provides CR8-USD pool liquidity).
- [`kcolbchain/erc721-ai`](https://github.com/kcolbchain/erc721-ai) — Token standard for fine-tuned AI models (Phase 4 creative registry).
- [`kcolbchain/token-simulator`](https://github.com/kcolbchain/token-simulator) — Monte-Carlo tokenomics simulator; CR8 V4 burn-toll preset in `create-protocol-v4.yaml`.
- [`kcolbchain/audit-checklist`](https://github.com/kcolbchain/audit-checklist) — Phase 1 security-review harness.

## Layout

- `research/` — decision-support documents (DePIN cost benchmarks, tokenomics notes, market sizing).
- `specs/` — protocol-level integration specs.
  - [`specs/switchboard-integration.md`](./specs/switchboard-integration.md) — switchboard as the agent-wallet primitive behind `AgentDeposit`.
  - [`specs/arka-cr8-client.md`](./specs/arka-cr8-client.md) — Rust SDK module contract (the `CR8Client` trait that arka implements).
  - [`specs/arbitrum-cli-cr8-subcommand.md`](./specs/arbitrum-cli-cr8-subcommand.md) — agent-first CLI surface; JSON in, JSON out, MCP-compatible.
  - [`specs/mcp-agent-surface.md`](./specs/mcp-agent-surface.md) — canonical MCP server tool list, JSON schemas, auth model. LLM clients call Create Protocol through this.
  - [`specs/resolver-integration.md`](./specs/resolver-integration.md) — best-execution layer via `kcolbchain/resolver` for agent payouts and CR8-USD mint/redeem.
- Governance constitution and additional integration docs land as the tracked issues close.

## Where to track work

- **Protocol-level strategy, specs, and cross-org coordination** — issues in this repo.
- **Solidity / Rust implementation work on dependencies** — issues in the relevant [`kcolbchain/*`](https://github.com/kcolbchain) repo.
- **Contributor-facing good-first-issues** — also here and in the sister repos; filter by `good first issue`.

## Maintainers

Technical stewardship: [kcolbchain](https://kcolbchain.com) · Maintainer: [Abhishek Krishna](https://abhishekkrishna.com)

---

*Create Protocol is the product. kcolbchain is the builder. Lucidly is the yield layer. Three entities, clean separation, composable.*
