# arka `CR8Client` — Module Contract

**Status:** Draft 1 · **Closes:** [`create-protocol/cr8#11`](https://github.com/create-protocol/cr8/issues/11)

This spec freezes the Rust API surface that [`kcolbchain/arka`](https://github.com/kcolbchain/arka) will expose for Create Protocol. After this lands, arka has a stable contract to implement against and any agent author can write code that compiles against `CR8Client` without reading our Solidity.

The contract is **API only.** Implementation choices (chain client, retry policy, MPC backend) live in arka.

---

## 1. Design constraints

1. **No hand-rolled ABI calls.** A Rust agent should never see `H160`, `U256`, `encode_function_input`, or RPC URLs unless it asks for them.
2. **Switchboard-native.** Every signing path goes through switchboard's MPC client; we do not accept a private-key constructor.
3. **Strongly typed errors.** A single `CR8Error` enum covers every failure mode; consumers `match` on it.
4. **Stream-first.** Long-running agents poll nothing; they subscribe.
5. **MCP-friendly.** Every public method maps cleanly to a tool call in [`specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md). If a method cannot be expressed as a JSON-in/JSON-out tool call, it does not belong on the trait.

---

## 2. Trait surface

```rust
use std::pin::Pin;
use futures_core::Stream;
use switchboard::Wallet;

pub type AgentId = u64;
pub type TaskId = String;          // opaque off-chain task id
pub type TxHash = [u8; 32];
pub type Nonce = u64;
pub type UsdcAmount = u64;         // smallest unit (6 decimals)
pub type SyUsdAmount = u128;       // smallest unit (18 decimals)

#[derive(Clone, Debug)]
pub struct AgentProfile {
    pub display_name: String,
    pub capability_tags: Vec<String>,  // e.g. ["llm:text", "rag:retrieval"]
    pub endpoint_url: String,          // off-chain task-claim endpoint
    pub a2a_pricing: A2aPricing,       // see §2.4
}

#[derive(Clone, Debug)]
pub struct Balance {
    pub idle_usdc: UsdcAmount,         // sitting in AgentDeposit
    pub parked_syusd: SyUsdAmount,     // routed to Lucidly
    pub pending_payouts: UsdcAmount,   // accepted but not yet released
}

#[derive(Clone, Debug)]
pub struct TaskHandle {
    pub task_id: TaskId,
    pub agent_id: AgentId,
    pub nonce: Nonce,
    pub claimed_at_block: u64,
    pub max_payout_usdc: UsdcAmount,
}

#[derive(Clone, Debug)]
pub struct Payout {
    pub task_id: TaskId,
    pub paid_usdc: UsdcAmount,
    pub tx_hash: TxHash,
    pub receipt_hash: [u8; 32],
}

#[derive(Clone, Debug)]
pub struct TaskReceipt {
    pub task_id: TaskId,
    pub work_proof: Vec<u8>,           // task-issuer-specific opaque bytes
    pub x402_session: String,          // switchboard meter session id
}

#[derive(Clone, Debug)]
pub enum RegistryEvent {
    AgentRegistered { id: AgentId, address: [u8; 20] },
    AgentRotated    { id: AgentId, old_addr: [u8; 20], new_addr: [u8; 20] },
    Deposited       { id: AgentId, amount: UsdcAmount },
    Withdrawn       { id: AgentId, amount: UsdcAmount },
    TaskSettled     { id: AgentId, amount: UsdcAmount, nonce: Nonce, receipt_hash: [u8; 32] },
}

pub trait CR8Client: Send + Sync {
    async fn register(&self, profile: AgentProfile) -> Result<AgentId, CR8Error>;
    async fn deposit(&self, agent: AgentId, amount: UsdcAmount) -> Result<TxHash, CR8Error>;
    async fn withdraw(&self, agent: AgentId, amount: UsdcAmount) -> Result<TxHash, CR8Error>;

    async fn claim_task(&self, agent: AgentId, task: TaskId) -> Result<TaskHandle, CR8Error>;
    async fn complete_task(&self, handle: TaskHandle, receipt: TaskReceipt) -> Result<Payout, CR8Error>;

    async fn balance(&self, agent: AgentId) -> Result<Balance, CR8Error>;
    async fn profile(&self, agent: AgentId) -> Result<AgentProfile, CR8Error>;

    fn watch(&self, agent: Option<AgentId>) -> Pin<Box<dyn Stream<Item = RegistryEvent> + Send>>;
}
```

### 2.1 Constructor pattern

Concrete builder lives in arka. The shape it must satisfy:

```rust
pub struct CR8ClientBuilder { /* ... */ }

impl CR8ClientBuilder {
    pub fn new(rpc_url: impl Into<String>) -> Self;
    pub fn wallet(mut self, wallet: Wallet) -> Self;                 // from switchboard
    pub fn agent_deposit_address(mut self, addr: [u8; 20]) -> Self;  // override; defaults per network
    pub fn confirmations(mut self, n: u8) -> Self;                   // default 2
    pub fn build(self) -> Result<Box<dyn CR8Client>, CR8Error>;
}
```

Note: no private-key setter. The only signing path is `Wallet`, which is provisioned via switchboard and may be an MPC quorum behind the scenes.

### 2.2 `claim_task` / `complete_task` semantics

- `claim_task` does **not** touch chain. It reserves a `nonce` from the local nonce manager and writes a session record to switchboard's x402 meter. The handle is the contract between the agent runtime and the SDK.
- `complete_task` **does** touch chain: it submits `AgentDeposit.settle(id, amount, receipt, sig)` and waits `confirmations`.
- If the agent crashes between `claim_task` and `complete_task`, the handle is recoverable via `recover_handle(task_id)` (added in §2.5).

### 2.3 `balance` is read-through

The SDK reads on-chain idle USDC, then asks the Lucidly adapter for `parked_syusd`, then sums pending payouts from local nonce state. One method, three sources, single struct.

### 2.4 `A2aPricing`

```rust
#[derive(Clone, Debug)]
pub struct A2aPricing {
    pub currency: Currency,            // Usdc | SyUsd (Phase 2+: Cr8Usd)
    pub rate_per_unit: u128,           // smallest unit per pricing_unit
    pub pricing_unit: PricingUnit,     // PerCall | PerToken | PerSecond
}
```

A2A pricing is stored in the registry as part of the agent profile so that switchboard can quote agent-to-agent transactions without a side-channel.

### 2.5 Recovery API

```rust
pub trait CR8ClientRecovery {
    async fn recover_handle(&self, task: TaskId) -> Result<Option<TaskHandle>, CR8Error>;
    async fn list_pending(&self, agent: AgentId) -> Result<Vec<TaskHandle>, CR8Error>;
}
```

Available as a sibling trait so that the main `CR8Client` stays minimal and embeddable in constrained environments. Default `arka::CR8Client` impl will implement both.

---

## 3. Error taxonomy

```rust
#[derive(Debug, thiserror::Error)]
pub enum CR8Error {
    // Configuration / setup
    #[error("rpc_url is missing or unreachable: {0}")]
    Rpc(String),
    #[error("agent_deposit contract address not set for chain_id {0}")]
    UnknownNetwork(u64),

    // Identity / registration
    #[error("agent {0} already registered")]
    AlreadyRegistered(AgentId),
    #[error("agent {0} not registered")]
    NotRegistered(AgentId),
    #[error("caller address does not match agent {0}'s registered address")]
    NotAuthorized(AgentId),

    // Funds
    #[error("agent {agent} has insufficient balance: requested {requested}, available {available}")]
    InsufficientBalance { agent: AgentId, requested: u128, available: u128 },
    #[error("USDC allowance insufficient: need {needed}, have {have}")]
    InsufficientAllowance { needed: u128, have: u128 },

    // Task lifecycle
    #[error("task {0} already claimed by another agent")]
    TaskAlreadyClaimed(TaskId),
    #[error("task {0} not claimed by agent {1}")]
    TaskNotClaimed(TaskId, AgentId),
    #[error("nonce {0} has already settled (replay)")]
    NonceReplay(Nonce),
    #[error("switchboard signature verification failed")]
    SignatureInvalid,

    // Switchboard / wallet
    #[error("switchboard quorum unreachable")]
    WalletUnavailable,
    #[error("switchboard meter session {0} not found")]
    MeterSessionMissing(String),

    // Chain
    #[error("transaction reverted: {0}")]
    Reverted(String),
    #[error("tx not confirmed after {0} blocks")]
    NotConfirmed(u64),

    // Catch-alls
    #[error("transport error: {0}")]
    Transport(String),
    #[error("internal: {0}")]
    Internal(String),
}
```

Consumers `match` on the variant; the `Internal` arm is the only one without operational semantics. Adding new variants is a minor-version-only change.

---

## 4. End-to-end example

```rust
use arka::cr8::{CR8ClientBuilder, AgentProfile, A2aPricing, Currency, PricingUnit, TaskReceipt};
use switchboard::WalletBuilder;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let wallet = WalletBuilder::new()
        .quorum("2/3")
        .recovery_set(vec!["alice@kcolbchain", "bob@kcolbchain", "device-key"])
        .provision()
        .await?;

    let cr8 = CR8ClientBuilder::new("https://sepolia-rollup.arbitrum.io/rpc")
        .wallet(wallet.clone())
        .confirmations(2)
        .build()?;

    // One-time agent setup
    let agent_id = cr8
        .register(AgentProfile {
            display_name: "summariser-001".into(),
            capability_tags: vec!["llm:text".into(), "rag:summarise".into()],
            endpoint_url: "https://agent.example/api/task".into(),
            a2a_pricing: A2aPricing {
                currency: Currency::Usdc,
                rate_per_unit: 100,           // 0.0001 USDC per token
                pricing_unit: PricingUnit::PerToken,
            },
        })
        .await?;

    cr8.deposit(agent_id, 5_000_000).await?;     // 5 USDC

    // Per-task loop
    loop {
        let task_id = pull_task_from_issuer().await?;
        let handle = cr8.claim_task(agent_id, task_id.clone()).await?;

        let work_proof = do_the_work(&task_id).await?;       // agent business logic
        let receipt = TaskReceipt {
            task_id: task_id.clone(),
            work_proof,
            x402_session: handle.task_id.clone(),
        };

        match cr8.complete_task(handle, receipt).await {
            Ok(payout) => println!("settled {} for {} USDC", payout.task_id, payout.paid_usdc),
            Err(arka::cr8::CR8Error::NonceReplay(n)) => {
                eprintln!("replay on nonce {n}, recovering");
                // recover via CR8ClientRecovery::recover_handle
            }
            Err(e) => return Err(e.into()),
        }
    }
}
```

This compiles against the trait above. Implementations live in arka.

---

## 5. Versioning rules

| Change | Semver bump | Example |
|---|---|---|
| Adding a new variant to `CR8Error` | minor | new chain-level revert reason |
| Adding a new method to `CR8Client` (with default impl) | minor | `pause(agent_id)` |
| Adding a new method without a default impl | major | breaks downstream impls |
| Changing a field type on `AgentProfile`, `Balance`, `TaskHandle`, `Payout` | major | renaming `idle_usdc` |
| Adding an optional field to an event | minor | extending `RegistryEvent::TaskSettled` |
| Renaming any public type | major | always |

Arka's `Cargo.toml` MUST pin `cr8-spec` to a minor range, e.g. `cr8-spec = "0.2"`.

---

## 6. Companion tracking

Once this spec merges, open:

- [`kcolbchain/arka#?`](https://github.com/kcolbchain/arka) — "Implement `CR8Client` per [`create-protocol/cr8/specs/arka-cr8-client.md`](https://github.com/create-protocol/cr8/blob/main/specs/arka-cr8-client.md)"

The tracking issue references this spec by commit-pinned URL so future spec edits do not silently change the implementation target.

---

## 7. References

- [`create-protocol/cr8/specs/switchboard-integration.md`](./switchboard-integration.md) — wallet primitive + contract behaviour
- [`create-protocol/cr8/specs/arbitrum-cli-cr8-subcommand.md`](./arbitrum-cli-cr8-subcommand.md) — agent-first CLI surface
- [`kcolbchain/arka`](https://github.com/kcolbchain/arka)
- [`kcolbchain/switchboard`](https://github.com/kcolbchain/switchboard)
- [`kcolbchain/arbitrum-cli`](https://github.com/kcolbchain/arbitrum-cli)

— [kcolbchain](https://kcolbchain.com) / [Abhishek Krishna](https://abhishekkrishna.com)
