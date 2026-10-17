# Travel expense claim

Build a reusable Agent Skill for Alderbridge Consulting's travel reimbursement workflow.

## Implemented component: independent work

The first implemented component applies the learner's captured choice to progress work whose own evidence, budget, authority and obligation dependencies are demonstrated. `src/travel_expense_claim/independence.py` propagates explicit prerequisites without treating a shared reviewer or source file as a dependency. It requires source references for all four dependency domains.

The source-backed verification is an **offline replay of retained evidence**, not a fresh-source run or a completed reimbursement workflow. From the repository root, Python 3.10 or newer with standard-library timezone data is sufficient:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m travel_expense_claim.verify_independence \
  --sources artifacts/runs/review-20261017033849Z/sources.json \
  --subject claim:C08:1 --subject claim:C01:1 --subject permit:P122:1 \
  --output artifacts/verification/choice-1/independence.json
```

The verifier checks retained hashes, reads all initial claim/evidence records and the shared budget, filters decision/Finance/cancellation deliveries by arrival before joining, and writes the requested subjects' gate results and provenance. A known business hold is a successful inspection, not a failed command. Missing, incompatible or corrupted required sources cause a nonzero exit with the error; no output is written. An identical replay preserves the existing output; a distinct result requires a new output path. Subject IDs are invocation inputs, not implementation constants.

The demonstrated results are C08 held with unknown entitlement, C01's existing accepted request awaiting settlement evidence, and P122's independent cancellation tracking with arrangements paused. Progress permission applies to the stated review/tracking scope; it does not authorize dispatch, bookings, payment or financial closure. The permit estimate is not an accepted Finance commitment, and this component does not establish its affordability for new arrangements.

The [coverage map](docs/coverage.md) records exact policy, interview, source and code/test references. Operational repair-queue organization, the full four-batch workflow and financial-completion acceptance remain pending the applicable learner decisions and implementation. A new live processing run must freshly attempt all five native sources; this offline verification does not claim to do so.

## Implemented component: full correction recheck

The learner chose a full recheck after material corrections. The scoped domestic-claim observer now rebuilds evidence, per-line Decimal arithmetic, filing eligibility, current approvals, actual shared budget/cost obligations and Finance history for every visible revision. Previous source versions and requests remain intact. Old approvals cannot authorize the current revision, and an amount-only Finance exception cannot resolve cancellation eligibility.

```bash
PYTHONPATH=src python3 -m travel_expense_claim.recheck \
  --sources artifacts/runs/review-20261017033849Z/sources.json \
  --claim C09 --claim C19 --claim C01 --claim C08 --through-batch 4 \
  --output artifacts/verification/choice-2/full-rechecks.json
```

The [focused result and source references](artifacts/verification/choice-2/report.md) explain C09's unchanged-total identity correction and C19's amount/cancellation revisions. The command also observes all visible supplied Finance commitments and separate cancellation processes, including P122 without a claim. It filters arrivals before joining current versions, decision packets and financial events. Known gaps hold the affected work; a demonstrable shared deficit or conflicting obligation holds dependent work. Exact redelivery does not duplicate money. Identical output is preserved; a distinct output requires a new path.

This is retained-source verification, not an operational snapshot writer, dispatch system or completed project Skill. International permit eligibility remains an explicit hold in this component. Current-resolution proof requires an agreeing supplied Finance event, current applicable reviews, and business time no earlier than those reviews and relevant cancellation; delivery batch alone cannot prove revision context. More ambiguous Finance evidence requires clarification rather than inferred authority. Financial-completion acceptance and repair-queue organization remain learner choices 3 and 4.

## Start

1. Read the [full Project D task](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98) for the scope, workflow and deliverables.
2. Use **Use this template → Create a new repository** on [GitRollTraining/travel-expense-claim](https://github.com/GitRollTraining/travel-expense-claim), then clone your own repository and work there.

## Supplied files

```text
README.md
snapshot.schema.json
```

The [snapshot schema](snapshot.schema.json) defines the required retained batch-state format. Create the Skill, outputs and checks required by the task, and replace this README with your actual setup, run, replay and handoff instructions while preserving the entry links and Interview rule.

## Before you work

No implementation or runtime is supplied; choose and document the dependencies your Skill needs. Follow the shared [Setting Up entire.io for a Project](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details) lesson and verify actual session capture before assessed work.

Use [Project D in Work Sim](https://work-sim.catalyte.ai/s/project-d-travel-expense-claim) for your stakeholder interview and obtain relevant business source links and context there. Read native business sources during each new run and retain the content actually used as the task requires.

**Interview rule.** You conduct the stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored.

- Export your interview as the original Work Sim Markdown, save one final complete file per session under `interviews/`, and commit and push it with your code. Do not rewrite the export. If the export is unavailable, contact the facilitator.
