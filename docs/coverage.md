# Project D requirements and evidence coverage

Status: source review complete; implementation and business-run verification pending. This map records requirements and coverage, not learner decisions. No arrival batch has been consumed. The four learner choices remain for the captured conversation, with financial-completion acceptance after a real result.

## Evidence retained

- Original interview: `interviews/project-d-travel-expense-claim-20261017-0334.md`, 549 lines, 133 message headings, 29,179 bytes. Copied unchanged and read in full. SHA-256: `8099acf7f137edf8521c50b3d80c1dd76fe6a4dd175356fa7b1648199b1606e2`.
- Collection run: `artifacts/runs/review-20261017033849Z/`. Its `sources.json` binds all retained content to all five native URLs. It is a source-review collection, not a completed processing run. The originals, native CellData, and extraction derivatives are distinguished in the manifest.
- Policy: the supplied POL-2026-1 URL resolves to **POL-2026.2**, also named throughout the review packets/ledger. `retained/policy.txt` preserves the title and 16 complete paragraphs, with paragraph wording cross-checked against browser-visible text after whitespace normalization. Policy citations below count paragraphs after the title.
- Three SRC-D-3 PDFs: initial claims 120 pages, updates 7 pages, receipts 102 pages. Every page was extracted and read, with representative pages visually checked. They contain 127 claim-version records for 121 distinct claims and 203 distinct expenses/receipts. These counts describe inputs, not approved or payable outcomes.
- SRC-D-3 workbook: complete XLSX export, all ten visible tabs, all populated rows/columns, and bounded native CellData reads. All 13,703 populated native values match the export, including numeric and date/time representations. No formulas, comments, hidden sheets/rows/columns or external links were found. Retained original representations preserve precision; extracted row views are supplemental.

## Coverage map

Implementation locations below are proposed component responsibilities under `skills/travel-expense-claim/`; none exists yet. Verification marked pending has not been performed. The existing public `snapshot.schema.json` remains authoritative.

| Requirement / rule | Interview or native source | Implementation location | Verification evidence | Remaining gap |
|---|---|---|---|---|
| Original interview fidelity | Interview metadata and every message | Required `interviews/*.md` | Exact byte equality and SHA-256 verified against supplied Downloads file | Include unchanged export in final submitted revision |
| Fresh reads, complete retained evidence, source binding | Assignment; all five URLs; collection `sources.json` | Pending source acquisition/manifest component | Three PDF lengths match Drive metadata; every page read; ten live tabs match export; all policy paragraphs checked | Repeat fresh acquisition for any new run; source review makes no processing claim |
| Fixed case clock; date and arrival semantics | Interview 265–297; policy ¶1, ¶5, ¶14; workbook row 3 notes | Pending batch/date handling | Source inspection confirms 2026-11-15 Europe/Amsterdam, local calendar dates and UTC events | Four ordered snapshots and tests pending; no later-batch leakage |
| Receipt plus settled employee payment | Interview 87, 212, 329–345; policy ¶2 | Pending evidence matcher | All claimed receipt references exist; C08 lacks COST-08 merchant payment; C01 has settled payment at Merchant payments row 6 | Test exact identity/currency/gross match, missing and ambiguous evidence |
| Exact caps, FX, half-up rounding, unknown versus zero | Interview 305–345; policy ¶3; FX/Caps tables | Pending monetary review | USD rate 0.9; caps in original expense currency; C108/C109 have rounding-sensitive lines | Decimal arithmetic and independent reconciliation pending; GBP rate/BE cap remain owned gaps |
| Deadline: two calendar months inclusive, month-end clamp | Policy ¶5; original cost first-filing dates | Pending eligibility review | Inspected boundary cases C110–C113 and C12 late exception | Focused month-end and revised-cost tests pending |
| Separate permit/claim reviews, stable roles, strict director threshold | Interview 353, 361, 377–389; policy ¶4, ¶6–7; People; Review ledger/packets | Pending decision admission/readiness | C04 combined owner/supervisor response; P02 permit and C02 claim routes differ; C99–C101 threshold boundaries | Validate subjects, revisions, actors, packet/source/budget versions; C119 director reply missing |
| Whole budget ledger without double-counted settled commitments | Policy ¶6; Budget rows 6–8; packet budget references | Pending budget context | Prior allocation/obligations retained with settled/refund columns | Validate allocation less net settled less remaining commitments across all accepted requests |
| Incomplete claims and independent work | Interview 361, 369; policy ¶12; C08/C01/P122 evidence below | Pending orchestration | Concrete source examples inspected | **Learner choice 1 required before implementation governs processing** |
| Corrections invalidate dependent review even at unchanged totals | Interview 397–429; policy ¶8; updates C09/C18/C19 | Pending revision and dependency handling | Old/new identities and amount-only versus cancellation exceptions inspected | **Learner choice 2 required**; tests for recomputation, approvals and held replacements pending |
| Local repair queue and partial responses | Interview 369, 477, 509; ledger returns C09/C21 | Pending repair queue and report | Return reasons/affected fields/owners retained | **Learner choice 4 required**; supported portions may resolve while remaining facts stay open |
| Stable requests, prior-cost/prepayment exclusion | Policy ¶9; updates p3 C24/C03; Finance activity | Pending obligation ledger | Shared COST-03 and distinct COST-24 preserved | Replay must not duplicate prior committed/settled cost; tests pending |
| Finance event admission, attempts, refunds, conflicts, late outcomes | Interview 445–469, 533; policy ¶10–11; Finance activity | Pending Finance reducer/reconciliation | Supplied partials, retry, exact redelivery, linked refunds, overpayment and post-cancellation transfer inspected | Validate all event bindings, replay identity, positive cents, chronology, refund ceiling and resolution |
| Independent trip/permit cancellations, including no-claim processes | Interview 437, 445, 525; policy ¶13–16; Travel cancellations/Trips | Pending cancellation state and consequences | TC122 no-claim, TC121 permit-only, TC018/TC019 claim/Finance consequences inspected | Separate event domains; pending confirmation; authority/target/time validation; no invented claim rows |
| Financial/operational completion | Interview 461, 469; policy ¶11, ¶16 | Pending report/readiness/closure | Source prerequisites inspected; no result yet | **Learner choice 3 after inspecting an actual result**; no premature financial-completion claim |
| Schema and sealed batch chain | Full `snapshot.schema.json`; assignment | Pending snapshot writer/semantic validator | Schema read in full; descriptive invariants identified | Validate shape plus hashes, references, uniqueness, availability, money and legal state transitions |
| CSV, report, operations handoff, exact commands | Assignment | Required `claims.csv`, `report.md`, `README.md` | No operational outputs produced in this review | All implementation/run/replay/handoff work pending |
| Real capture linked to revision | Actual Entire session `01a14282-ba9a-7540-aafd-73a472f91b04` | Entire-managed Git records | Active recorded session and one existing local temporary checkpoint observed | Verify recorded checkpoint after first meaningful commit; remote sync/access remains unverified |

## Record coverage controls

| Source records | Count / arrival distribution |
|---|---|
| Initial claims | 120, all revision 1 / batch 1; C01–C121 excluding C24; C13 withdrawn |
| Updates | Six batch-3 versions, one batch-4 version; C24 first arrives in batch 3 |
| Receipts | 203 unique records over 102 pages |
| People / trips / merchant payments | 14 / 123 / 201 data rows |
| FX / caps / budget | 2 / 2 / 3 data rows |
| Review ledger and packets | 307 matching records each: batches 1=289, 2=0, 3=15, 4=3 |
| Finance activity | 220 deliveries: batches 1=100, 2=100, 3=10, 4=10 |
| Travel cancellations | 9 deliveries: batches 1=2, 2=4, 3=2, 4=1 |

Arrival is distinct from business time. Packets inherit availability from their matching ledger decision. Exact Finance/cancellation redeliveries count as deliveries here, not additional money or additional cancellation processes. Receipt presence alone cannot introduce a later claim revision before its arrival.

## First learner choice: evidence and consequences

- **C08 revision 1:** initial claim p8 requests EUR 120. Receipt p4 contains R-COST-08, but the complete Merchant payments tab contains no COST-08 payment. Entitlement is unproven, not zero. Missing employee payment evidence must remain held and owned.
- **C01 revision 1:** initial claim p1 and receipt p1 support EUR 100; Merchant payments row 6 is settled. Review ledger/packets rows 6–8 identify its three claim approvals. Finance activity row 33 records batch-one acceptance; settlement at row 6 arrives in batch 2, so it cannot be reported paid in batch 1.
- **P122 / T122 revision 1:** Trips row 128 shows EUR 500 estimate and no commitment. Review ledger/packets rows 301–303 describe its separate permit route. Travel cancellations row 6 is a batch-one request, row 7 is batch-two confirmation, and row 14 redelivers confirmation in batch 4. There is no claim to invent. A pending valid cancellation pauses new affected arrangements even if independent work continues elsewhere.
- Policy ¶12 permits independently progressing unaffected work or conservatively holding the batch with its business cost explained. Interview 361/369 establishes that incompleteness does not inherently block independent work. The policy permits a chosen conservative hold; it does not turn C08 into a dependency of C01. Shared evidence, authority, prior obligations and budget still require dependency checks.

No approach has been adopted by the learner yet. The remaining three choices likewise remain unmade. Policy minimums constrain every choice: partial evidence is not partial-payment authority; an accepted request is not payment; business cancellation is not Finance cancellation.

## Open scope and ownership

| Open item | Evidence / scope | Owner and next action |
|---|---|---|
| Missing GBP exchange rate | FX contains EUR/USD only; COST-22 GBP 45 and COST-116-2 GBP 10 need payment-date rates | Finance: supply exact applicable rates or explicit authorized disposition; retain affected money as unknown |
| Missing BE lodging cap | Caps contains NL lodging/meals only; T23 is BE | Finance: define applicable cap or explicit authorized disposition; never borrow NL rates |
| Missing current human responses | For example C119 EUR 1,000.01 has no director reply | Applicable directory reviewer via Administration: wait for authorized scenario evidence; fabricate nothing |
| First learner constraint | C08/C01/P122 examples above | Beckham: choose and explain progression/hold boundaries in captured conversation |
| Remaining learner constraints | Revalidation, repair organization, and final acceptance | Beckham: decide at their appropriate evidence stage, before each governs affected work |
| Source-version interpretation | Supplied policy slug says 2026-1; live page and all review packets identify POL-2026.2 | Current evidence consistently supports retaining POL-2026.2. Raise any later conflicting native version for clarification instead of silently mixing it |
| Capture remote pairing | Local session/checkpoint exists; earlier checkpoint listing could not reach remote | Coding agent: inspect recorded checkpoint after first meaningful commit, and verify sync when network/auth allow; facilitator repairs genuinely missing capture |

No native retrieval scope remains missing. The rate, cap and reply gaps are supplied business facts to report and own, not failed source downloads. No follow-up interview has been run or scripted.

## Verification still required after implementation

The schema alone does not enforce correct predecessor/source bytes, temporal availability, key uniqueness, actor/role authority, decision/request/cost references, rounded totals, admitted-money reconciliation, valid closure or cancellation authority. Enable date-time format checks. Keep Finance activity IDs separate from cancellation IDs and resolve every cancellation issue reference to `issues[].record_id`. Exercise all supplied branches, including exact threshold/cap boundaries, line rounding, first-filing dates, personal/unknown categories, returns, stale reviews, post-acceptance changes, partial settlements, failed attempts, linked refunds, overpayments, cancellation before and after commitment/payment, original requests after reassignment, and unchanged replay. Additional isolated checks supplement the primary run.

No implementation tests, operational run, financial conclusion or submission claim is recorded as complete here.
