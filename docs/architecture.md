# System Architecture

## Overview

This project is a modular, open-source framework for **on-chain token discovery, scoring, strategy evaluation, and execution planning** across multiple EVM-compatible chains. It is designed as **research-first infrastructure**: components are deterministic, composable, and inspectable, enabling reproducible analysis and safe experimentation.

The system deliberately separates **data ingestion**, **decision-making**, and **execution intent generation** to ensure transparency and auditability.

---

## High-Level Architecture

```
┌──────────────────────────────┐
│ Multi-Chain Ingestion Layer  │
│  - RPC / Indexer adapters    │
│  - Token discovery           │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Token Normalization Layer    │
│  - ScannedToken (canonical)  │
│  - Metrics & indicators      │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Strategy System              │
│  - StrategyManager           │
│  - Pluggable strategies      │
│  - Deterministic decisions   │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Intent Builder               │
│  - Single source of truth    │
│  - Validation & defaults     │
│  - TradeIntent objects       │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Execution Engine             │
│  - Chain-aware profiles      │
│  - Simulation or live exec   │
└──────────────────────────────┘
```

---

## Core Design Principles

### 1. Determinism over heuristics

All core domain objects (`ScannedToken`, `StrategyDecision`, `TradeIntent`) are:

* Typed dataclasses
* Serializable
* Free of hidden side effects

This enables reproducible research, offline analysis, and safe testing.

---

### 2. Strict separation of concerns

| Layer          | Responsibility          | Explicitly Does NOT Do  |
| -------------- | ----------------------- | ----------------------- |
| Ingestion      | Fetch & discover tokens | Score, trade, or decide |
| Normalization  | Canonical token model   | Chain-specific logic    |
| Strategy       | Evaluate & decide       | Execute trades          |
| Intent Builder | Validate & formalize    | Market interaction      |
| Execution      | Act on intents          | Generate decisions      |

This separation is enforced in code and treated as a **system invariant**.

---

### 3. Single source of truth for execution

The **Intent Builder** is the *only* component allowed to convert decisions into executable intents.

This constraint ensures:

* Consistent validation
* Centralized risk controls
* Auditability of execution logic

No other module may construct `TradeIntent` objects directly.

---

## Pluggability Model

### Fixed Components

* Core data models
* Execution intent schema
* Validation rules

These are intentionally stable to preserve compatibility.

### Pluggable Components

* Token scanners
* Strategy implementations
* Execution backends (simulated or live)

New strategies can be added without modifying the execution or ingestion layers.

---

## Public-Good Orientation

This architecture is designed to support:

* Research into token discovery and market structure
* Educational examples of DeFi execution pipelines
* Transparent experimentation without capital risk

The system can be used **without executing trades**, making it suitable for analysis, alerts, and simulation-only use cases.

---

## Non-Goals (Explicit)

The following are deliberately out of scope:

* Capital management
* Profit guarantees
* Alpha claims
* Closed or proprietary strategies

These constraints reinforce the project’s role as **open infrastructure**, not a managed trading product.

---

## Summary

The architecture prioritizes clarity, determinism, and composability. By separating discovery, decision-making, and execution intent generation, the system enables trustworthy research and safe experimentation across multiple chains while remaining extensible for future public-good use cases.
