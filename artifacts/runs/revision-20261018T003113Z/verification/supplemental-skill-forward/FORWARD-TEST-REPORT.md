# Supplemental offline Skill forward-test

Evidence directory: `/private/tmp/travel-skill-forward-c7xz9wyg`

This is an isolated offline forward-test of the Agent Skill and README, using the retained corpus from `artifacts/runs/revision-20261018T003113Z/sources.json`. No fresh native access occurred. The real repository, runs, interview and publication were not modified by this test; no external messages, bookings, approvals or financial actions were made.

## Copy and runtime

Copied current code, Skill, README, docs, schema, requirements and unchanged original interview into `/private/tmp/travel-skill-forward-c7xz9wyg/workspace`. Copied all 21 bound retained files and source-read-verification evidence into a distinct test run. All 21 retained source hashes matched before processing. The copied test manifest is explicitly labelled supplemental offline data; its exact prior link binds a preserved copy of the original revision manifest, whose original prior manifest was also retained. Historical file observation metadata remains historical and is explicitly identified as such.

Test run: `offline-skill-forward-test-20261018T004145Z`. Source manifest: `/private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json`.

The system `python3` did not have jsonschema. Used the existing repository virtualenv interpreter read-only; its pinned `jsonschema` version is 4.25.1. Every operational invocation sets `PYTHONDONTWRITEBYTECODE=1`, with `PYTHONPATH=src` and cwd in the temporary copy. This shares only the installed runtime/dependency, not processing state or implementation paths. Copied input fidelity check: 22/23 files still match the repository at the end of this test; the sole difference is `docs/coverage.md`, changed elsewhere during this concurrent test. All copied Python source, Skill, README, schema, requirements and original interview still match. This test made no real-repository writes.

## Separate stops and observed results

| Observation | After batch 1 | After batch 2 |
|---|---:|---:|
| Current / next cursor | 1 / 2 | 2 / 3 |
| Claims | 120 | 120 |
| Finance events available | 100 | 200 |
| Original accepted obligation cents | 1183415 | 1183415 |
| Gross / net confirmed paid cents | 0 / 0 | 1153915 / 1153915 |
| Confirmed refund cents | 0 | 0 |
| Closed reimbursed claims | 0 | 95 |
| Open repair items | 65 | 70 |

Both consumption commands exited zero with `state: awaiting-explicit-continuation`. Batch 1 produced only `batches/1.json` and `stages/1/`; only after intentional batch-2 continuation did `2.json` and `stages/2/` appear. No batch 3 or 4 was consumed. Batch-1 sealed files retained their exact bytes and nanosecond mtimes after batch 2.

Owner counts after batch 1: ADMIN-01 19, SUP-01 18, LEAD-01 14, FIN-01 9, EMP-01 2, EMP-03 2, DIR-01 1. After batch 2: ADMIN-01 20, SUP-01 16, LEAD-01 15, FIN-01 14, EMP-01 2, EMP-03 2, DIR-01 1. These are repair-item counts, not the total count of claims awaiting ordinary settlement. The handoff separately lists current claims and owners.

I inspected the queue after each stop. C09's return preserves LEAD-01 as returning reviewer while EMP-01 owns revised trip evidence. C21's funding return belongs to directory budget owner LEAD-01. C08 remains held with unknown entitlement and EMP-01 paid-proof work. Missing rates/caps/category definitions remain FIN-01 work. C119's EUR 1000.01 entitlement awaits DIR-01. C01 changes from pending/unpaid in batch 1 to closed reimbursed at 10000 cents in batch 2. C20 retains the 11000-cent payment, -1000-cent balance and two distinct open Finance items (refund/overpayment fact and explicit resolution); future refund/resolution inputs were not consumed.

For batch 2 I selected the real TC122 repair item `RQ-d506ea23d238f50ef3326f3a` from the batch-1 queue. Supplied row-7 supervisor confirmation resolves exactly that item. TC122 is confirmed with no financial effect, no affected claim and no reimbursement request. Other claims proceed independently. All local drafts remain `sent: false`.

## Unchanged replay and verification

The second batch-2 invocation uses exactly the same command and arguments as its first invocation. It returned `replay: true`, retained cursor 2 / next 3 and preserved all **40 run files** with identical SHA-256 and `st_mtime_ns`, no additions or removals. This covers sources, retained bytes, snapshots, stage views, operation records and top-level current projections. `verify` then exited zero with `verified_batches: [1, 2]`; it likewise changed no run file bytes/mtimes.

Additional independent checks parsed the retained native effective values directly, without importing implementation modules. They reconciled all batch-1/2 Finance event IDs and accepted/settled/refund totals, per-claim money identities, all closed-reimbursed current-review/obligation/payment conditions, queue owner-view membership, all 120 CSV rows with nine columns and blank unknown amounts, report item presence, source/predecessor hashes, version-arrival prefix bounds, TC122 no-claim behavior and C09/C21 returning-reviewer/provider ownership. The first supplemental checker draft assumed an incorrect queue field name; that checker was corrected from the actual artifact and then passed. No product fix was required.

## Instructions and presentation feedback

The Skill and README were sufficient to run seal, status, one intentional continuation, replay and verify without reading implementation internals or prior implementation guidance. There was no blocking missing instruction. The explicit task scope to stop after two batches took precedence over the Skill's ordinary full-four-batch completion instruction.

Nonblocking wording observations:

- On replay, stdout reprints the original stored `resumed_tasks` open-to-resolved transition while also reporting `replay: true`. A reader should understand that this is stored operation history, not a second resolution. Naming this stored replay history would be clearer.
- Queue evidence responses say `Fresh applicable-version observation proves this fact` in this explicitly offline retained-source run. The accompanying manifest and handoff make supplied facts clear, but `current applicable-version supplied evidence` would avoid any accidental impression of fresh native retrieval.
- `open_work_by_owner` counts repair items; ordinary settlement waits appear in the claim handoff rather than that repair count. Describing the count as open repair work would remove ambiguity.

These are clarity suggestions, not business-rule failures established by this forward-test. Successful prefix reconstruction and selected independent checks do not prove every business rule correct. Later correction/refund/resolution arrivals 3–4 and recovery were intentionally outside this test; no fresh source access or real-world financial authority is asserted. I did not rerun the entire unit suite because the delegated request was an operational Skill forward-test and the parent separately verifies the suite.

## Exact operational commands

The following is the execution log. Stdout/stderr are separately retained as numbered files in this directory; fingerprint and independent-check JSON files provide the assertions behind this report.

```text
Setup: python3 heredoc copies src, skills, docs, README.md, snapshot.schema.json, requirements.txt, AGENTS.md, original interview, all 21 retained manifest files, source-read-verification.json, original manifest and linked prior manifest. Copied manifest receives distinct offline test run_id and exact prior link.
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow seal --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json --batch 1 --completion-accepted
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow status --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow continue --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json --batch 2 --task RQ-d506ea23d238f50ef3326f3a --completion-accepted
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow status --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json --task RQ-d506ea23d238f50ef3326f3a
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow continue --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json --batch 2 --task RQ-d506ea23d238f50ef3326f3a --completion-accepted
cwd=/private/tmp/travel-skill-forward-c7xz9wyg/workspace
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/user/fellowship/travel-expense-claim/.venv/bin/python -m travel_expense_claim.workflow verify --sources /private/tmp/travel-skill-forward-c7xz9wyg/workspace/artifacts/runs/offline-skill-forward-test-20261018T004145Z/sources.json --completion-accepted
cwd=/private/tmp/travel-skill-forward-c7xz9wyg
python3 independent_checks.py
```
