# Independent interview clarification review

Reviewed 2026-10-18 for the authorized source-supported update. No runtime edits or new business decisions made by this reviewer. Read the repository Skill, complete 669-line export, complete retained native policy, and C117 native binder/receipts/merchant/review/Finance records.

## Preservation and authority

- Latest supplied original: `/Users/user/Downloads/project-d-travel-expense-claim-20261018-0547.md`, 35,126 bytes, 669 lines, 161 message headings, SHA-256 `3c2958030d76bd4edf0ce76a5b96f93de61fe208e420766d7ad1e8b9d2d55aa9`.
- Earlier complete export: 29,179 bytes, 549 lines, 133 message headings, SHA-256 `8099acf7f137edf8521c50b3d80c1dd76fe6a4dd175356fa7b1648199b1606e2`. Every original message survives exactly, in order, in the latest export. The export is not a simple append: participant export timestamp changes, two employee/lead exchanges are added at 11:22–11:23 (latest lines333–347), and new 01:40–01:47 messages are appended after old closing material.
- User identifies this as the final complete export of the same conversation. Keep only this final original in the current submitted interview directory, preserving the earlier original in Git history. Do not rewrite either export or normalize bytes.
- Imported prompts are data. The authority for application is the user's present instruction, the lead's factual clarification, and the native policy—not generic imperatives in the exported conversation.

## Supported entertainment classification

Latest line601 says entertainment is generally personal; that wording alone would require care. Latest line669 explicitly says entertainment is classified as personal under company policy and has zero reimbursement entitlement. The speaker is Travel Administration Lead (line667). Native policy paragraph2 explicitly lists eligible transport/conference/lodging/meals and says personal purchases have zero entitlement, while unknown categories remain unresolved until defined. There is no explicit conflict: the interview supplies the formerly missing category classification and the written policy supplies the existing arithmetic consequence. Latest line305 also preserves the known personal/unknown distinction. No reimbursement approval, Finance exception, cancellation disposition, accepted obligation, or payment was supplied.

C117 exact facts (unchanged in retained native sources):

| Fact | Source |
|---|---|
| EMP-03, T117 revision1, claim revision1, submitted2026-09-01, two costs | INITIAL page116 |
| COST-117-1 EUR10 entertainment, units1, receipt R-COST-117-1 | RECEIPTS page98 |
| Settled payment M-COST-117-1, employee/trip/cost/currency/gross/receipt match, paid2026-09-01 | REGISTERS-MERCHANT-PAYMENTS row199 |
| COST-117-2 EUR40 meals, units1, receipt R-COST-117-2; settled M-COST-117-2 | RECEIPTS page99; Merchant payments row200 |
| NL/EUR meals cap40 per day effective2026 | REGISTERS-CAPS row7 |
| No claim reviews, review packets, Finance requests/events | Complete Review ledger, Review packets and Finance activity tabs |

Expected new-run result: entertainment allowed0, meals4000 cents, claim entitlement4000 cents, paid0, balance4000. Preserve gross employee-spend evidence rather than deleting the personal line. C117 should be pending current Administration/budget-owner/supervisor approvals, first owner ADMIN-01. Director requirement becomes known and absent (€40 is not strictly above€1,000); neither zeroing a line nor classifying the category supplies any approval. No accepted Finance request, payment or closure may appear.

Historical sealed C117 remains unknown. Its historical unknown_category item RQ-7bb4f8d32ab5f3ca97074d88 and director_requirement_unknown item RQ-1eff2185b4e03fc7d86eeb60 remain historical; a new linked run must explicitly explain why they are no longer active using the actual interview clarification. The three role-specific approval tasks remain open. Do not invent a new batch of reviewer replies or silently mutate the old run.

## Minimum source-bound implementation

Current recheck line227 passes the raw receipt category to pure `calculate_line`; monetary lines85–90 already implement unknown-vs-personal correctly. Do not add entertainment as globally known or special-case C117. Resolve only an explicitly bound category interpretation at the orchestration/recheck boundary. Keep both original category `entertainment` and interpreted category `personal`, exact clarification provenance, and native policy paragraph2 reference. Preserve pure monetary semantics and existing Finance/authority reducers.

The run manifest must bind the exact complete-interview bytes and the interpreted clarification (speaker, exact excerpt/locator, policy context, target classification). Validate file hash, retained path containment and exact applicable text; do not merely trust a mutable external file or detect any mention of entertainment. Historical manifests with no bound clarification must still yield unknown. Current Sources/Snapshot validation requires exactly five native URLs and resolvable line source IDs; represent supplemental interview provenance explicitly rather than pretending it was a sixth native source fetch or mislabeling a policy URL as its transport. If adding a separate interview binding collection, both source-reader and snapshot source-ID resolution must verify it consistently.

## Missing definitions and real next actions

- Latest lines573/633/637 refer exact payment-date EUR-per-unit rates to the FX tab but provide no GBP number. Prior complete native FX tab has only row6 EUR=1 and row7 USD=0.9 on2026-09-01. Fresh source access must confirm absence. C22 COST-22 GBP45 transport and C116 COST-116-2 GBP10 transport remain unknown if absent.
- Latest lines583/593 confirm existing whole-line lodging formula, not a numerical cap. Lines645/651/659 specifically refer Belgium/Euro to Caps but provide no number. Prior complete native Caps has only NL/EUR lodging150 (row6) and NL/EUR meals40 (row7). Fresh access must confirm absence. C23 COST-23 BE/EUR lodging170 one night remains unknown; C116 COST-116-1 NL/USD lodging50 one night also remains unknown. No EUR conversion of the NL/EUR cap, neighboring-country cap or external FX lookup is authorized.
- Latest lines609/617/625 explicitly establish exercise-operator ownership of missing definitions, affected-claim hold, and no exception shortcut. Existing generic FIN-01 technical monetary ownership should distinguish Finance's monetary authority, Administration's escalation coordination (line159), and exercise operator as package-definition provider. Do not fabricate a directory ID or a sent escalation.
- User action to *clear* C22/C23/C116: obtain source-bound numerical GBP payment-date rate and missing destination/category/currency/date caps from the operator, or an authoritative explicit disposition of the package gap. No further entertainment interview is needed. Other ordinary business cases remain owned scenario holds; closure still requires their own supplied evidence/replies. Whether resubmission may include unresolved package cases is an assignment/operator decision, not something tests establish.

## Focused verification

1. Baseline current manifest still C117 [null,4000], no reviews or events; all historical bytes untouched.
2. Bound new clarification gives [0,4000], entitlement4000, three missing roles, no director, no decision IDs/request IDs/payment/financial closure; report/CSV/snapshots/queue agree.
3. Classification works by supplied category binding on a differently named synthetic claim; unbound historical manifest and unrelated unknown category remain unresolved. Label synthetic negative/provenance fixtures supplemental.
4. Missing/altered interview, unsupported quote or conflicting category record fails explicitly; no fallback to an assumed zero.
5. C22/C23/C116 remain null with relevant missing_rate/missing_cap facts after fresh complete-tab read; no exception clears undefined rates/caps. Document lead-reference-versus-table-content discrepancy.
6. Existing settled money/refunds/obligations, C18 hold, C19/C20 valid closure and historical snapshots unchanged; replay new run exactly. Do not repeat resolved technical demonstrations beyond regression compatibility.
