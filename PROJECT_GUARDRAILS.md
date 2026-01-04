# Project Guardrails (DO NOT MODIFY OR DELETE)

This file defines non-negotiable constraints for all AI-assisted work on this project. Any changes require explicit human approval.

# AI conversation rules

- Address the developer using informal "ты", not "вы".
- Do not use polite/formal tone.
- Be concise, technical, and direct.
- No motivational fluff.
- Focus on analysis and concrete facts.

# Code writing rules

- Do not put comments in the code


# Claude Code Project Instructions

The section below defines **project-level rules** for Claude Code when working in this repository.
Claude Code CLI reads this file automatically at the start of every session.

---

## 1. Default Workflow

* **Always follow this pipeline:**
  **Plan Mode → agreed plan with Definition of Done → auto-accept edits → verification**
* Do **not** start implementation until the plan is explicitly approved.
* If Plan Mode is unnecessary for a task, clearly state why before proceeding.

---

## 2. Planning Rules

* Plans must be concrete and actionable.
* A plan must include:

  * files/modules to be changed
  * risks or assumptions
  * verification steps (tests, commands, checks)
* Avoid speculative refactors or improvements unless explicitly requested.

---

## 3. Implementation Rules

* Prefer **minimal, surgical changes** over large refactors.
* Do not delete:

  * tests
  * documentation
  * code paths
    unless explicitly approved.
* If unsure about intent or impact — **ask before acting**.

---

## 4. Verification (Mandatory)

* Every non-trivial change must be verified.
* Prefer existing tests and tooling.
* If verification fails:

  * fix the issue
  * re-run verification
  * only then report success

---

## 5. Permissions & Blocking

* If blocked by missing permissions, tools, or environment issues:

  * clearly state what is missing
  * stop execution
  * do not stall or retry silently

---

## 6. Stability & Failure Handling

* If execution stalls or no progress is made for ~90 seconds:

  * report current state
  * explain what is blocking progress
* **Do not output filler, nonsense, or placeholder text.**
* If the session state becomes inconsistent, stop and report.

---

## 7. General Behavior

* Be explicit and predictable.
* Optimize for correctness and maintainability over speed.
* Treat this file as authoritative for how work in this repository should be performed.


