<p align="center">
  <img src="assets/conductor.png" alt="Skill Conductor" width="100%">
</p>

# Skill Conductor

> A skill that creates, evaluates, and improves other skills. Meta-level.

[![Release](https://img.shields.io/github/v/release/smixs/skill-conductor)](https://github.com/smixs/skill-conductor/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Install](https://img.shields.io/badge/install-npx%20skills%20add-black)](https://skills.sh)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-d97757)](https://code.claude.com/docs/en/plugins)

Architecture-first skill lifecycle: **design → build → test → evaluate → package**.

Most skill tools jump straight to "write SKILL.md." Conductor makes you choose the architecture first — because rewriting a wrong pattern costs more than writing it right.

## Install

```bash
# skills.sh — installs into ~/.claude/skills
npx skills add smixs/skill-conductor
```

```bash
# Claude Code plugin
/plugin marketplace add smixs/skill-conductor
/plugin install skill-conductor@smixs
```

### Codex port (`codex-port`)

This fork keeps the upstream workflow and adds a Codex runtime. Install `skills/skill-conductor` from the [`codex-port` branch](https://github.com/anicim/skill-conductor/tree/codex-port/skills/skill-conductor) into `~/.agents/skills/skill-conductor` or `%USERPROFILE%\.agents\skills\skill-conductor`.

The port uses `codex exec --json` for trigger evaluation and the authenticated Codex CLI for description improvement. Run `codex login status` before those automated modes; no Anthropic API key is needed.

Codex-specific changes stay isolated in `codex-port`, so upstream updates remain visible and can be merged or rebased later.

<details>
<summary><strong>v3.2.0 — Evidence-based upgrade: form-matching, judge calibration, pressure testing</strong></summary>

- **Principle #10: Match the form to the failure** — classify the baseline failure before writing a rule; prohibitions bulletproof discipline failures but measurably backfire on shaping failures (obra/superpowers wording tests + Guardrails polarity data). Plus: no nuance clauses, exemption clauses don't scope.
- **Critique-before-verdict judges** — all three eval agents (grader, comparator, bineval) now write the detailed evidence critique BEFORE committing to the 1/0 verdict, with a borderline few-shot example in each (Hamel Husain's judge methodology).
- **Threshold-blind judging** — the BinEval judge no longer computes the overall score or the GATE; the orchestrator aggregates. A judge that knows the bar is biased toward it.
- **Automatic cross-family judge calibration** — a second judge from a different model family answers the same bank; stable disagreement flags a badly worded question, not a dispute. Self-preference-bias guard on final acceptance.
- **Variance discipline** — improvements on non-critical questions count only when they reproduce in 2 consecutive runs; the 3-iteration cap now carries its STICK rationale.
- **`references/pressure-testing.md`** — micro-test protocol (no-guidance control, 5+ reps, variance as a metric) + pressure scenarios for discipline skills (7 pressure types, forced A/B/C choice, rationalization tables).
- **Pushy description formula** — `[What] + Use when [4-5 phrasings] + "even if they don't explicitly say '<canonical term>'" + Do NOT use for [...]`, deduped to a single canonical home in Principle #2.
- **Question bank v1.1** — 5 new questions: pushy triggers, nuance clauses, directive reference loading, time-rot language, redundant-content (E:A:R).
- **Self-hosted proof** — this release was produced by Conductor evaluating and improving itself: 3 gated iterations, dual-family judges (Claude + GPT via codex), all critical questions passing.

</details>

<details>
<summary><strong>v3.1.0 — Gated self-update: held-out gate + edit budget (SkillOpt core)</strong></summary>

- **Held-out gate for body edits** — Mode 2 IMPROVE now splits evals into train/held-out (`scripts/split_evals.py`, deterministic, stratified by optional `evals[].category`). Lessons and edits come from TRAIN only; a candidate is accepted iff no held-out assertion regresses (flip-confirmation re-run for noise), train pass-rate strictly improves, and no new critical failure. Methodology borrowed from [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt).
- **Edit budget** — at most 3 atomic edits per iteration (one edit = one lesson, labeled); no wholesale rewrites, so gate rejections stay attributable.
- **Case transitions** — assertion-level diff parent→candidate (improved / regressed / persistent-fail / stable-success) recorded as an additive `transitions` block in benchmark.json.
- **Refactor** — `split_eval_set` generalized into `utils.split_evals(stratify_key=...)`; `run_loop.py` (Mode 5 OPTIMIZE) delegates to it, split unchanged bit-for-bit.

</details>

<details>
<summary><strong>v3.0.0 — BinEval scoring, English canon, dual-channel install</strong></summary>

- **BinEval evaluation** — replaces the old 5-axis 1-10 scoring with atomic binary yes/no questions across 5 dimensions (Discovery, Clarity, Structure, Robustness, Completeness). Each answer carries grounding evidence; the pass criterion is a **gate on critical questions**, not an opaque number. Adapted from *"Ask, Don't Judge"* ([arXiv 2606.27226](https://arxiv.org/abs/2606.27226)).
- **Deterministic + LLM split** — `eval_skill.py --json` emits structural checks as binary question records; an evaluator agent answers the judgment questions with evidence and a self-update loop feeds failing questions back into edits.
- **9 authoring principles** — a universal canon (pre-flight, no-process-in-description, MOC, fresh-practitioner author, TWI "why", blind-agent test, inline checklists, one-term-per-concept, cut-the-fat) in `references/sop-practices.md`, applied to every skill.
- **Dual-channel install** — one repo, one source of truth, installable via skills.sh and the Claude Code plugin marketplace.

</details>

<details>
<summary><strong>v3: SOP practices + smoke tests</strong></summary>

- **`references/sop-practices.md`** — 80 years of Standard Operating Procedure wisdom applied to skill authoring. Inline checklists at risk-points, pre-flight checks, programmatic validation, exception handling patterns. Use for procedural skills (client intake, onboarding, reporting, escalation)
- **`scripts/test_smoke.py`** — fast safety net for skill-conductor scripts themselves. Verifies critical scripts execute on known-good skills, fail on known-bad, produce expected output shapes. Run: `uv run scripts/test_smoke.py`
- Updated eval agents (grader, comparator, analyzer) with refined rubrics
- Improved `package_skill.py`, `eval_skill.py`, and schema validation
- Updated `patterns.md` and `schemas.md` with tighter definitions

</details>

<details>
<summary><strong>v2: Anthropic's eval engine meets architecture-first design</strong></summary>

Anthropic [updated their skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) with serious eval infrastructure. We took the best of it:

**From Anthropic's skill-creator:**
- 3 specialized agents: **grader** (assertion checking + claim extraction), **comparator** (blind A/B testing), **analyzer** (post-hoc root cause analysis)
- Parallel eval execution with isolated contexts (no cross-contamination)
- Automated description optimization with train/test split (60/40)
- Benchmark tracking: pass rate, tokens, time with variance analysis
- HTML eval viewer with qualitative + quantitative tabs

**What Conductor adds on top:**
- **Architecture before code.** 5 patterns (Sequential, Iterative, Context-Aware, Domain Intelligence, Multi-MCP) with selection criteria. Pick wrong = rewrite everything later
- **Degrees of freedom.** Low (deterministic scripts) → Medium (pseudocode) → High (free text). Match freedom to risk tolerance
- **TDD RED before writing.** Verify the agent fails WITHOUT the skill first. If it already handles the task — you don't need a skill
- **Quality scoring with a gate** (now BinEval — see v1.0.0). Numbers and evidence, not a "vibe check"
- **Skill categorization.** Capability uplift (teaching something new) vs Encoded preference (sequencing known abilities). Different skills need different testing strategies

</details>

## Synthesized from

1. **[Anthropic Skill Creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator)** — eval infrastructure, grader/comparator/analyzer agents, benchmark pipeline
2. **[The Complete Guide to Building Skills for Claude](https://claude.com/blog/complete-guide-to-building-skills-for-claude)** — architecture patterns, success metrics
3. **[Superpowers / writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md)** by Jesse Vincent — TDD approach, the "description trap" discovery, match-the-form-to-the-failure, the micro-test protocol, pressure scenarios and rationalization tables
4. **[Skills Best Practices](https://github.com/mgechev/skills-best-practices)** by Minko Gechev — three-stage LLM validation, eval methodology
5. **[hamelsmu/evals-skills](https://github.com/hamelsmu/evals-skills)** by Hamel Husain — critique-before-verdict judge outputs, borderline few-shot examples, judge calibration discipline
6. **[grafana/skills — skill-authoring](https://github.com/grafana/skills)** — the pushy description pattern in production, judge score-variance discipline ("three consecutive local passes before shipping")
7. **[softaworks/agent-toolkit — skill-judge](https://github.com/softaworks/agent-toolkit)** — the Expert/Activation/Redundant knowledge-delta taxonomy, directive loading triggers, the freedom-consequence test
8. **[neolabhq/context-engineering-kit](https://github.com/neolabhq/context-engineering-kit)** — threshold-blind judges (never tell the judge the bar)
9. **[trailofbits/skills — skill-improver](https://github.com/trailofbits/skills)** — the stop-hook pattern for unattended improvement loops (referenced, not implemented)

### Methodology foundations

- **[Standard Operating Procedures: A Writing Guide](https://extension.psu.edu/standard-operating-procedures-a-writing-guide)** — Richard Stup, Penn State Extension. Format selection, hierarchical vs. flowchart procedures.
- **[Procedure Writing: Principles and Practices](https://books.google.com/books/about/Procedure_Writing.html?id=Tm5RAAAAMAAJ)** — Wieringa, Moore & Barnes (Battelle Press, 1998). Imperative steps, removing modal weasel-words.
- **[Toyota TWI (Training Within Industry)](https://www.allaboutlean.com/wp-content/uploads/2019/01/TWI_Job_Instruction_Manual.pdf)** — the "Job Instruction" method: step → key point → why; the 5 Whys root-cause practice ([Job Methods manual](https://www.allaboutlean.com/wp-content/uploads/2019/01/TWI_Job_Methods_Manual.pdf), [The Roots of Lean](https://www.lean.org/downloads/105.pdf)).
- **McDonald's Operations Manual** — the canonical 600+ page SOP system; checklists at the point of use. The manual itself is proprietary; it is documented in John F. Love's [*McDonald's: Behind the Arches*](https://archive.org/details/mcdonaldsbehinda0000love).
- **[Ask, Don't Judge: Binary Questions for Interpretable LLM Evaluation and Self-Improvement](https://arxiv.org/abs/2606.27226)** — the BinEval method behind Conductor's evaluation.
- **[Guardrails Beat Guidance](https://arxiv.org/abs/2604.11088)** (5000+ Claude Code runs on SWE-bench) — rule polarity: helpful rules are negative constraints, harmful ones positive directives → Principle #10.
- **[TICK: Generated Checklists Improve LLM Evaluation and Generation](https://arxiv.org/abs/2410.03608)** — checklist as spec + eval + feedback; refinement plateaus and degrades past 3–4 iterations → the 3-iteration cap.
- **[CheckEval](https://arxiv.org/abs/2403.18771)** and **[Prosa](https://arxiv.org/abs/2605.01630)** — binary decomposition makes judges reproducible across model families → cross-family judge calibration.
- **[Self-Preference Bias in Rubric-Based Evaluation](https://arxiv.org/abs/2604.06996)** — judges favor their own family even on binary rubrics → the out-of-family acceptance rule.
- **[LLMs Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798)** and **[BIG-Bench Mistake](https://arxiv.org/abs/2311.08516)** — self-correction needs an external gate; models fix errors well only when an external checker locates them → the gated self-update loop.
- **[SkillJuror](https://arxiv.org/abs/2606.11543)** — progressive disclosure with explicit loading triggers beats both flat files and passive reference lists → directive loading rules.
- **[SkillReducer](https://arxiv.org/abs/2603.29919)** — >60% of public skill-body text changes no agent behavior → the actionability test in Principle #9.
- **[IFScale](https://arxiv.org/abs/2507.11538)** and **[Prompt Design at Scale](https://arxiv.org/abs/2607.19257)** — compliance collapses near 80 simultaneous rules; format matters less than rule count → the rule budget and MOC structure.

## 6 Modes

| Mode | What it does |
|------|-------------|
| **CREATE** | Architecture selection → TDD baseline → scaffold → write → verify → refactor |
| **IMPROVE** | Diagnose → eval loop → self-update loop (failing questions → targeted edits) → iterate |
| **VALIDATE** | Structural checks + trigger testing + BinEval scoring |
| **REVIEW** | Pass/fail quality gate for third-party skills before you install them |
| **OPTIMIZE** | Auto-tune the description for accurate triggering with a train/test split |
| **PACKAGE** | Validate structure + package as `.skill` for distribution |

## Architecture patterns

Choose before writing a single line:

| Pattern | Use when |
|---|---|
| Sequential workflow | Clear step-by-step process |
| Iterative refinement | Output improves with cycles |
| Context-aware selection | Same goal, different tools by context |
| Domain intelligence | Specialized knowledge beyond tool access |
| Multi-MCP coordination | Workflow spans multiple services |

## Eval infrastructure

```
                    ┌─────────┐
                    │  SKILL  │
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼────┐ ┌──▼───┐ ┌───▼────┐
         │ Grader  │ │ A/B  │ │Analyzer│
         │         │ │Blind │ │        │
         │assertions│ │compare│ │root    │
         │+ claims │ │      │ │cause   │
         └─────────┘ └──────┘ └────────┘
              │          │          │
              └──────────┼──────────┘
                         │
                   ┌─────▼─────┐
                   │ Benchmark │
                   │ mean±std  │
                   └───────────┘
```

Quality is scored with **BinEval**: binary yes/no questions per dimension, each answered with evidence; the skill passes when every *critical* question answers yes — not when a scalar clears a threshold.

## Installation layout

```
skills/
└── skill-conductor/
    ├── SKILL.md
    ├── agents/
    │   ├── grader.md
    │   ├── comparator.md
    │   ├── analyzer.md
    │   └── bineval.md
    ├── eval-viewer/
    │   ├── generate_review.py
    │   └── viewer.html
    ├── references/
    │   ├── patterns.md
    │   ├── schemas.md
    │   ├── sop-practices.md
    │   ├── bineval-method.md
    │   ├── quality-questions.md
    │   ├── pressure-testing.md
    │   └── runtime-setup.md
    ├── assets/
    │   └── eval_review.html
    └── scripts/
        ├── init_skill.py
        ├── eval_skill.py
        ├── run_eval.py
        ├── run_loop.py
        ├── improve_description.py
        ├── aggregate_benchmark.py
        ├── generate_report.py
        ├── package_skill.py
        ├── quick_validate.py
        ├── test_smoke.py
        └── utils.py
```

**Claude Code:** the install commands above drop it into `.claude/skills/`. Auto-activates when the agent detects a skill-building task.

## Key discovery

Never put process steps in the skill description. If your description says "exports assets, generates specs, creates tasks" — the model follows the description and skips the body. Tested experimentally.

```yaml
# ✅ Good
description: Analyze design files for developer handoff. Use when user uploads .fig files.

# ❌ Bad - model follows this and ignores SKILL.md body
description: Exports Figma assets, generates specs, creates Linear tasks, posts to Slack.
```

## License

MIT — see [LICENSE](LICENSE).
