# Project D: Travel expense claim

Reusable [Agent Skill](skills/travel-expense-claim/SKILL.md) for Alderbridge Consulting's complete supplied travel-permission, claim review, repair and Finance-reconciliation exercise. The company and replies are fictional; the implementation prepares local work and consumes supplied facts, with approvals, exceptions, bookings and payments remaining human-owned.

The [assignment](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98), [public template](https://github.com/GitRollTraining/travel-expense-claim) and supplied [snapshot schema](snapshot.schema.json) define the submission. [Coverage and adoption](docs/coverage.md) distinguish actual verification, legitimate owned business holds and unfinished work. The [final complete interview export](interviews/project-d-travel-expense-claim-20261018-0547.md) is preserved byte-for-byte under `interviews/`; earlier exports of the same conversation remain in Git history.

## Setup

Python 3.10 or newer with timezone data is required. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The processing dependency is pinned `jsonschema`; all arithmetic, event reduction, queue management and output generation otherwise use the standard library. Native acquisition uses supported browser/Drive tools. PDF extraction and workbook cross-checking additionally use `pypdf` and `openpyxl` (the Codex bundled runtime already supplies them); install those only when needed for a new collection. See [source acquisition and resume](docs/source-acquisition.md).

Follow the course's [Entire setup lesson](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details). Verify `entire status` reports Enabled, Codex and sync target origin, then inspect a real commit-linked checkpoint. Configuration alone is insufficient. If capture appears incomplete, inspect actual root and child JSONL payloads separately from exact-token accounting metadata, diagnose supported recovery, and report any genuinely unavailable assessed records.

## Current linked run and preserved assessment

The assessed revision is `d11fb0607cded870f51308226cdc2db686460c0a`; its [original handoff](artifacts/runs/submission-20261017T154939Z/report.md), sources and snapshots remain unchanged, and its original interview remains in Git history. Its 79.1/100 assessment prompted targeted continuation, recovery and repair-ownership corrections; private “No evidence” checkpoints are not inferred from that score.

The current collection is `artifacts/runs/clarification-20261018T054954Z/sources.json`, linked by `prior_run` path/hash to technical revision run `revision-20261018T003113Z` at commit `917838bf6d0e1534b53da193b73883a8de4ce7e5`. Fresh native access again covers all five locations, 229 PDF pages, 16 policy paragraphs and ten tabs; 13,703 values match the fresh XLSX. Native business content is unchanged. A separate original-interview binding supplies the explicit entertainment-to-personal classification and exercise-operator ownership of missing definitions. It supplies no claim approval. The old policy slug resolves to POL-2026.2. The exercise clock remains **2026-11-15 Europe/Amsterdam**.

The new run has now consumed all four batches in separate invocations. See its [operational report](artifacts/runs/clarification-20261018T054954Z/report.md) and [before/after verification](artifacts/runs/clarification-20261018T054954Z/verification/report.md). The full suite passed 224 tests; independent source reconciliation found no mismatches, and offline replay preserved all 69 files then present. C117 is now pending three reviews at EUR40, with no payment or approval invented. The earlier technical fixes were retained. [Three missing numeric definitions](docs/follow-up-topics.md) remain operator/facilitator follow-up for C22, C23 and C116. No assessment resubmission has been made.

All four learner choices remain adopted in the real captured conversation. Changed evidence would require revisiting affected choices; a new run alone does not invent a new learner decision. The financial-completion flag supplies no evidence, review, transfer or approval.

## Preview, consume one batch, then wait

Preview is unsealed inspection of a selected retained-source prefix. It consumes no operational batch:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow preview \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json \
  --through-batch 1 \
  --output-dir artifacts/runs/clarification-20261018T054954Z/inspection/batch-1
```

Start only batch 1. The command seals its state/view, reports owned waiting work and exits. It does not consume batches 2–4:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow seal \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json --batch 1 \
  --completion-accepted
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow status \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json
```

Continue only when the next supplied arrival is intentionally consumed. These exact native C20 task IDs demonstrate separate partial facts; obtain other task IDs from the queue/status, never guess them:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow continue \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json --batch 2 --completion-accepted
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow continue \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json --batch 3 \
  --task RQ-65c94a8a3837096ec1a0f284 --completion-accepted
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow status \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json \
  --task RQ-e20eaf20f448b036b947421a
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow continue \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json --batch 4 \
  --task RQ-e20eaf20f448b036b947421a --completion-accepted
```

Batch 3 proves C20's linked refund and resolves only its overpayment fact; its separate Finance-resolution item and claim remain held despite zero balance. Batch 4 supplies the actual resolution. `--task` traces that existing item's before/after state; independent work still progresses under choice 1. Later batches are fixed exercise inputs, not responses caused by local drafts.

The run writes:

- `batches/1.json` through `batches/4.json`: UTF-8 `travel-claim-snapshot/2` snapshots, exact source hash and immediate predecessor chain.
- `claims.csv`: exactly one current row per claim and the required nine columns; unknown money is blank. Cancellation processes without claims never create claim rows.
- `report.md`: current operations handoff, amounts/states, owned next evidence/actions, missing-definition escalations and queue changes.
- `repair-queue.json`: per-subject/revision/fact items, owner-based views, unsent local drafts, evidence-verification records and preserved history.
- `summary.json`: independently checkable batch totals and cardinalities.
- `stages/<batch>/`: immutable CSV/report/queue/summary and `operation.json` for each actual consumption, including resumed tasks and actual UTC observation time.
- `run-state.json`: source/implementation hashes, consumed cursor and sealed-file bindings. Top-level outputs are validated current projections of the latest stage; earlier stage views remain sealed.

Every source revision, receipt/paid proof, calculation, decision packet, accepted request, transfer/refund and cancellation has retained provenance. Current entitlement and current authorized obligation are distinct where withdrawal, rejection or a later correction changes the obligation. Prepaid costs are explicitly linked and excluded from the new obligation. Business cancellation never releases a Finance commitment by itself.

## Verification and unchanged replay

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow verify \
  --sources artifacts/runs/clarification-20261018T054954Z/sources.json \
  --completion-accepted
git diff --check
```

`verify` reconstructs only consumed prefixes and validates every sealed stage, predecessor, source/prior-run binding, implementation hash and current projection. It performs no fresh native access or mutation: this is an **offline replay**. Repeating an already consumed `continue --batch N` with identical inputs is also a no-op; it preserves bytes/mtimes and never moves the cursor backward. A changed implementation requires a new linked run; use the graded commit's original code to reproduce its historical runner.

Replay stdout echoes the stored `resumed_tasks` transition; `replay: true` means it did not perform that transition again. `open_work_by_owner` counts open repair items; ordinary settlement waits also appear in the claim handoff. Queue `proven_facts` retains the original requested issue label: a resolved overpayment item means evidence addressed that issue, not that an overpayment remains true. Its source references, history and current money establish the result. “Fresh applicable-version observation” in an offline replay means a current applicable source observation, not another native fetch or a human reply.

Tests include the ordinary path across twelve employees, strict thresholds, caps/FX/per-line rounding, deadlines and filing-before-payment, exact review/role/source bindings, unknown evidence/definitions, returns and partial repairs, withdrawals/rejections, corrections, prepaid links, partial settlements/retries, linked refunds, overpayments, later transfers and separate no-claim cancellations. Isolated adverse fixtures supplement the complete native primary run.

Earlier `choice-1` and `choice-2` verification artifacts are preserved historical outputs of their original commits. They are not final operational snapshots; a newer implementation must not overwrite their distinct result bytes.

## Success, partial results and failure

Exit zero means the requested processing/verification operation completed, including legitimate held/pending business cases. It does not mean every claim is paid or every obligation closed. Read `report.md` and the queue for exact owner, fact, source/revision and next action.

Missing/corrupt required source bytes, incompatible layouts, invalid manifest/schema/chain/reference state or distinct existing sealed content cause a nonzero error naming the failing prerequisite. Keep the evidence and failed acquisition observation. Raise missing definitions or access with Finance/lead/facilitator; do not guess or label unimplemented checks as business uncertainty. No retry changes approvals, sends requests, books travel or moves money.

## Explicit recovery and human follow-up

Missing/corrupt snapshots, stage views, projections, cursor, changed implementation or interrupted publications fail before continuation. `seal` cannot silently adopt or recreate historical files. Preserve the damaged run. Obtain fresh attempts at all five locations and complete history in a **distinct** run, with `prior_run: {run_id, path, sha256}` binding the prior `sources.json` and a nonempty `change_reason`. Then:

```bash
PYTHONPATH=src .venv/bin/python -m travel_expense_claim.workflow recover \
  --sources artifacts/runs/<new-fresh-run>/sources.json \
  --from-run artifacts/runs/<damaged-run>/sources.json \
  --through-batch 2 --completion-accepted
```

Recovery reconstructs complete retained history through the explicitly selected batch in the new run. Its operations record actual recovery times and the old source binding; they do not invent historical execution times or repair the old files. Continue from that new cursor normally. This schema supports batches 1–4; a later batch requires a separately verified schema/implementation revision.

[Prioritized follow-up topics](docs/follow-up-topics.md) identify missing GBP FX, applicable lodging caps and entertainment treatment. Those cases remain unknown/held. Finance owns the definition; the learner raises package omissions with the lead/facilitator. An unsent draft is not evidence that clarification was obtained. Returned reviewers and evidence providers remain distinct. Hypothetical Finance recovery fixtures are supplemental, never supplied outcomes for C18.

Before submission, commit all required files, inspect the actual `Entire-Checkpoint` trailer plus its Git ref/full transcript, publish code and checkpoint refs when authorized, and compare their origin objects. Entire's installed pre-push hook synchronizes the real checkpoint refs alongside `git push origin main`. Public repository visibility permits reading code/interview evidence; facilitator-specific account/tool access is reported only to the extent actually verified. Prepare the repository URL, full commit, run/report and real capture refs for the learner's Classroom private comment. The learner submits.

**Interview rule.** You conduct the [Project D Work Sim](https://work-sim.catalyte.ai/s/project-d-travel-expense-claim) stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored. Export one final complete original Work Sim Markdown per session under `interviews/`, without rewriting it, and commit/push it with the code. If the export is unavailable, contact the facilitator.
