# AGENTS.md

## Source of Truth

`docs/plan/personal-quant-lab-v01-plan.md` is the frozen implementation plan for Personal Quant Lab v0.1.

The plan is authoritative for:

- architecture decisions D1–D10;
- milestone scope and ordering;
- schemas and lifecycle semantics;
- validation rules;
- acceptance criteria.

Do not silently reinterpret, simplify, replace, or redesign frozen decisions.

## Execution Protocol

Work on exactly one milestone at a time.

Before changing code:

1. Read the full frozen plan.
2. Identify the active milestone.
3. Read all global decisions referenced by that milestone.
4. Inspect the current repository state and previous milestone evidence.
5. State any conflict between the repository and the frozen plan before implementing.

During implementation:

- Stay within the active milestone unless a minimal prerequisite change is strictly necessary.
- Do not implement later milestones early.
- Do not change frozen architecture to make implementation easier.
- Do not weaken tests, gates, validation rules, or invariants to make them pass.
- Do not silently substitute libraries, APIs, data semantics, or algorithms.
- If an external API differs from the plan, verify the actual API and document the discrepancy.
- Prefer deterministic tests over assumptions.

## Plan Deviations

If the plan cannot be implemented as written:

STOP that part of the implementation.

Record:

- the conflicting plan section;
- observed evidence;
- affected files;
- proposed resolution;
- whether remaining milestone work can safely continue.

Do not make a product or architecture decision on the user's behalf.

## Milestone Completion

A milestone is complete only when:

- every required task in that milestone is implemented;
- every milestone-specific verification passes;
- the full applicable regression suite passes;
- lint/check commands required by the plan pass;
- no known plan deviation remains hidden;
- an execution report is produced.

Do not begin the next milestone.

## Completion Report

At the end of the active milestone report:

- implemented plan items;
- files changed;
- tests and commands actually executed;
- exact test results;
- deviations or unresolved risks;
- evidence paths;
- Git status.

Stop after the report and wait for review.
