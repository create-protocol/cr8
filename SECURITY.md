# Security Policy

## Supported Versions

CR8 is currently in pre-audit Phase 1 development. No version has been formally
audited or deployed to Arbitrum mainnet. All contracts on Arbitrum Sepolia
(testnet) should be treated as unaudited.

| Version / Phase | Supported |
| --------------- | --------- |
| Phase 1 — Agent registry MVP (testnet) | Security reports accepted |
| Phase 2+ — CR8-USD stablecoin, staking, vesting | Not yet deployed |

Once Phase 1 passes audit and mainnet deployment occurs, this table will be
updated with specific contract addresses and the corresponding supported
version.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security vulnerabilities via email:

**security@kcolbchain.com**

Include in your report:

- A description of the vulnerability and its potential impact.
- Contract name(s) and function(s) affected.
- A proof-of-concept or reproduction steps (even a minimal one).
- Whether you believe the issue is exploitable on testnet, mainnet, or both.
- Your preferred contact method for follow-up.

### Response timeline

| Step | Target |
| ---- | ------ |
| Acknowledgement | Within 48 hours |
| Initial triage and severity assessment | Within 5 business days |
| Fix or mitigation plan communicated | Within 14 business days |
| Public disclosure (after fix) | Coordinated with reporter |

We follow responsible disclosure: we will not take legal action against good-faith
security research that follows this policy.

## Scope

In scope:

- All Solidity contracts under this org (`AgentDeposit`, CR8-USD stablecoin,
  staking, vesting, Lucidly adapter).
- Protocol logic bugs — reentrancy, access-control bypass, arithmetic errors,
  oracle manipulation, flash-loan attack vectors.
- Integration vulnerabilities between Create Protocol contracts and Lucidly
  `syUSD` vaults.

Out of scope:

- Front-end / off-chain tooling bugs (please open a regular issue).
- Gas optimizations (please open a regular issue).
- Issues in third-party dependencies (Arbitrum, OpenZeppelin, Lucidly) —
  report those upstream.
- Theoretical attacks with no realistic path to exploitation.

## Bug Bounty

A formal bug bounty program will be announced alongside the Phase 1 mainnet
deployment. Until then, critical vulnerability reports will be acknowledged
in our public changelogs, and reporters may be invited to participate in the
pre-audit review program with appropriate recognition.
