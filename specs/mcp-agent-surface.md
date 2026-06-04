# MCP Agent Surface — Standard Tool Schema for LLM-Driven Create Protocol Agents

**Status:** Draft 1 · **Closes:** [`create-protocol/cr8#15`](https://github.com/create-protocol/cr8/issues/15)

This spec defines the **canonical Model Context Protocol (MCP) server** for Create Protocol. After this lands, any LLM client that speaks MCP — Claude Code, Claude Desktop, Cursor, Continue, custom orchestrators — can discover Create Protocol's verbs by name, with typed schemas, without a bespoke adapter. The server is a thin shim over [`arbitrum-cli cr8`](./arbitrum-cli-cr8-subcommand.md); the CLI is the implementation, the MCP server is the shape LLMs see.

The goal is not to invent a new agent surface. It is to make sure the same verbs that an agent calls via shell also work via MCP, with identical semantics, error codes, and JSON shapes.

---

## 1. Scope

In scope:
- Public MCP tool list (names, JSON schemas, arg validation rules).
- Auth model — switchboard wallet signing per request.
- Rate limits + abuse policy for the hosted instance.
- One reference agent transcript (register → deposit → claim → complete) using only MCP calls.

Out of scope:
- The CLI verbs themselves — those live in [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md).
- The Rust SDK — that lives in [`specs/arka-cr8-client.md`](./arka-cr8-client.md).
- Discovery of Create Protocol from the MCP registry — handled at the registry level, not by this server.

---

## 2. Tool list

Each tool maps 1:1 to a CLI verb (third column). Tool names are namespaced `cr8.*` so they coexist with other servers in a client. All inputs/outputs are JSON; error envelope matches the CLI spec §3.

| Tool | Effect | CLI verb |
|---|---|---|
| `cr8.register` | Register an agent address with a profile | `arbitrum-cli cr8 register` |
| `cr8.deposit` | Deposit USDC into an agent's registry balance | `arbitrum-cli cr8 deposit` |
| `cr8.withdraw` | Withdraw USDC from an agent's registry balance | `arbitrum-cli cr8 withdraw` |
| `cr8.balance` | Read agent balance (idle USDC + parked syUSD + pending) | `arbitrum-cli cr8 balance` |
| `cr8.profile` | Read agent profile (address + dereferenced AgentProfile) | `arbitrum-cli cr8 profile` |
| `cr8.tasks_list` | List tasks visible to the agent (filterable) | `arbitrum-cli cr8 tasks list` |
| `cr8.claim_task` | Reserve a task + open the x402 meter session | `arbitrum-cli cr8 claim` |
| `cr8.complete_task` | Submit settlement and release the payout | `arbitrum-cli cr8 complete` |
| `cr8.watch_events` | Server-streamed registry events (NDJSON via MCP streaming) | `arbitrum-cli cr8 watch` |

Anything not on this list is unsupported. The list grows by minor-version bumps; tool removal is a major.

---

## 3. JSON schemas

### 3.1 `cr8.register`

```json
{
  "name": "cr8.register",
  "description": "Register an agent address on the Create Protocol registry. Idempotent: re-registering an already-registered address returns its existing id.",
  "inputSchema": {
    "type": "object",
    "required": ["address", "profile"],
    "properties": {
      "address": { "type": "string", "pattern": "^0x[a-fA-F0-9]{40}$" },
      "profile": {
        "type": "object",
        "required": ["display_name", "capability_tags", "endpoint_url", "a2a_pricing"],
        "properties": {
          "display_name": { "type": "string", "minLength": 1, "maxLength": 64 },
          "capability_tags": {
            "type": "array",
            "items": { "type": "string", "pattern": "^[a-z][a-z0-9_:.-]*$" },
            "maxItems": 32
          },
          "endpoint_url": { "type": "string", "format": "uri" },
          "a2a_pricing": {
            "type": "object",
            "required": ["currency", "rate_per_unit", "pricing_unit"],
            "properties": {
              "currency": { "enum": ["Usdc", "SyUsd"] },
              "rate_per_unit": { "type": "integer", "minimum": 0 },
              "pricing_unit": { "enum": ["PerCall", "PerToken", "PerSecond"] }
            }
          }
        }
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["agent_id", "tx_hash", "profile_uri"],
    "properties": {
      "agent_id": { "type": "integer", "minimum": 1 },
      "tx_hash": { "type": "string" },
      "profile_uri": { "type": "string", "pattern": "^ipfs://" }
    }
  }
}
```

### 3.2 `cr8.deposit`

```json
{
  "name": "cr8.deposit",
  "description": "Deposit USDC into an agent's balance. Requires prior ERC-20 approval to the AgentDeposit contract.",
  "inputSchema": {
    "type": "object",
    "required": ["agent_id", "amount_usdc"],
    "properties": {
      "agent_id": { "type": "integer", "minimum": 1 },
      "amount_usdc": { "type": "number", "exclusiveMinimum": 0 }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["agent_id", "amount_usdc_smallest", "tx_hash"],
    "properties": {
      "agent_id": { "type": "integer" },
      "amount_usdc_smallest": { "type": "integer" },
      "tx_hash": { "type": "string" }
    }
  }
}
```

### 3.3 `cr8.withdraw`

Same shape as `cr8.deposit`. Caller must be the agent's currently-registered address.

### 3.4 `cr8.balance`

```json
{
  "name": "cr8.balance",
  "description": "Read an agent's balance breakdown — idle USDC, parked syUSD, pending payouts.",
  "inputSchema": {
    "type": "object",
    "required": ["agent_id"],
    "properties": { "agent_id": { "type": "integer", "minimum": 1 } }
  },
  "outputSchema": {
    "type": "object",
    "required": ["agent_id", "idle_usdc_smallest", "parked_syusd_smallest", "pending_payouts_usdc_smallest"],
    "properties": {
      "agent_id": { "type": "integer" },
      "idle_usdc_smallest": { "type": "integer" },
      "parked_syusd_smallest": { "type": "string", "pattern": "^[0-9]+$" },
      "pending_payouts_usdc_smallest": { "type": "integer" }
    }
  }
}
```

`parked_syusd_smallest` is a string because 18-decimal syUSD exceeds JSON-safe integer range on some runtimes.

### 3.5 `cr8.profile`

```json
{
  "name": "cr8.profile",
  "description": "Read an agent's on-chain registration and dereferenced AgentProfile.",
  "inputSchema": {
    "type": "object",
    "required": ["agent_id"],
    "properties": { "agent_id": { "type": "integer", "minimum": 1 } }
  },
  "outputSchema": {
    "type": "object",
    "required": ["agent_id", "address", "profile_uri"],
    "properties": {
      "agent_id": { "type": "integer" },
      "address": { "type": "string" },
      "profile_uri": { "type": "string" },
      "profile": { "type": "object" }
    }
  }
}
```

`profile` is omitted if IPFS dereference fails; the call still returns success.

### 3.6 `cr8.tasks_list`

```json
{
  "name": "cr8.tasks_list",
  "description": "List tasks visible to an agent. Joins on-chain registry events with the configured issuer index.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id":   { "type": "integer", "minimum": 1 },
      "status":     { "enum": ["open", "claimed", "done", "all"], "default": "all" },
      "since":      { "type": "string", "format": "date-time" },
      "limit":      { "type": "integer", "minimum": 1, "maximum": 500, "default": 50 }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["tasks"],
    "properties": {
      "tasks":  { "type": "array", "items": { "type": "object" } },
      "cursor": { "type": ["string", "null"] }
    }
  }
}
```

### 3.7 `cr8.claim_task`

```json
{
  "name": "cr8.claim_task",
  "description": "Reserve a task and open the x402 meter session. Off-chain only. Idempotent for the same (agent, task) pair.",
  "inputSchema": {
    "type": "object",
    "required": ["agent_id", "task_id"],
    "properties": {
      "agent_id": { "type": "integer", "minimum": 1 },
      "task_id":  { "type": "string", "minLength": 1 }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["task_id", "agent_id", "nonce", "max_payout_usdc_smallest", "expires_at_block"],
    "properties": {
      "task_id":                  { "type": "string" },
      "agent_id":                 { "type": "integer" },
      "nonce":                    { "type": "integer" },
      "max_payout_usdc_smallest": { "type": "integer" },
      "expires_at_block":         { "type": "integer" }
    }
  }
}
```

The MCP server holds the task-handle locally (the CLI's `handle_file`). Clients do not need to round-trip it; the server keys recovery off `(agent_id, task_id)`.

### 3.8 `cr8.complete_task`

```json
{
  "name": "cr8.complete_task",
  "description": "Submit task receipt and release the payout. Settles AgentDeposit.settle(id, amount, receipt, sig).",
  "inputSchema": {
    "type": "object",
    "required": ["agent_id", "task_id", "receipt"],
    "properties": {
      "agent_id": { "type": "integer", "minimum": 1 },
      "task_id":  { "type": "string" },
      "receipt": {
        "type": "object",
        "required": ["task_id", "work_proof", "x402_session"],
        "properties": {
          "task_id":      { "type": "string" },
          "work_proof":   { "type": "string", "contentEncoding": "base64" },
          "x402_session": { "type": "string" }
        }
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["task_id", "agent_id", "paid_usdc_smallest", "tx_hash", "receipt_hash"],
    "properties": {
      "task_id":            { "type": "string" },
      "agent_id":           { "type": "integer" },
      "paid_usdc_smallest": { "type": "integer" },
      "tx_hash":            { "type": "string" },
      "receipt_hash":       { "type": "string" }
    }
  }
}
```

### 3.9 `cr8.watch_events`

Streamed via the MCP server's streaming-response channel. Each event is one JSON document; the channel stays open until the client disconnects.

```json
{
  "name": "cr8.watch_events",
  "description": "Subscribe to registry events. Streams JSON documents on the MCP streaming channel.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id":   { "type": "integer", "minimum": 1 },
      "from_block": { "type": "integer", "minimum": 0 },
      "event":      { "type": "array", "items": { "enum": ["AgentRegistered", "AgentRotated", "Deposited", "Withdrawn", "TaskSettled"] } }
    }
  },
  "outputSchema": {
    "type": "object",
    "description": "Per-event document. Matches RegistryEvent shape from arka-cr8-client spec §2.",
    "properties": {
      "type":   { "enum": ["AgentRegistered", "AgentRotated", "Deposited", "Withdrawn", "TaskSettled"] },
      "block":  { "type": "integer" }
    }
  }
}
```

---

## 4. Auth model

### 4.1 Sequence

```
   ┌────────────┐    1. tool call: cr8.deposit(...)     ┌────────────┐
   │ LLM client │ ────────────────────────────────────► │ MCP server │
   └────────────┘                                       └─────┬──────┘
                                                              │
                                                              │ 2. server constructs canonical tx payload
                                                              │    (eip-712 typed-data, includes nonce + agent_id)
                                                              │
   ┌────────────┐    3. sign request via switchboard          │
   │switchboard │ ◄────────────────────────────────────────── │
   │ MPC quorum │                                             │
   │  (off-box) │ ────────────────────────────────────────►   │ 4. signed payload returned
   └────────────┘                                             │
                                                              │
                                                              │ 5. server submits tx, waits N confirmations
                                                              │
   ┌────────────┐    6. tool result: { agent_id, tx_hash }    │
   │ LLM client │ ◄──────────────────────────────────────────│
   └────────────┘
```

### 4.2 Auth rules

1. **Wallet binding.** The MCP server is configured with a single switchboard wallet handle at startup. All chain-touching tool calls sign with that wallet. The LLM client cannot supply a private key, ever.
2. **Agent ownership check.** For `cr8.withdraw`, `cr8.complete_task`, `cr8.rotate`, the server verifies the configured wallet is the currently-registered address for the supplied `agent_id` before proceeding. Mismatch returns `NotAuthorized`.
3. **No client-supplied transaction data.** The LLM client never sends raw calldata. It sends only the JSON args in §3 schemas. The server constructs the tx.
4. **No private-key paths.** If a tool call would require a private key the wallet doesn't have (e.g. a non-switchboard EOA), the server returns `WalletUnavailable`.

### 4.3 Why this matters

LLMs make mistakes. A naively-implemented MCP server that accepted "send X USDC to address Y" risks the LLM hallucinating an address. The pattern above guarantees:

- The LLM can express **intent** (deposit 5 USDC into agent 17) but never **calldata**.
- The wallet's recovery / rotation / quorum is fully off-band.
- Every chain-touching call has a server-side authorization check before the wallet signs.

---

## 5. Rate limits + abuse policy (hosted instance)

The reference hosted instance lives at `mcp.kcolbchain.com/cr8` (forthcoming). Self-hosters can configure these arbitrarily.

| Resource | Default limit | Burst |
|---|---|---|
| Read tools (`balance`, `profile`, `tasks_list`) | 60 / min per wallet | 30 |
| Write tools (`register`, `deposit`, `withdraw`, `claim_task`, `complete_task`) | 12 / min per wallet | 6 |
| `watch_events` streams | 4 concurrent streams per wallet | n/a |
| RPC bandwidth | 5 MB / min per wallet | 2 MB |

Throttled requests return MCP error `RateLimited` with a `retry_after_seconds` field. The hosted instance reserves the right to block wallets exhibiting:

- Repeated invalid signatures.
- High-rate `cr8.register` with the same address (registration spam).
- Anomalous `cr8.tasks_list` polling that suggests using the MCP server as a backend index (use the on-chain event stream + issuer index instead).

---

## 6. Reference transcript — register → deposit → claim → complete via MCP

```
MCP call:        cr8.register(
                   address="0xAgent...",
                   profile={ display_name: "summariser-001",
                             capability_tags: ["llm:text", "rag:summarise"],
                             endpoint_url: "https://agent.example/api/task",
                             a2a_pricing: { currency: "Usdc",
                                            rate_per_unit: 100,
                                            pricing_unit: "PerToken" } })
MCP result:      { agent_id: 17, tx_hash: "0x...", profile_uri: "ipfs://Qm..." }

MCP call:        cr8.deposit(agent_id=17, amount_usdc=5)
MCP result:      { agent_id: 17, amount_usdc_smallest: 5000000, tx_hash: "0x..." }
                 (server has already issued the ERC-20 approval out-of-band)

MCP call:        cr8.tasks_list(agent_id=17, status="open")
MCP result:      { tasks: [{ task_id: "t-abc", max_payout_usdc_smallest: 250000, ... }] }

MCP call:        cr8.claim_task(agent_id=17, task_id="t-abc")
MCP result:      { task_id: "t-abc", agent_id: 17, nonce: 42,
                   max_payout_usdc_smallest: 250000, expires_at_block: 198431500 }

# LLM does the work — runs inference, produces summary, captures proof.

MCP call:        cr8.complete_task(
                   agent_id=17, task_id="t-abc",
                   receipt={ task_id: "t-abc",
                             work_proof: "<base64>",
                             x402_session: "t-abc" })
MCP result:      { paid_usdc_smallest: 175000, tx_hash: "0x...", receipt_hash: "0xabcd..." }

MCP call:        cr8.balance(agent_id=17)
MCP result:      { agent_id: 17, idle_usdc_smallest: 4825000,
                   parked_syusd_smallest: "0", pending_payouts_usdc_smallest: 0 }
```

This transcript is enough for any MCP-speaking LLM client to operate as a Create Protocol agent from cold start, given:
- An MCP server pointed at a switchboard wallet.
- Prior ERC-20 USDC approval to the `AgentDeposit` contract (typically done once at server provisioning).

---

## 7. Versioning

| Change | Bump |
|---|---|
| Adding a new tool | minor |
| Adding an optional field to an existing input schema | minor |
| Adding a new field to an output schema | minor |
| Tightening input validation (rejecting previously-accepted inputs) | major |
| Removing a tool, removing an output field | major |
| Renaming any tool, field, or enum value | major |
| Changing auth model | major |

Servers advertise their MCP-spec version via the standard `serverInfo` field on the MCP handshake.

---

## 8. References

- [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md) — underlying CLI verbs
- [`specs/arka-cr8-client.md`](./arka-cr8-client.md) — Rust SDK shape (`CR8Error` codes match here)
- [`specs/switchboard-integration.md`](./switchboard-integration.md) — wallet primitive + on-chain behaviour
- [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli) — implementation
- Model Context Protocol — https://modelcontextprotocol.io

— [kcolbchain](https://kcolbchain.com) / [Abhishek Krishna](https://abhishekkrishna.com)
