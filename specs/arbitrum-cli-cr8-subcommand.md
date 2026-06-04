# `arbitrum-cli cr8` Subcommand — Agent-First MCP Surface

**Status:** Draft 1 · **Closes:** [`create-protocol/cr8#12`](https://github.com/create-protocol/cr8/issues/12)

This spec defines the `cr8` subcommand group that [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli) ships as the agent-first CLI for Create Protocol. JSON in, JSON out. Idempotent where possible. No interactive prompts. Every verb maps 1:1 to a method on the [`CR8Client`](./arka-cr8-client.md) trait, so an LLM agent that knows the CLI knows the SDK.

This is the **lowest-friction integration path** for any LLM that can invoke a shell command. We treat MCP compatibility as a hard gate, not a nice-to-have.

---

## 1. Verb table

| Verb | Maps to | Mutates chain | Idempotent |
|---|---|---|---|
| `arbitrum-cli cr8 register` | `CR8Client::register` | yes | no — registering an already-registered address returns its id with exit 0 |
| `arbitrum-cli cr8 deposit` | `CR8Client::deposit` | yes | no — each call moves funds |
| `arbitrum-cli cr8 withdraw` | `CR8Client::withdraw` | yes | no |
| `arbitrum-cli cr8 tasks list` | reads `RegistryEvent` history + off-chain task index | no | yes |
| `arbitrum-cli cr8 claim` | `CR8Client::claim_task` | no (off-chain handle) | yes — repeated claims by same agent are no-ops |
| `arbitrum-cli cr8 complete` | `CR8Client::complete_task` | yes | yes via `(agentId, nonce)` replay protection |
| `arbitrum-cli cr8 balance` | `CR8Client::balance` | no | yes |
| `arbitrum-cli cr8 watch` | `CR8Client::watch` | no | yes (long-running) |
| `arbitrum-cli cr8 profile` | `CR8Client::profile` | no | yes |

Verbs that do not appear here are out of scope (e.g., no `cr8 slash`, no `cr8 dispute` — see [`specs/switchboard-integration.md`](./switchboard-integration.md) §6.4).

---

## 2. Common conventions

- **Global flags** (inherited from `arbitrum-cli`):
  - `--rpc <url>` (default: env `ARB_RPC_URL`)
  - `--wallet <switchboard-wallet-id>` (default: env `SWITCHBOARD_WALLET`)
  - `--network <name>` (default `arbitrum-sepolia`; `arbitrum` for mainnet)
  - `--json` (default true for `cr8` subcommands — see §3.1)
  - `--quiet` (suppress non-essential stderr)
  - `--timeout <seconds>` (default 60)

- **Exit codes** (consistent with `arbitrum-cli` parent):
  - `0` — success
  - `1` — usage error
  - `2` — chain-level failure (revert, not-confirmed, RPC down)
  - `3` — switchboard failure (wallet unreachable, signing rejected)
  - `4` — protocol-level rejection (replay, not authorized, insufficient balance)
  - `>=10` — internal error

- **No interactive prompts.** Every required input is either a flag, an env var, or a value piped to stdin. If anything is missing, exit `1` with a structured error.

- **Structured stderr.** Human-readable messages go to stderr; only the result JSON goes to stdout.

---

## 3. Output schemas

### 3.1 Default: JSON-only stdout

All `cr8` verbs emit a single JSON document to stdout — never partial, never streaming, except for `cr8 watch` which emits newline-delimited JSON (NDJSON).

```jsonc
// success envelope
{
  "ok": true,
  "verb": "register",
  "data": { /* verb-specific payload */ }
}

// failure envelope
{
  "ok": false,
  "verb": "register",
  "error": {
    "code": "AlreadyRegistered",
    "message": "agent 17 already registered",
    "details": { "agent_id": 17, "address": "0xAgent..." }
  }
}
```

The `code` enum matches the [`CR8Error`](./arka-cr8-client.md#3-error-taxonomy) variants 1:1. LLM tool callers match on `code`, not message text.

### 3.2 Structured errors are mandatory

A failure that does not produce the failure envelope is a CLI bug. There are no "raw stack trace" exits to stdout. The only place a raw error appears is stderr, when `--quiet` is not set.

---

## 4. Verb specifications

### 4.1 `cr8 register`

```
arbitrum-cli cr8 register \
  --address 0xAgent... \              # MPC wallet address from switchboard
  --profile <file.json | -> \         # AgentProfile JSON (see below)
```

Profile JSON:
```json
{
  "display_name": "summariser-001",
  "capability_tags": ["llm:text", "rag:summarise"],
  "endpoint_url": "https://agent.example/api/task",
  "a2a_pricing": {
    "currency": "Usdc",
    "rate_per_unit": 100,
    "pricing_unit": "PerToken"
  }
}
```

Success `data`:
```json
{ "agent_id": 17, "tx_hash": "0x...", "profile_uri": "ipfs://Qm..." }
```

The CLI pins the profile JSON to IPFS via the configured pinning endpoint (`--ipfs-api`, default `env IPFS_API`) and submits the resulting `bytes32` CID to `AgentDeposit.register`.

### 4.2 `cr8 deposit`

```
arbitrum-cli cr8 deposit \
  --agent <id> \
  --amount <usdc-decimal>             # e.g. 5.0 = 5 USDC; converted to 6-decimal smallest unit
```

Success `data`:
```json
{ "agent_id": 17, "amount_usdc_smallest": 5000000, "tx_hash": "0x..." }
```

If USDC allowance is insufficient, the CLI emits a `InsufficientAllowance` error envelope and exits `4`. The CLI does **not** auto-approve; that is a separate verb (`arbitrum-cli erc20 approve ...`) by design.

### 4.3 `cr8 withdraw`

```
arbitrum-cli cr8 withdraw \
  --agent <id> \
  --amount <usdc-decimal>
```

Success `data`:
```json
{ "agent_id": 17, "amount_usdc_smallest": 1000000, "tx_hash": "0x..." }
```

### 4.4 `cr8 tasks list`

```
arbitrum-cli cr8 tasks list \
  --agent <id> \                      # optional; default lists all visible to the wallet
  --status <open|claimed|done|all> \  # default: all
  --since <iso8601> \                 # default: last 7 days
  --limit <int>                       # default: 50, max 500
```

Success `data`:
```json
{
  "tasks": [
    {
      "task_id": "t-abc",
      "agent_id": 17,
      "status": "claimed",
      "claimed_at_block": 198431201,
      "max_payout_usdc_smallest": 250000,
      "issuer_endpoint": "https://issuer.example"
    }
  ],
  "cursor": null
}
```

The CLI joins the on-chain `RegistryEvent` history with the configured issuer-side index (`--issuer-url`, default `env CR8_ISSUER_URL`). Tasks not yet known to the issuer index do not appear.

### 4.5 `cr8 claim`

```
arbitrum-cli cr8 claim <task_id> \
  --agent <id>
```

Success `data`:
```json
{
  "task_id": "t-abc",
  "agent_id": 17,
  "nonce": 42,
  "max_payout_usdc_smallest": 250000,
  "expires_at_block": 198431500,
  "handle_file": "/tmp/cr8-handle-t-abc.json"
}
```

`handle_file` is a local artifact the agent **must** retain across crashes; `cr8 complete` reads it to recover the nonce. On a clean handle pickup, `cr8 claim` of the same `(agent, task_id)` exits `0` and returns the existing handle.

### 4.6 `cr8 complete`

```
arbitrum-cli cr8 complete <task_id> \
  --agent <id> \
  --receipt <file.json | ->           # TaskReceipt JSON
```

Receipt JSON:
```json
{
  "task_id": "t-abc",
  "work_proof": "<base64 bytes>",
  "x402_session": "t-abc"
}
```

Success `data`:
```json
{
  "task_id": "t-abc",
  "agent_id": 17,
  "paid_usdc_smallest": 175000,
  "tx_hash": "0x...",
  "receipt_hash": "0xabcd..."
}
```

Replay (`(agentId, nonce)` already settled) returns exit `4` with `code: "NonceReplay"`. The original `Payout` is fetched by `receipt_hash` from event history and surfaced under `data.replayed_payout` for the LLM to reason about.

### 4.7 `cr8 balance`

```
arbitrum-cli cr8 balance \
  --agent <id>
```

Success `data`:
```json
{
  "agent_id": 17,
  "idle_usdc_smallest": 3825000,
  "parked_syusd_smallest": "1175000000000000000",
  "pending_payouts_usdc_smallest": 0
}
```

`parked_syusd_smallest` is a string because syUSD is 18-decimal and exceeds JSON-safe integer range on some runtimes.

### 4.8 `cr8 watch`

```
arbitrum-cli cr8 watch \
  --agent <id> \                      # optional; omit to stream all
  --from-block <int> \                # default: latest
  --event <type1,type2>               # filter, default: all
```

Output is NDJSON to stdout. One event per line, schema matches `RegistryEvent` from the [`CR8Client`](./arka-cr8-client.md#2-trait-surface) spec:

```ndjson
{"type":"TaskSettled","agent_id":17,"amount_usdc_smallest":175000,"nonce":42,"receipt_hash":"0xabcd...","block":198431320}
{"type":"Deposited","agent_id":17,"amount_usdc_smallest":5000000,"from":"0xUser...","block":198431301}
```

Long-running. Re-emits on RPC reconnect with no duplicates per `(tx_hash, log_index)`.

### 4.9 `cr8 profile`

```
arbitrum-cli cr8 profile \
  --agent <id>
```

Success `data`:
```json
{
  "agent_id": 17,
  "address": "0xAgent...",
  "profile_uri": "ipfs://Qm...",
  "profile": { /* dereferenced AgentProfile JSON, identical to register-input shape */ }
}
```

If `profile_uri` cannot be fetched, returns the URI alone (no `profile` field) — the verb does not fail for unreachable IPFS.

---

## 5. Worked example: LLM agent completing a task via CLI only

Below is a transcript of an LLM agent doing one full register → deposit → claim → complete cycle using only `arbitrum-cli cr8` tool calls. No SDK. No bespoke contract code.

```text
LLM tool call:   arbitrum-cli cr8 register
                   --address 0xAgent...
                   --profile -
                 stdin: { "display_name": "summariser-001", ... }
LLM result:      { "ok": true, "verb": "register",
                   "data": { "agent_id": 17, "tx_hash": "0x...",
                             "profile_uri": "ipfs://Qm..." } }

LLM tool call:   arbitrum-cli erc20 approve
                   --token USDC --spender $AGENT_DEPOSIT --amount 5
LLM result:      { "ok": true, "data": { "tx_hash": "0x..." } }

LLM tool call:   arbitrum-cli cr8 deposit --agent 17 --amount 5
LLM result:      { "ok": true, "data": { "amount_usdc_smallest": 5000000, ... } }

LLM tool call:   arbitrum-cli cr8 tasks list --agent 17 --status open
LLM result:      { "ok": true, "data": { "tasks": [ { "task_id": "t-abc", ... } ] } }

LLM tool call:   arbitrum-cli cr8 claim t-abc --agent 17
LLM result:      { "ok": true, "data": { "nonce": 42, "handle_file": "..." } }

# LLM does the actual work here — runs inference, produces summary, captures proof.

LLM tool call:   arbitrum-cli cr8 complete t-abc --agent 17 --receipt -
                 stdin: { "task_id": "t-abc", "work_proof": "...", "x402_session": "t-abc" }
LLM result:      { "ok": true, "data": { "paid_usdc_smallest": 175000, "tx_hash": "0x..." } }

LLM tool call:   arbitrum-cli cr8 balance --agent 17
LLM result:      { "ok": true, "data": { "idle_usdc_smallest": 4825000, ... } }
```

This transcript is enough for an LLM with a generic tool-call surface to operate as an agent on Create Protocol from a cold start.

---

## 6. MCP compatibility checklist

Per [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli)'s MCP gate, every `cr8` verb satisfies:

| # | Requirement | Status |
|---|---|---|
| 1 | All inputs accepted via flags or stdin | yes |
| 2 | No TTY-only behaviour (no spinners, no prompts) | yes |
| 3 | Structured success/failure JSON envelope | yes |
| 4 | Error `code` is a stable enum, not free text | yes — matches `CR8Error` |
| 5 | Long-running operations stream NDJSON, not nested JSON | yes — `cr8 watch` only |
| 6 | Idempotency labelled in this spec | yes — §1 table |
| 7 | Exit code reflects category, not just success/fail | yes — §2 |
| 8 | No verb depends on global state outside flags / env | yes |

Any future verb added to `cr8` MUST pass this checklist before merge.

---

## 7. Companion tracking

After this spec merges:

- Open [`kcolbchain/arbitrum-cli#?`](https://github.com/kcolbchain/arbitrum-cli) titled
  *"Implement `cr8` subcommand per [`create-protocol/cr8/specs/arbitrum-cli-cr8-subcommand.md`](https://github.com/create-protocol/cr8/blob/main/specs/arbitrum-cli-cr8-subcommand.md)"*
  with a commit-pinned URL.

---

## 8. References

- [`create-protocol/cr8/specs/arka-cr8-client.md`](./arka-cr8-client.md) — Rust SDK shape these verbs reflect
- [`create-protocol/cr8/specs/switchboard-integration.md`](./switchboard-integration.md) — wallet primitive + on-chain contract behaviour
- [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli)
- [`kcolbchain/arka`](https://github.com/kcolbchain/arka)
- [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard)

— [kcolbchain](https://kcolbchain.com) / [Abhishek Krishna](https://abhishekkrishna.com)
