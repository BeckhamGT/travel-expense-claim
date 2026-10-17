# Project D: Travel expense claim

Reusable [Agent Skill](skills/travel-expense-claim/SKILL.md) for Alderbridge Consulting's complete supplied travel-permission, claim review, repair and Finance-reconciliation exercise. The company and replies are fictional; the implementation prepares local work and consumes supplied facts, with approvals, exceptions, bookings and payments remaining human-owned.

The [assignment](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98), [public template](https://github.com/GitRollTraining/travel-expense-claim) and supplied [snapshot schema](snapshot.schema.json) define the submission. [Coverage and adoption](docs/coverage.md) distinguish actual verification, legitimate owned business holds and unfinished work. The original interview is preserved under `interviews/`.

## Setup

Python 3.10 or newer with timezone data is required. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The processing dependency is pinned `jsonschema`; all arithmetic, event reduction, queue management and output generation otherwise use the standard library. Native acquisition uses supported browser/Drive tools. PDF extraction and workbook cross-checking additionally use `pypdf` and `openpyxl` (the Codex bundled runtime already supplies them); install those only when needed for a new collection. See [source acquisition and resume](docs/source-acquisition.md).

Follow the course's [Entire setup lesson](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details). Verify `entire status` reports Enabled, Codex and sync target origin, then inspect a real commit-linked checkpoint. Configuration alone is insufficient. Genuinely missing assessed capture requires facilitator repair before further assessed implementation.

## Full-source preview and final run

The fresh collection is `artifacts/runs/submission-20261017T154939Z/sources.json`. It covers all five native locations: three complete PDFs (120/7/102 pages), 16 policy paragraphs and all ten populated workbook tabs. All 13,703 populated native workbook values match the fresh XLSX export. The policy's supplied old-version URL resolves to POL-2026.2. The exercise clock is **2026-11-15 Europe/Amsterdam**; local calendar dates and UTC event timestamps retain their distinct meanings.

Preview the real result before learner financial-completion adoption:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow preview \
  --sources artifacts/runs/submission-20261017T154939Z/sources.json \
  --output-dir artifacts/runs/submission-20261017T154939Z/inspection
```

The retained `preview/report.md` is the original inspection result; later implementation refinements preserve it. The command above writes the current `inspection/report.md`. An identical replay is preserved; for a distinct preview use another `--output-dir` rather than overwrite either result. Sealed run paths remain fixed under the manifest's run directory.

Only **after the learner's captured choice 3** accepts the financial-completion conditions and full delivery scope, seal all observed arrival batches:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow seal \
  --sources artifacts/runs/submission-20261017T154939Z/sources.json \
  --completion-accepted
```

The adoption flag supplies no evidence, review, Finance event or payment. Every case must independently satisfy the source conditions. Legitimate unresolved cases remain owned and traceable; they do not reduce the assigned all-record scope.

The run writes:

- `batches/1.json` through `batches/4.json`: UTF-8 `travel-claim-snapshot/2` snapshots, exact source hash and immediate predecessor chain.
- `claims.csv`: exactly one current row per claim and the required nine columns; unknown money is blank. Cancellation processes without claims never create claim rows.
- `report.md`: operations handoff, full amounts/states, owned next evidence/actions and significant batch/queue updates.
- `repair-queue.json`: per-subject/revision/fact items, owner-based views, unsent local drafts, evidence-verification records and preserved history.
- `summary.json`: independently checkable batch totals and cardinalities.

Every source revision, receipt/paid proof, calculation, decision packet, accepted request, transfer/refund and cancellation has retained provenance. Current entitlement and current authorized obligation are distinct where withdrawal, rejection or a later correction changes the obligation. Prepaid costs are explicitly linked and excluded from the new obligation. Business cancellation never releases a Finance commitment by itself.

## Verification and unchanged replay

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow verify \
  --sources artifacts/runs/submission-20261017T154939Z/sources.json \
  --completion-accepted
git diff --check
```

`verify` reconstructs every cumulative batch from retained history, compares exact sealed bytes, validates Draft 2020-12 with explicit RFC3339 date-time checks, verifies all retained source/predecessor hashes and references, and checks CSV/queue/report/summary agreement. It performs no fresh native read and changes no output: this is an **offline replay**. Same input and implementation preserve event/request identity and money; distinct sealed content is rejected.

Tests include the ordinary path across twelve employees, strict thresholds, caps/FX/per-line rounding, deadlines and filing-before-payment, exact review/role/source bindings, unknown evidence/definitions, returns and partial repairs, withdrawals/rejections, corrections, prepaid links, partial settlements/retries, linked refunds, overpayments, later transfers and separate no-claim cancellations. Isolated adverse fixtures supplement the complete native primary run.

Earlier `choice-1` and `choice-2` verification artifacts are preserved historical outputs of their original commits. They are not final operational snapshots; a newer implementation must not overwrite their distinct result bytes.

## Success, partial results and failure

Exit zero means the requested processing/verification operation completed, including legitimate held/pending business cases. It does not mean every claim is paid or every obligation closed. Read `report.md` and the queue for exact owner, fact, source/revision and next action.

Missing/corrupt required source bytes, incompatible layouts, invalid manifest/schema/chain/reference state or distinct existing sealed content cause a nonzero error naming the failing prerequisite. Keep the evidence and failed acquisition observation. Raise missing definitions or access with Finance/lead/facilitator; do not guess or label unimplemented checks as business uncertainty. No retry changes approvals, sends requests, books travel or moves money.

## Resume and handoff

For a new authorized source batch, attempt all five native locations again and retain complete relevant version/event history in a new run. Add `prior_run` and `change_reason` to its manifest. Run the same preview/seal/verify commands with its actual manifest path; the runner observes all supplied positive arrival numbers in order. Revisit adopted constraints when changed evidence alters their basis. A corrupt predecessor can be diagnosed or rebuilt from complete retained history in a new explicitly linked run; preserve the original and never invent historical execution times.

Before submission, commit all required files, inspect the actual `Entire-Checkpoint` trailer plus its Git ref/full transcript, publish code and checkpoint refs when authorized, and compare their origin objects. Entire's installed pre-push hook synchronizes the real checkpoint refs alongside `git push origin main`. Public repository visibility permits reading code/interview evidence; facilitator-specific account/tool access is reported only to the extent actually verified. Prepare the repository URL, full commit, run/report and real capture refs for the learner's Classroom private comment. The learner submits.

**Interview rule.** You conduct the [Project D Work Sim](https://work-sim.catalyte.ai/s/project-d-travel-expense-claim) stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored. Export one final complete original Work Sim Markdown per session under `interviews/`, without rewriting it, and commit/push it with the code. If the export is unavailable, contact the facilitator.
