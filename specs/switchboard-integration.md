# Switchboard Integration Spec

**Status:** Draft 1 · **Closes:** [`create-protocol/cr8#10`](https://github.com/create-protocol/cr8/issues/10)

This spec defines how the Create Protocol registry consumes [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard) as the canonical agent-wallet primitive. After this lands, an agent that registers on CR8 is, by construction, an agent with a switchboard MPC wallet, an A2A payment endpoint, and an x402 meter — there is no second wallet stack.

The spec is normative for Phase 1 (Arbitrum Sepolia, USDC settlement). Phase 2+ extensions are called out where relevant but not specified here.

---

## 1. Why this exists

Two failure modes the registry must avoid:

1. **Wallet duplication.** Agents end up with one wallet to satisfy `AgentDeposit.register` and a different wallet for actually running. This breaks A2A pricing (counterparty identity diverges from settlement identity) and breaks key rotation (two recovery paths, neither complete).
2. **Tight coupling at the contract level.** If `AgentDeposit` imports switchboard types, every switchboard release becomes an L2 redeploy. The registry must treat switchboard wallets as *plain Ethereum addresses* and read state through events, not interface calls.

The integration is therefore **off-chain at provisioning time, address-only on-chain.** The registry holds an address; switchboard owns the keys behind it.

---

## 2. Sequence: agent sign-up → first paid task

```
   ┌────────┐    ┌───────────────┐    ┌────────────────┐    ┌────────────────┐
   │ Human  │    │ switchboard   │    │ AgentDeposit   │    │ Task issuer    │
   │ / dev  │    │  (kcolbchain) │    │  (cr8 on L2)   │    │  (off-chain)   │
   └───┬────┘    └───────┬───────┘    └────────┬───────┘    └────────┬───────┘
       │ 1. provision    │                     │                     │
       │ MPC wallet      │                     │                     │
       │────────────────►│                     │                     │
       │                 │  2. derive addr A   │                     │
       │◄────────────────│  + recovery quorum  │                     │
       │                 │                     │                     │
       │ 3. register(A, profile_uri)           │                     │
       │──────────────────────────────────────►│                     │
       │                 │                     │ emits AgentRegistered(A, id)
       │◄──────────────────────────────────────│                     │
       │                 │                     │                     │
       │ 4. fund A with USDC, deposit          │                     │
       │──────────────────────────────────────►│                     │
       │                 │                     │ emits Deposited(id, amt)
       │                 │                     │                     │
       │                 │                     │                     │
       │ 5. task posted (off-chain)            │                     │
       │ ◄─────────────────────────────────────────────────────────  │
       │ 6. agent claims (A signs via switchboard MPC quorum)        │
       │   ┌──────────────────────────────────────────────────────►  │
       │   │             │                     │                     │
       │   │ 7. x402 meter starts; agent does work                   │
       │   │             │                     │                     │
       │   │             │ 8. settlement payload (x402 receipt)      │
       │   │             │ ◄────────────────────────────────────────│
       │   │             │ 9. settle(id, receipt) → USDC to A        │
       │   │             │────────────────────►│                     │
       │   │             │                     │ emits TaskSettled
```

Step numbers are referenced by the contract / SDK behaviour requirements in §5.

---

## 3. What lives where

| Concern | Owner | Surface |
|---|---|---|
| MPC key generation, threshold quorum, signing | switchboard | Rust / Python clients (`kcolbchain/switchboard`) — off-chain |
| Recovery / key rotation policy | switchboard | Off-chain MPC committee; on-chain artifact is a single address swap (see §6) |
| A2A payment metering (x402) | switchboard | Off-chain HTTP/402 envelope; the cr8 registry sees only the settled receipt |
| Agent identity (canonical id) | cr8 | `AgentDeposit` mapping `address → AgentId` |
| Deposit balance, payouts, slashing | cr8 | `AgentDeposit` storage, ERC-20 USDC transfers |
| Reputation / task-history | cr8 | Read-only from `TaskSettled` events; no contract API |
| Lucidly syUSD auto-park | cr8 (idle balance) + Lucidly (vault) | `AgentDeposit` adapter hook; out of scope for this spec |
| LLM tool-call surface | `kcolbchain/arbitrum-cli` `cr8` subcommand | Spec'd separately in [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md) |
| Rust agent SDK | `kcolbchain/arka` `CR8Client` | Spec'd separately in [`specs/arka-cr8-client.md`](./arka-cr8-client.md) |

**Hard rule:** `AgentDeposit.sol` must compile and pass tests with zero switchboard imports. The integration is by address, not by interface. This survives every switchboard release, including breaking ones.

---

## 4. Switchboard primitives the registry depends on

Each row is a contract that switchboard must hold for cr8 to function. Versions track switchboard's published tags.

| Primitive | Switchboard surface | Used by cr8 for | Stability |
|---|---|---|---|
| MPC wallet provisioning | `switchboard.provision_wallet(quorum, recovery_set) -> Address` | Step 1–2 of §2 | Stable since `v0.1.0` |
| Threshold signing | `switchboard.sign(wallet_id, payload) -> Signature` | Any `AgentDeposit` tx the agent submits (step 4, 6, 9) | Stable since `v0.1.0` |
| Key rotation | `switchboard.rotate(wallet_id, new_quorum) -> Address (same)` | Address must not change; quorum may. See §6. | Stable since `v0.1.0` |
| x402 metering | `switchboard.meter(session_id, rate) -> Receipt` | Step 7 — produces the off-chain receipt the issuer posts to `settle` | Stable since `v0.1.0` |
| A2A counterparty handshake | `switchboard.a2a_handshake(peer) -> Channel` | Required for agent↔agent payouts (not Phase 1 critical path) | Stable since `v0.1.0` |
| Recovery quorum lookup | `switchboard.recovery_quorum(wallet_id) -> Set<Address>` | Optional registry-side display only | Stable since `v0.1.0` |

If switchboard breaks any of these, cr8 has to ship a contract change. Therefore: switchboard's MAJOR version is part of cr8's release notes.

---

## 5. Contract behaviour requirements

The cr8 registry MUST satisfy the following, regardless of switchboard implementation. These are the testable bits.

### 5.1 `AgentDeposit.register`

- Input: `address agent`, `bytes32 profileUri` (IPFS CID v1, sha-256 multihash; the registry does not pin content).
- Effect: assigns the next `AgentId` and stores `agent → id`, `id → agent`, `id → profileUri`.
- Reverts: if `agent` is the zero address, if `agent` is already registered, if `profileUri` is `bytes32(0)`.
- Emits: `AgentRegistered(address indexed agent, uint64 indexed id, bytes32 profileUri)`.
- Access: anyone may call (the registry does not gatekeep wallet provenance — only one wallet per address).

### 5.2 `AgentDeposit.deposit`

- Input: `uint64 agentId`, `uint256 amountUsdc`.
- Pre-cond: `agentId` exists; `msg.sender` has approved the contract for at least `amountUsdc` of USDC.
- Effect: `IERC20(USDC).transferFrom(msg.sender, address(this), amountUsdc)`; increments `balances[id]`.
- Emits: `Deposited(uint64 indexed id, address indexed from, uint256 amount)`.
- **Idempotency:** none required. Each call moves new funds.

### 5.3 `AgentDeposit.settle`

- Input: `uint64 agentId`, `uint256 amountUsdc`, `bytes calldata receipt`, `bytes calldata switchboardSig`.
- `receipt` is an opaque blob; the contract only verifies the signature and the included `(agentId, amountUsdc, nonce)` triple.
- `switchboardSig` is signed by the agent's MPC wallet (the address registered in §5.1). The contract recovers the signer and rejects if it does not match.
- Replay protection: `(agentId, nonce)` MUST be strictly monotonic per agent. Settlement reverts on equal-or-lower nonce.
- Effect: pays `amountUsdc` USDC from `balances[id]` to the registered counterparty extracted from `receipt`.
- Emits: `TaskSettled(uint64 indexed agentId, uint256 amountUsdc, uint64 nonce, bytes32 receiptHash)`.

### 5.4 `AgentDeposit.withdraw`

- Input: `uint64 agentId`, `uint256 amountUsdc`.
- Pre-cond: caller is the agent's currently-registered address (i.e., the MPC wallet signing for `agentId`).
- Effect: `IERC20(USDC).transfer(agentAddress, amountUsdc)`; decrements `balances[id]`.
- Emits: `Withdrawn(uint64 indexed id, uint256 amount)`.

### 5.5 Events read by the registry surface

Only these events are part of the public read API. Anything not listed is internal and may change between releases.

```
AgentRegistered(address indexed agent, uint64 indexed id, bytes32 profileUri)
AgentRotated   (uint64 indexed id, address indexed oldAddr, address indexed newAddr)
Deposited      (uint64 indexed id, address indexed from, uint256 amount)
Withdrawn      (uint64 indexed id, uint256 amount)
TaskSettled    (uint64 indexed agentId, uint256 amountUsdc, uint64 nonce, bytes32 receiptHash)
```

---

## 6. Failure modes and their handling

### 6.1 Switchboard outage

The registry remains fully usable for **read** and **withdraw** during a switchboard outage, because both depend only on the on-chain address and registry state. **Write** (settlement, new registration) requires switchboard for signing.

Behaviour:

- `register`, `deposit`, `settle`, `withdraw` revert with the standard EVM revert reason; the failure surface is the wallet, not the contract.
- The registry MUST NOT include an "emergency settle" path that bypasses switchboard signature checks. Doing so re-introduces single-key custody.
- Off-chain dashboards SHOULD show `switchboard_health: degraded` and disable submit buttons; reads remain live.

### 6.2 Key rotation

Switchboard rotation preserves the on-chain address (rotation is a quorum swap, not a key swap). However, in catastrophic cases an agent may need to rotate to a **new** address.

Behaviour:

- `AgentDeposit.rotate(uint64 id, address newAgent, bytes calldata switchboardProof)` — signed by the old MPC quorum, attested by switchboard.
- `switchboardProof` is verified by recovering against the OLD agent address.
- Effect: `agent → id` mapping is updated; old address is retired (registers as `address(0)` for that id).
- Emits: `AgentRotated(uint64 indexed id, address indexed oldAddr, address indexed newAddr)`.
- The new address inherits the deposit balance, profile URI, and id. Task settlement nonce is **not** reset.

### 6.3 Agent wallet recovery (key loss)

Recovery is a switchboard concern. The registry sees only the resulting `rotate` call from the new MPC quorum.

Recovery policy is published off-chain (see [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard) `RECOVERY.md`) and is **not** ratified by the registry. Agents and their counterparties must inspect the recovery quorum before transacting; the registry does not enforce quorum size.

### 6.4 Disputed settlements

The registry does not arbitrate. `settle` either reverts (bad signature, replay, insufficient balance) or executes. Disputes are off-chain via switchboard A2A channels or the task issuer's own dispute flow. A future `Dispute` precompile is out of scope here.

---

## 7. End-to-end test against Arbitrum Sepolia

A contributor reading only this spec should be able to:

1. `cargo install switchboard-cli` (from [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard)).
2. `switchboard wallet provision --quorum 2/3 --rpc $ARB_SEPOLIA` → returns `0xAgent...`.
3. Fund the wallet with 10 USDC from a faucet.
4. `arbitrum-cli cr8 register --address 0xAgent... --profile ipfs://Qm...` (see [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md)).
5. `arbitrum-cli cr8 deposit --agent <id> --amount 5` (USDC).
6. Run a sample x402-metered task against the demo issuer endpoint (URL in switchboard `EXAMPLES.md`).
7. Observe `TaskSettled` event in the issuer dashboard.
8. `arbitrum-cli cr8 withdraw --agent <id> --amount 1`.

Each command exits non-zero on failure with a structured JSON error (see arbitrum-cli spec §3.2).

---

## 8. Out of scope (will not be specified here)

- CR8-USD mint/redeem flow — separate spec, Phase 2.
- Lucidly syUSD auto-park policy — separate spec, Phase 1.5.
- Slashing / reputation — Phase 2+. Until then, `TaskSettled` event history is the public reputation surface.
- Cross-chain wallet portability — Phase 3+; not in switchboard's Phase 1 contract.

---

## 9. References

- [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard) — wallet primitive
- [`kcolbchain/switchboard#20`](https://github.com/kcolbchain/switchboard/issues/20) — Lucidly syUSD idle-balance auto-park
- [`kcolbchain/arka`](https://github.com/kcolbchain/arka) — Rust agent SDK
- [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli) — agent-first CLI
- ERC-7528 (canonical ERC-20 USDC address handling)
- x402 HTTP payment metering (off-chain)

— [kcolbchain](https://kcolbchain.com) / [Abhishek Krishna](https://abhishekkrishna.com)
