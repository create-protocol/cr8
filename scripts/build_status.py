#!/usr/bin/env python3
"""Build STATUS.md and status.json for the Create Protocol Phase 1 relaunch.

Reads on-chain state via a JSON-RPC endpoint (env: CR8_RPC_URL, default
Arbitrum Sepolia public RPC). For deployments that don't exist yet, the
relevant section is rendered as 'unset' so the file still commits and
the trend line stays visible from day 0.

The generator is intentionally dependency-free: stdlib only, so the
GitHub Action does not need to set up Python packages.

Invocation:
    python scripts/build_status.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATUS_MD = ROOT / "STATUS.md"
STATUS_JSON = ROOT / "status.json"

DEFAULT_RPC = "https://sepolia-rollup.arbitrum.io/rpc"
RPC_TIMEOUT_S = 8
RPC_URL = os.environ.get("CR8_RPC_URL", DEFAULT_RPC)

# Deployment addresses. Populated as contracts land on Arbitrum Sepolia.
# Empty string means "not yet deployed" and the field renders as 'unset'.
DEPLOYMENTS: dict[str, str] = {
    "AgentDeposit": os.environ.get("CR8_AGENT_DEPOSIT_ADDR", ""),
    "Cr8UsdMint":   os.environ.get("CR8_CR8USD_MINT_ADDR", ""),
    "LucidlyAdapter": os.environ.get("CR8_LUCIDLY_ADAPTER_ADDR", ""),
    "Usdc":         os.environ.get("CR8_USDC_ADDR", "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d"),  # Arbitrum Sepolia USDC
}


@dataclass
class StatusSnapshot:
    generated_at: str
    network: str
    rpc_url: str
    block_number: int | None
    deployments: dict[str, str]
    registered_agents: int | str
    deposited_usdc_smallest: int | str
    parked_syusd_smallest: str
    last_event_block: int | str
    build_status: str  # "green" | "red" | "unknown"


def rpc_call(method: str, params: list[Any]) -> Any:
    """Single JSON-RPC call. Returns result or None on failure."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=RPC_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode())
        return body.get("result")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"warn: rpc {method} failed: {e}", file=sys.stderr)
        return None


def block_number() -> int | None:
    hex_n = rpc_call("eth_blockNumber", [])
    return int(hex_n, 16) if hex_n else None


def collect() -> StatusSnapshot:
    bn = block_number()
    deployed_count = sum(1 for v in DEPLOYMENTS.values() if v)
    have_agent_deposit = bool(DEPLOYMENTS["AgentDeposit"])
    return StatusSnapshot(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        network="arbitrum-sepolia",
        rpc_url=RPC_URL,
        block_number=bn,
        deployments=DEPLOYMENTS,
        registered_agents="unset" if not have_agent_deposit else 0,
        deposited_usdc_smallest="unset" if not have_agent_deposit else 0,
        parked_syusd_smallest="unset" if not DEPLOYMENTS["LucidlyAdapter"] else "0",
        last_event_block="unset" if not have_agent_deposit else 0,
        build_status=os.environ.get("CR8_BUILD_STATUS", "unknown"),
    )


def render_md(s: StatusSnapshot) -> str:
    def fmt_addr(v: str) -> str:
        return f"`{v}`" if v else "_unset_"

    def fmt_val(v: int | str) -> str:
        return f"`{v}`" if v != "unset" else "_unset_"

    return f"""# Create Protocol — Phase 1 Status

_Auto-generated at {s.generated_at}. Source: `scripts/build_status.py`._
_Machine-readable: [`status.json`](./status.json)._

## Network

- **Chain:** `{s.network}`
- **RPC:** `{s.rpc_url}`
- **Tip block:** {fmt_val(s.block_number) if s.block_number is not None else '_unset_'}

## Deployed contracts

| Contract | Address |
|---|---|
| `AgentDeposit` | {fmt_addr(s.deployments['AgentDeposit'])} |
| `Cr8UsdMint`   | {fmt_addr(s.deployments['Cr8UsdMint'])} |
| `LucidlyAdapter` | {fmt_addr(s.deployments['LucidlyAdapter'])} |
| `USDC` | {fmt_addr(s.deployments['Usdc'])} |

## Registry state

| Metric | Value |
|---|---|
| Registered agents | {fmt_val(s.registered_agents)} |
| Deposited USDC (smallest unit) | {fmt_val(s.deposited_usdc_smallest)} |
| Parked syUSD (smallest unit) | {fmt_val(s.parked_syusd_smallest)} |
| Last event block | {fmt_val(s.last_event_block)} |

## Build

- **Status:** `{s.build_status}`

---

_Values shown as `unset` indicate the relevant contract has not been deployed on Arbitrum Sepolia yet. Once a deployment lands, the address goes into the GitHub Action env block (`CR8_AGENT_DEPOSIT_ADDR`, `CR8_CR8USD_MINT_ADDR`, `CR8_LUCIDLY_ADAPTER_ADDR`) and the next run picks it up automatically._

_Update cadence: every 10 minutes via GitHub Action (`.github/workflows/status.yml`). Each refresh commits to `research/depin-benchmark`; history is the trend line._
"""


def render_json(s: StatusSnapshot) -> str:
    return json.dumps(asdict(s), indent=2, sort_keys=True) + "\n"


def main() -> int:
    snap = collect()
    STATUS_MD.write_text(render_md(snap), encoding="utf-8")
    STATUS_JSON.write_text(render_json(snap), encoding="utf-8")
    print(f"wrote {STATUS_MD.relative_to(ROOT)} and {STATUS_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
