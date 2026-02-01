# Strategy System

## Purpose

The strategy system is responsible for **evaluating normalized token data and producing deterministic decisions**. It is explicitly **non-executing** and **non-capital-aware**, enabling reproducible research, comparison of approaches, and safe experimentation.

Strategies operate on canonical inputs and emit standardized outputs that downstream components can audit and validate.

---

## Core Concepts

### Strategy

A **strategy** is a pure evaluation unit that:

* Consumes one or more `ScannedToken` objects
* Applies transparent logic (rules, indicators, thresholds)
* Emits a `StrategyDecision`

A strategy **must not**:

* Execute trades
* Access private keys
* Perform network I/O
* Maintain hidden state

This constraint ensures strategies remain deterministic and testable.

---

### StrategyDecision

A `StrategyDecision` represents the **full reasoning output** of a strategy evaluation.

Typical fields include:

* Decision outcome (e.g. approve / reject / observe)
* Confidence or score
* Rationale and contributing signals
* Optional metadata for analysis

Decisions are data, not actions.

---

## Strategy Manager

The **Strategy Manager** orchestrates strategy evaluation.

Responsibilities:

* Registering available strategies
* Providing a consistent evaluation lifecycle
* Aggregating decisions across strategies
* Enforcing evaluation order and constraints

The manager does **not**:

* Resolve execution conflicts
* Optimize profit
* Select capital allocation

It exists to provide **comparability and structure**, not dominance logic.

---

## Evaluation Flow

```
ScannedToken(s)
      │
      ▼
┌────────────────────┐
│ Strategy Manager   │
│  - invokes each    │
│    registered      │
│    strategy        │
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│ StrategyDecision(s)│
│  - structured      │
│  - explainable     │
└────────────────────┘
```

Each strategy is evaluated independently, enabling side-by-side comparison and ensemble-style analysis without implicit coupling.

---

## Pluggability and Extension

### Adding a New Strategy

To add a strategy:

* Implement the strategy interface
* Declare required inputs
* Return a `StrategyDecision`

No changes to execution or ingestion layers are required.

### Research Use Cases

This design supports:

* A/B testing of decision logic
* Strategy benchmarking
* Educational demonstrations
* Alert-only or simulation workflows

---

## Determinism and Reproducibility

Given the same:

* Input tokens
* Strategy configuration
* Versioned code

The strategy system will produce identical decisions.

This property is essential for:

* Scientific comparison
* Debugging
* Public-good research

---

## Explicit Non-Goals

The strategy system intentionally avoids:

* Capital management
* Risk sizing
* Portfolio optimization
* Profit attribution

These concerns belong to separate layers or external systems.

---

## Summary

The strategy system provides a **clean, deterministic decision layer** that bridges token discovery and execution intent generation. By enforcing strict boundaries and standardized outputs, it enables transparent research, extensibility, and safe collaboration within a public-good framework.
