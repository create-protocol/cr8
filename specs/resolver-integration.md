# Resolver Integration Spec

**Status:** Draft 1 · **Closes:** [`create-protocol/cr8#13`](https://github.com/create-protocol/cr8/issues/13)

This spec defines how [`kcolbchain/resolver`](https://github.com/kcolbchain/resolver) plugs into Create Protocol as the execution layer for (a) agent payout settlements that cross venues and (b) CR8-USD mint/redeem hops that benefit from best-execution across UniswapX / Across / CoW.

The point is that Create Protocol does **not** write its own solver. It expresses intents; resolver competes for fills. If resolver returns no fillable quote within budget, we degrade to direct settlement.

---

## 1. Why bother

Two narrow but real cases where best-execution matters:

1. **Agent payout in a non-USDC asset.** An agent earns USDC into `AgentDeposit`, has idle balance auto-parked as syUSD, then wants to take 0.5 ETH home to spend on inference. Two-hop route (syUSD → USDC → ETH) wants tightest price. Resolver finds it; agent pays a single fee, not two AMM slips.
2. **CR8-USD mint from arbitrary stable.** A user wants to mint CR8-USD with USDT or DAI. The mint contract only accepts USDC. Resolver routes USDT → USDC → CR8-USD as one intent; user signs once.

Neither case is fast-path. Neither is performance-critical. Both shave 10–30 bps that compound at volume. That is the whole pitch — no MEV moonshot.

---

## 2. Intent schemas

The intent shapes below sit on top of resolver's existing intent envelope; we add two `kind` values: `CR8_PAYOUT` and `CR8_MINT`.

### 2.1 `CR8_PAYOUT`

```jsonc
{
  "kind": "CR8_PAYOUT",
  "version": 1,
  "agent_id": 17,
  "from": "0xAgentAddr...",
  "input": {
    "currency": "SyUsd",
    "max_amount_smallest": "1175000000000000000"   // up to 1.175 syUSD
  },
  "output": {
    "currency": "Eth",
    "min_amount_smallest": "498500000000000000"    // require ≥ 0.4985 ETH
  },
  "deadline_block": 198431900,
  "fee_policy": {
    "payer": "caller",           // see §3
    "max_bps": 30
  },
  "signature": "0x..."           // EIP-712 over the canonical hash, signed by AgentDeposit-registered address
}
```

### 2.2 `CR8_MINT`

```jsonc
{
  "kind": "CR8_MINT",
  "version": 1,
  "from": "0xUserAddr...",
  "input": {
    "currency": "Usdt",
    "max_amount_smallest": "100000000"              // up to 100 USDT
  },
  "output": {
    "currency": "Cr8Usd",
    "min_amount_smallest": "99500000000000000000"   // require ≥ 99.5 CR8-USD (18 dp)
  },
  "deadline_block": 198431900,
  "fee_policy": {
    "payer": "caller",
    "max_bps": 30
  },
  "signature": "0x..."
}
```

### 2.3 Currency enum

Initial set:
- `Usdc` (6 dp)
- `Usdt` (6 dp)
- `Dai` (18 dp)
- `SyUsd` (18 dp; Lucidly)
- `Cr8Usd` (18 dp; minted by stablecoin-toolkit)
- `Eth` (18 dp)

Adding a currency is a minor bump. Removing one is a major. Resolver fails an intent with `UNSUPPORTED_CURRENCY` if either side is not in the list.

---

## 3. Fee policy

Who pays the resolver and how it accounts.

| Field value | Meaning |
|---|---|
| `"payer": "caller"` | Resolver fee comes out of the caller's input or output side, capped at `max_bps`. The caller eats the spread. |
| `"payer": "treasury"` | Protocol treasury reimburses the resolver fee at the end of the epoch, capped at `max_bps`. Used for protocol-initiated flows (e.g. system-wide CR8-USD rebalances). |
| `"payer": "split"` | 50/50 between caller and treasury. Reserved for promo periods. Not used in v1. |

Defaults:
- `CR8_PAYOUT` from agent: `caller`. Agent eats the fee. Max 30 bps in v1.
- `CR8_MINT` for user: `caller`. User eats the fee. Max 30 bps in v1.

Treasury-paid intents will be batched per epoch and settled to resolver via a single Merkle-claim contract; the spec for that lives in a future doc and is **out of scope** here.

---

## 4. Sequence diagrams

### 4.1 `CR8_PAYOUT` happy path

```
   ┌────────┐    1. cr8 withdraw --target Eth ...   ┌────────────┐
   │ Agent  │ ────────────────────────────────────► │ arbitrum-cli│
   └────────┘                                       └─────┬──────┘
                                                          │
                                                          │ 2. construct CR8_PAYOUT intent + EIP-712 sign
                                                          │
                                                          ▼
                                                    ┌────────────┐
                                                    │ resolver   │
                                                    └─────┬──────┘
                                                          │ 3. quote across UniswapX / Across / CoW
                                                          │ 4. select best filler
                                                          ▼
                                                    ┌────────────┐
                                                    │ filler     │
                                                    └─────┬──────┘
                                                          │ 5. atomic-fill: pulls syUSD, returns Eth
                                                          │    settles via AgentDeposit.withdraw + DEX
                                                          ▼
                                                    ┌────────────┐
                                                    │ AgentDeposit│
                                                    └────────────┘
       ┌────────┐    6. ETH lands at agent address    ◄
       │ Agent  │                                     │
       └────────┘
```

### 4.2 `CR8_MINT` happy path

```
   ┌──────┐  1. mint CR8-USD from USDT     ┌────────────┐
   │ User │ ──────────────────────────────►│ arbitrum-cli│
   └──────┘                                └─────┬──────┘
                                                 │ 2. construct CR8_MINT intent + sign
                                                 ▼
                                           ┌────────────┐
                                           │ resolver   │
                                           └─────┬──────┘
                                                 │ 3. route: USDT→USDC via UniswapX,
                                                 │            USDC→CR8-USD via mint contract
                                                 ▼
                                           ┌────────────┐
                                           │ stablecoin │
                                           │  toolkit   │
                                           └────────────┘
       ┌──────┐  4. CR8-USD lands at user address ◄
       │ User │
       └──────┘
```

---

## 5. Fallback — no fillable quote

If resolver returns no quote satisfying `min_amount_smallest` within `deadline_block` and `max_bps`, the caller degrades.

| Intent | Fallback |
|---|---|
| `CR8_PAYOUT` (agent → non-USDC) | Call `AgentDeposit.withdraw` directly in USDC; agent does the asset swap externally. |
| `CR8_MINT` (user → CR8-USD via non-USDC) | Reject with `NO_FILLABLE_QUOTE`. User retries by first swapping into USDC themselves, then calling mint directly. |

The fallback path is documented in [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md) verbs that consume intents. Agents that bypass resolver entirely keep working unchanged.

---

## 6. Non-goals (v1)

- **MEV capture splitting.** Resolver may earn MEV on the fills it executes. v1 logs realized PnL but does not split. Splitting is a future spec.
- **Cross-chain payouts.** v1 stays L2-local (Arbitrum). Cross-chain routing through Across is a v2 extension.
- **Order-flow auctions / RFQ.** Resolver may evolve into one, but the v1 intent set above does not require it.
- **Custom slippage curves per agent.** All slippage is fixed-bps; tiered curves are out of scope.

---

## 7. Failure modes + error codes

Errors returned to the caller (CLI surface). These map onto resolver's existing error taxonomy where possible; new codes added below.

| Code | Meaning | Recommended action |
|---|---|---|
| `NO_FILLABLE_QUOTE` | Resolver could not find a quote ≤ `max_bps` before `deadline_block` | Retry with relaxed `max_bps` or fall back per §5 |
| `UNSUPPORTED_CURRENCY` | `input.currency` or `output.currency` not in §2.3 | Surface to user; do not silently substitute |
| `DEADLINE_EXPIRED` | `deadline_block` passed during resolver round-trip | Caller resigns + resubmits |
| `INTENT_SIGNATURE_INVALID` | EIP-712 signature does not recover to expected signer | Likely caller bug; investigate |
| `AGENT_NOT_OWNED` | `from` address doesn't match registered agent for `agent_id` | Caller signs from wrong wallet; rotate or re-key |
| `FEE_BUDGET_EXCEEDED` | All quotes exceeded `max_bps` cap | Same as `NO_FILLABLE_QUOTE` |
| `FILLER_REVERTED` | Selected filler's transaction reverted on-chain | Resolver retries with next-best filler automatically (up to 3); only surfaced if all retries fail |

---

## 8. Acceptance checklist

For this spec to be considered live:

- [ ] Resolver implements both intent kinds with the canonical EIP-712 hash defined in `kcolbchain/resolver/specs/intent-hash.md` (tracking issue to open there).
- [ ] At least one filler tests against an Arbitrum Sepolia deployment for each intent kind.
- [ ] arbitrum-cli `cr8 withdraw --target` flag wires through to a `CR8_PAYOUT` intent when the target currency isn't USDC.
- [ ] stablecoin-toolkit mint flow accepts a routed deposit via a `CR8_MINT` intent.
- [ ] Failure-mode codes from §7 are returned consistently from CLI exit envelopes.

---

## 9. References

- [`kcolbchain/resolver`](https://github.com/kcolbchain/resolver) — implementation
- [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md) — CLI verbs that emit / consume these intents
- [`specs/arka-cr8-client.md`](./arka-cr8-client.md) — Rust SDK error mapping
- [`kcolbchain/meridian#19`](https://github.com/kcolbchain/meridian/issues/19) — CR8-USD pool liquidity (upstream)
- [`kcolbchain/stablecoin-toolkit#18`](https://github.com/kcolbchain/stablecoin-toolkit/issues/18) — burn-toll mint/redeem
- EIP-712 typed structured data hashing

— [kcolbchain](https://kcolbchain.com) / [Abhishek Krishna](https://abhishekkrishna.com)
