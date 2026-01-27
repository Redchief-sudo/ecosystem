# Contributing to Ecosystem

Thank you for your interest in contributing to **Ecosystem**.

This project is an **infrastructure-grade, simulation-first autonomous trading framework**. Contributions are expected to uphold strict standards around correctness, determinism, safety, and architectural clarity.

This is **not** a consumer trading bot and **not** optimized for short-term experimentation at the expense of system integrity.

---

## Core Principles

All contributions must respect the following principles:

1. **Simulation-First**
   No contribution should require live capital, private keys, or real execution by default.

2. **Determinism Over Convenience**
   System behavior must be reproducible, inspectable, and explainable.

3. **Explicit Governance**
   Risk, entry, position, and exit logic must be modeled explicitly — not embedded implicitly.

4. **Separation of Concerns**
   Scanning, decision-making, intent generation, and execution must remain cleanly separated.

5. **Safety by Default**
   Unsafe behavior must require *intentional configuration*, never accidental activation.

---

## What You Can Contribute

### ✅ Encouraged Contributions

* Simulation / dry-run tooling
* Deterministic trading lifecycle tests
* Risk and policy enforcement logic
* Multi-chain normalization improvements
* Strategy evaluation frameworks (not profit claims)
* Observability, logging, and diagnostics
* Documentation and architectural clarification

### 🚫 Discouraged / Out-of-Scope Contributions

* Live trading shortcuts
* Hardcoded private keys or RPC credentials
* Profit guarantees or performance marketing
* Chain-specific hacks that break abstraction boundaries
* UI layers that obscure execution logic

---

## Safety & Execution Rules

By default:

* **No real trades are executed**
* **No private keys are loaded**
* **All execution paths are simulated or disabled**

Any contribution that introduces live execution capability **must**:

1. Be explicitly gated behind configuration flags
2. Include a simulation-safe fallback
3. Be reviewed for failure modes
4. Never be enabled by default

Pull requests violating these rules will be rejected.

---

## Architecture Boundaries (Important)

Contributors **must not** bypass or collapse the following layers:

* **Scanners** → discover opportunities only
* **Strategies** → evaluate signals only
* **Intent Builder** → convert decisions into executable intents
* **Policies (entry/position/exit/risk)** → enforce governance
* **Execution** → act on approved intents

Trade intents **must only be created** via the intent builder.

---

## Development Setup

Basic environment setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Simulation and tests **must run without secrets or API keys**.

---

## Testing Expectations

All non-trivial changes must include:

* Unit tests **or** lifecycle tests
* Clear assertions (not print-based validation)
* Deterministic outcomes where applicable

If behavior cannot be deterministically tested, it must be explicitly documented.

---

## Pull Request Guidelines

When opening a PR:

* Clearly state *what domain* you are modifying
* Explain *why* the change is needed
* Describe any new invariants or assumptions
* Confirm simulation-only safety

Low-context or speculative PRs may be closed without review.

---

## Review Philosophy

Reviews prioritize:

1. Correctness
2. Safety
3. Architectural integrity
4. Long-term maintainability

Speed and novelty are secondary.

---

## Code of Conduct

Be respectful, precise, and constructive.

This project values **clarity over ego** and **correctness over cleverness**.

---

## Disclaimer

This project is provided for research and infrastructure purposes only.
It does not constitute financial advice.

Contributors are responsible for understanding the implications of any code they submit.
