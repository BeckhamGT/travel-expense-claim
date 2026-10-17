# Full correction recheck: focused result

The user's full-recheck choice was recorded in `docs/coverage.md` before implementation. This result is an offline replay of retained SRC-D-3 / POL-2026.2 evidence at the exercise clock, **2026-11-15 Europe/Amsterdam**. It does not declare financial completion or consume operational batch snapshots. The source manifest SHA-256 remains `23895ede4a65fa089ad8b73812b9182e4f1d8aff85516aa5d93d4b8a43aff5a5`.

| Case / availability | Current evidence and arithmetic | Current approvals / Finance observation |
|---|---|---|
| C09 r1, batches 1–2 | T09 / COST-09, supported EUR 80 | Administration approves; budget owner returns. No request or payment observed. |
| C09 r2, batch 3 | T09B / COST-09B, independently rematched receipt and settled merchant payment; still EUR 80 | Three new exact-revision approvals. REQ-C09 accepted for EUR 80; paid EUR 0. Old approvals are history. |
| C09 r2, batch 4 | Same current basis | One EUR 80 transfer on REQ-C09. No duplicate request; no earlier-request correction to resolve. |
| C19 r1, batches 1–2 | Gross/allowed EUR 100 | Original approvals/request retained; EUR 100 transfer first becomes visible in batch 2. |
| C19 r2, batch 3 | Gross EUR 100; bound amount-only exception calculates EUR 80. TC019 is confirmed. | Held: cancellation disposition missing, current reviews omit TC019, Finance resolution absent, EUR 20 overpaid. Adjustment changes obligation, not money. |
| C19 r3, batch 4 | Explicit Finance disposition binds C19/r3/COST-19/TC019 and retains EUR 80 | Fresh cancellation-aware approvals; original EUR 100 transfer less linked EUR 20 confirmed refund gives EUR 80 net. Matching Finance resolution observed. Recheck supported; final acceptance remains pending. |

All three C19 revisions and both C09 revisions remain linked to original source pages. No request, approval or transfer was created by this verification. A fully supported recheck does not authorize renewed travel: T19 revision 1 remains retired for future arrangements.

## Exact source records

Source IDs and row/page references below resolve through the unchanged [five-source manifest](../../runs/review-20261017033849Z/sources.json). The [policy](../../runs/review-20261017033849Z/retained/policy.txt) is POL-2026.2; paragraph numbers count the sixteen paragraphs after its title.

- **Revalidation and money rules:** policy ¶2–3 (paid evidence, arithmetic, exact exceptions), ¶5–8 (filing/current source and role bindings/material changes), ¶9–11 (stable requests, admitted transfers/refunds, explicit resolution), ¶12 (independence), ¶13–16 (separate cancellation, current disposition/reviews and Finance consequences). Interview lines 397–429 describe correction handling; the user's captured choice selects full recheck.
- **C09:** INITIAL p9; UPDATES p1; RECEIPTS pp5/12; Trips rows 14/29; Merchant payments rows 13/28; Review ledger and Review packets rows 31–32 (r1) and 58–60 (r2). Finance activity row 46 is `F-C09-accepted`, batch 3; row 29 is `F-C09-1`, batch 4. September 3 occurrence dates on the new replies do not import them before batch 3 or make their explicitly bound new revision stale.
- **C19:** INITIAL p19; UPDATES p2 (r2, empty covered issues) and p7 (r3, exact TC019 coverage); RECEIPTS p10; Trips row 24; Merchant payments row 23; Review ledger/packets rows 50–52 (r1), 61–63 (r2, missing cancellation context), 310–312 (r3, TC019 context). Travel cancellations rows 12–13 establish employee request `TC019-requested` and later supervisor confirmation `TC019-confirmed`. Finance activity rows 44/22/23/24/25 establish acceptance, original transfer, adjustment, linked refund and resolution respectively; `F-C19-3` explicitly refunds `F-C19-1`, and `F-C19-4` resolves EUR 80.
- **Independent controls:** C01 INITIAL p1 / RECEIPTS p1 / Merchant payments row 6 / reviews rows 6–8 / Finance acceptance row 33 and batch-2 settlement row 6. C08 INITIAL p8 / RECEIPTS p4 lacks settled COST-08 proof in the complete Merchant payments tab. P122 is Trips row 128 / reviews rows 301–303 / cancellation rows 6–7, with exact confirmation redelivery at row 14; no claim is created.

## Verification

`PYTHONPATH=src python3 -m unittest discover -s tests -q`: **97 tests passed**. The 19 full-recheck tests supplement authority, cancellation, exact arithmetic, Finance-admission and initial-independence checks. The [machine result](full-rechecks.json) records four cumulative batch observations with source refs and owned issues.

- Batch 1 is identical when replayed alone or as the prefix of all four batches. A malformed batch-4 exception cannot alter batch 1 or hold unrelated C01. Current malformed monetary data stays unknown for the affected claim.
- C09's unchanged total still triggers new trip/cost evidence and fresh exact-revision approvals. C19 r2 cannot borrow r1 approvals or r3 cancellation coverage; r3 cannot reuse a wrong actor, cost, revision, cancellation ID or pre-confirmation packet.
- Admitted transfers survive revisions, invalid deliveries and conflicts. Refunds require a prior exact transfer and cannot exceed its unrecovered amount. Exact `F-C01-1` redelivery has one monetary effect. A late-imported old resolution cannot establish current-revision resolution merely through its arrival batch.
- C01 remains supported through all four batches; C08's unsupported entitlement remains null, with EMP-01 responsible for matching settled proof. P122 cancellation stays independent and paused/retired as its supplied state requires; no C122 claim appears. Unrelated C18's known late transfer is charged to budget without imposing its own reconciliation hold on C01/C09/C19.
- Budget charges each accepted obligation once, retaining actual expenditure when it exceeds a corrected obligation: C19 charges EUR 100 until its confirmed refund, then EUR 80. Shared remaining funds are **316585 / 315585 / 304585 / 296585 cents** across the four batches. Isolated real deficits, conflicting commitments and shared accepted costs hold the dependent work; superseded unaccepted costs alone do not.
- Cancellation conflicts remain attached through established event/process identity even if a conflicting delivery changes its trip. Invalid records for a different exact trip revision do not hold the current one. Original retained source, interview and choice-1 result bytes remain unchanged; identical replay preserves output.

Current-resolution corroboration is deliberately explicit because Finance rows have no claim-revision field: current amount and applicable reviews, event availability, and business chronology must agree. This observer holds ambiguous future cases for a supplied Finance clarification; it does not infer a universal resolution binding from batch number alone. International permit eligibility, operational sealed snapshots, repair-queue organization and financial-completion acceptance are outside this scoped component.

## Remote and capture check

Entire reports **Enabled**, agent **Codex**, checkpoint sync target **origin**, and the active root session. The previous commit `fe6aa27532edea504e26c8cb5c349813d4e12391` has local checkpoint `01M5420G39TKTVAF2QVFVX7HF8`; its actual Git ref contains session metadata, prompt and full transcript.

The successful read-only remote query advertised only starter `main` at `c3b2f46ce3d3294735e5c51b19e0cb2e98b228ea`, with no Entire checkpoint refs. **The previous commit and checkpoint are not remotely synchronized.** See [remote evidence](remote-sync.json). No push or approval change was performed. Publication remains the next remote step requiring the user's authorization.
