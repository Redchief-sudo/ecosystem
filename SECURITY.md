# Security Policy

## Overview

Ecosystem is designed as a **research-grade, infrastructure framework** for autonomous trading systems. Security is treated as a **first-class architectural concern**, not an afterthought.

The system prioritizes:

* Deterministic behavior
* Explicit risk boundaries
* Controlled execution paths
* Safe-by-default operation

By default, Ecosystem **does not execute live trades** and **does not require private keys**.

---

## Default Safety Guarantees

Out of the box, Ecosystem enforces the following guarantees:

* **No real funds** are used
* **No private keys** are loaded or required
* **Execution can be fully simulated or disabled**
* **Risk limits are enforced before execution**
* **All decisions are logged and traceable**

Any deviation from these defaults requires **explicit configuration changes**.

---

## Execution Gating

Trade execution is intentionally gated behind multiple layers:

1. **Strategy evaluation** — produces signals only
2. **Entry & position policies** — validate intent eligibility
3. **Risk limits** — enforce capital and exposure constraints
4. **Trade intent construction** — validates all required fields
5. **Execution layer** — may be mocked, simulated, or disabled

At no point does a strategy directly execute trades.

---

## Key Management

* Ecosystem does **not** ship with key management enabled
* No private keys are stored in the repository
* Environment variables and secrets are intentionally ignored by version control

If live execution is enabled, key handling is the responsibility of the operator and should follow industry best practices (HSMs, vaults, or hardware wallets).

---

## Configuration Safety

Configuration files:

* Are schema-validated where applicable
* Separate strategy logic from execution parameters
* Support read-only simulation modes

Misconfigured or incomplete configs are designed to **fail fast**, not silently degrade.

---

## Known Limitations

* This project is under active development
* Formal third-party security audits have not yet been completed
* Live trading environments require additional hardening by operators

These limitations are explicitly acknowledged and tracked.

---

## Reporting Security Issues

If you discover a security vulnerability:

* **Do not** open a public issue
* Contact the maintainer directly via GitHub

Responsible disclosure is appreciated.

---

## Disclaimer

This software is provided **as-is**, without warranty of any kind.

It is intended for research, experimentation, and infrastructure development. Use in live trading environments is done **entirely at the operator’s own risk**.
