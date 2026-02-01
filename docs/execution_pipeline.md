# Execution Pipeline

## Purpose

The execution pipeline is responsible for **acting on validated execution intents** produced by the system. It is deliberately separated from strategy logic to ensure that **decisions and actions remain distinct**, auditable, and reproducible.

This layer may operate in **simulation-only** or **live execution** modes, depending on configuration.

---

## Core Principle: Intent ≠ Execution

A central design invariant of this system is:

> **No execution occurs without a `TradeIntent`.**

All market interaction flows exclusively from a validated intent object. This guarantees:

* Centralized validation
* Consistent defaults
* Explicit risk boundaries
* Full audit trails

No other component is permitted to submit transactions or interact with markets directly.

---

## TradeIntent

A `TradeIntent` represents a **fully specified, execution-ready plan**.

Typical properties include:

* Chain and protocol identifiers
* Trade side and size parameters
* Execution type (e.g. market, limit, simulated)
* Time validity and safety constraints

TradeIntents are:

* Immutable once constructed
* Serializable
* Suitable for logging, simulation, or deferred execution

---

## Intent Builder

The **Intent Builder** is the sole authority for converting `StrategyDecision` objects into `TradeIntent`s.

Responsibilities:

* Validating decision inputs
* Applying execution defaults
* Enforcing system-wide constraints
* Rejecting malformed or unsafe intents

This consolidation prevents fragmented execution logic and simplifies auditing.

---

## Execution Engine

The **Execution Engine** consumes `TradeIntent` objects and performs one of the following actions:

* Simulate execution (no on-chain interaction)
* Generate execution plans
* Submit transactions to the network (when enabled)

The engine does not evaluate strategies or reinterpret decisions.

---

## Chain-Aware Execution Profiles

Execution behavior is configured through **chain execution profiles**, which define:

* Supported protocols
* Gas and fee handling
* Confirmation assumptions
* Safety fallbacks

This abstraction allows the same intent to be executed (or simulated) across different EVM chains without modifying upstream logic.

---

## Simulation Mode

Simulation is a first-class capability.

In simulation mode:

* No private keys are required
* No transactions are broadcast
* Outputs are fully inspectable

This mode enables:

* Research and experimentation
* Educational demonstrations
* Pre-flight validation of strategies

---

## Safety and Reproducibility

The execution pipeline prioritizes safety through:

* Explicit intent validation
* Immutable execution plans
* Configurable execution boundaries

Given identical intents and configuration, execution behavior is deterministic.

---

## Explicit Non-Goals

The execution pipeline does not:

* Select strategies
* Manage capital allocation
* Optimize for profit
* Conceal execution logic

These responsibilities are intentionally excluded to preserve transparency and trust.

---

## Summary

The execution pipeline provides a **controlled, auditable bridge** between abstract decisions and real-world actions. By enforcing intent-based execution and chain-aware profiles, the system supports safe simulation, reproducible research, and transparent on-chain interaction within a public-good framework.
