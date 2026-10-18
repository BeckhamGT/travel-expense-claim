# Travel expense operations handoff

Run: `clarification-20261018T054954Z`. Case clock: `2026-11-15 Europe/Amsterdam`.

Consumed arrival batches 1–1 of 4. Waiting for explicit continuation; later batches have not been consumed. Business approvals, exceptions, bookings and money remain human-owned; all replies/outcomes are fixed supplied exercise facts.

Inputs are bound in `sources.json`; native content, full searchable PDF extractions and all ten workbook CellData tabs are retained. Earlier source-review and choice-verification artifacts remain unchanged.

| Batch | Claims | Net paid cents | Accepted obligation cents | Budget remaining cents | Status counts |
|---|---:|---:|---:|---:|---|
| 1 | 120 | 0 | 1183415 | 316585 | {'pending': 103, 'held': 13, 'closed-no-payment': 2, 'withdrawn': 1, 'rejected': 1} |

## Source-bound interview clarification

The complete learner-conducted interview is bound separately from the five freshly read native locations. Its original bytes are retained, with one final complete export for this conversation under `interviews/`; previous export versions remain in Git history. The clarification defines category treatment under policy paragraph 2. It is not a claim approval, eligibility exception or Finance outcome.

| Category | Policy treatment | Affected claim / revision / cost | Exact evidence |
|---|---|---|---|
| entertainment | personal: known zero line entitlement; other lines and current approvals remain separate | C117 / 1 / COST-117-1 | INTERVIEW:line669; POLICY:paragraph2 |

## Current claims and owned next work

Unknown money remains null/blank; known zero is explicit. Balance uses the current authorized obligation, preserving overpayments and explicit non-payment dispositions. Prepaid costs are linked and excluded from a new obligation without erasing the original transfer.

| Claim / revision | Trip | Status | Allowed / net paid / balance cents | Next owner | Reason |
|---|---|---|---|---|---|
| C01 / 1 | T01 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C02 / 1 | T02 | pending | 54000 / 0 / 54000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C03 / 1 | T03 | pending | 20000 / 0 / 20000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C04 / 1 | T04 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C05 / 1 | T05 | pending | 100000 / 0 / 100000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C06 / 1 | T06 | pending | 100001 / 0 / 100001 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C07 / 1 | T07 | pending | 30000 / 0 / 30000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C08 / 1 | T08 | held | unknown / 0 / unknown | EMP-01 | C08 revision 1 / COST-08: receipt and matching settled merchant proof missing, ambiguous or incompatible; Current revision lacks applicable approval roles: administration, budget_owner, supervisor, director_requirement_unknown |
| C09 / 1 | T09 | held | 8000 / 0 / 8000 | EMP-01 | Please supply the revised trip evidence.; next action: Provide revised trip evidence.; Current revision lacks applicable approval roles: budget_owner, supervisor |
| C10 / 1 | T10 | held | 9000 / 0 / 9000 | FIN-01 | The complete applicable permit route was approved only after the first commitment day; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C100 / 1 | T100 | pending | 100000 / 0 / 100000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C101 / 1 | T101 | pending | 100001 / 0 / 100001 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C102 / 1 | T102 | pending | 14999 / 0 / 14999 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C103 / 1 | T103 | pending | 15000 / 0 / 15000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C104 / 1 | T104 | pending | 15000 / 0 / 15000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C105 / 1 | T105 | pending | 3999 / 0 / 3999 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C106 / 1 | T106 | pending | 4000 / 0 / 4000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C107 / 1 | T107 | pending | 4000 / 0 / 4000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C108 / 1 | T108 | pending | 208 / 0 / 208 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C109 / 1 | T109 | pending | 208 / 0 / 208 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C11 / 1 | T11 | pending | 6000 / 0 / 6000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C110 / 1 | T110 | pending | 2500 / 0 / 2500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C111 / 1 | T111 | pending | 2500 / 0 / 2500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C112 / 1 | T112 | held | 2500 / 0 / 2500 | FIN-01 | First filing is after the original planned trip deadline; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C113 / 1 | T113 | held | 2500 / 0 / 2500 | EMP-03 | Initial filing predates payment or receipt; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C114 / 1 | T114 | held | unknown / 0 / unknown | EMP-03 | C114 revision 1 / COST-114-2: receipt and matching settled merchant proof missing, ambiguous or incompatible; Current revision lacks applicable approval roles: administration, budget_owner, supervisor, director_requirement_unknown |
| C115 / 1 | T115 | pending | 1500 / 0 / 1500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C116 / 1 | T116 | held | unknown / 0 / unknown | Exercise operator | COST-116-1 (USD, paid 2026-09-01): Need exactly one applicable destination/category/currency/payment-date cap; COST-116-2 (GBP, paid 2026-09-01): Need exactly one exact payment-date rate for the expense currency; Current revision lacks applicable approval roles: administration, budget_owner, supervisor, director_requirement_unknown |
| C117 / 1 | T117 | pending | 4000 / 0 / 4000 | ADMIN-01 | Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C118 / 1 | T118 | closed-no-payment | 0 / 0 / 0 | — | Known zero entitlement with no financial effect |
| C119 / 1 | T119 | pending | 100001 / 0 / 100001 | DIR-01 | Current revision lacks applicable approval roles: director |
| C12 / 1 | T12 | held | 7000 / 0 / 7000 | FIN-01 | First filing is after the original planned trip deadline; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C120 / 1 | T120 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C121 / 1 | T121 | held | 3000 / 0 / 3000 | SUP-01 | A valid business cancellation request pauses affected payment readiness; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C13 / 1 | T13 | withdrawn | 5000 / 0 / 0 | — | Employee withdrew before review. |
| C14 / 1 | T14 | rejected | 4000 / 0 / 0 | — | Client work was cancelled. |
| C15 / 1 | T15 | closed-no-payment | 0 / 0 / 0 | — | Known zero entitlement with no financial effect |
| C16 / 1 | T16 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C17 / 1 | T17 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C18 / 1 | T18 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C19 / 1 | T19 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C20 / 1 | T20 | pending | 10000 / 0 / 10000 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C21 / 1 | T21 | held | 8000 / 0 / 8000 | LEAD-01 | Budget owner requests a funding review before committing.; next action: Obtain funding decision.; Current revision lacks applicable approval roles: budget_owner, supervisor |
| C22 / 1 | T22 | held | unknown / 0 / unknown | Exercise operator | COST-22 (GBP, paid 2026-09-01): Need exactly one exact payment-date rate for the expense currency; Current revision lacks applicable approval roles: administration, budget_owner, supervisor, director_requirement_unknown |
| C23 / 1 | T23 | held | unknown / 0 / unknown | Exercise operator | COST-23 (EUR, paid 2026-09-01): Need exactly one applicable destination/category/currency/payment-date cap; Current revision lacks applicable approval roles: administration, budget_owner, supervisor, director_requirement_unknown |
| C25 / 1 | T25 | held | 10000 / 0 / 10000 | FIN-01 | No complete active applicable permit route is established before the first commitment; Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C26 / 1 | T26 | pending | 10000 / 0 / 10000 | ADMIN-01 | Current revision lacks applicable approval roles: administration, budget_owner, supervisor |
| C27 / 1 | T27 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C28 / 1 | T28 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C29 / 1 | T29 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C30 / 1 | T30 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C31 / 1 | T31 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C32 / 1 | T32 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C33 / 1 | T33 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C34 / 1 | T34 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C35 / 1 | T35 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C36 / 1 | T36 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C37 / 1 | T37 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C38 / 1 | T38 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C39 / 1 | T39 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C40 / 1 | T40 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C41 / 1 | T41 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C42 / 1 | T42 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C43 / 1 | T43 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C44 / 1 | T44 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C45 / 1 | T45 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C46 / 1 | T46 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C47 / 1 | T47 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C48 / 1 | T48 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C49 / 1 | T49 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C50 / 1 | T50 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C51 / 1 | T51 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C52 / 1 | T52 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C53 / 1 | T53 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C54 / 1 | T54 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C55 / 1 | T55 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C56 / 1 | T56 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C57 / 1 | T57 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C58 / 1 | T58 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C59 / 1 | T59 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C60 / 1 | T60 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C61 / 1 | T61 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C62 / 1 | T62 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C63 / 1 | T63 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C64 / 1 | T64 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C65 / 1 | T65 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C66 / 1 | T66 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C67 / 1 | T67 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C68 / 1 | T68 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C69 / 1 | T69 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C70 / 1 | T70 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C71 / 1 | T71 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C72 / 1 | T72 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C73 / 1 | T73 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C74 / 1 | T74 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C75 / 1 | T75 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C76 / 1 | T76 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C77 / 1 | T77 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C78 / 1 | T78 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C79 / 1 | T79 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C80 / 1 | T80 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C81 / 1 | T81 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C82 / 1 | T82 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C83 / 1 | T83 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C84 / 1 | T84 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C85 / 1 | T85 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C86 / 1 | T86 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C87 / 1 | T87 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C88 / 1 | T88 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C89 / 1 | T89 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C90 / 1 | T90 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C91 / 1 | T91 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C92 / 1 | T92 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C93 / 1 | T93 | pending | 3500 / 0 / 3500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C94 / 1 | T94 | pending | 4500 / 0 / 4500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C95 / 1 | T95 | pending | 5500 / 0 / 5500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C96 / 1 | T96 | pending | 6500 / 0 / 6500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C97 / 1 | T97 | pending | 7500 / 0 / 7500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C98 / 1 | T98 | pending | 8500 / 0 / 8500 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |
| C99 / 1 | T99 | pending | 99999 / 0 / 99999 | FIN-01 | Accepted obligation awaits remaining confirmed settlement |

## Independent cancellation processes

| Process | Exact target | Business state | Financial consequence | Affected claims / original requests | Owner / next action |
|---|---|---|---|---|---|
| TC121 | permit P121 / 1 | requested | unresolved | ['C121'] / [] | SUP-01 / Retain original request and money; current disposition/review/reconciliation requires the stated source evidence |
| TC122 | trip T122 / 1 | requested | no-financial-effect | [] / [] | SUP-01 / Complete sources show no commitment, employee-paid cost or reimbursement obligation |

## Repair queue and significant updates

`repair-queue.json` preserves one item per subject/revision/missing fact or return reason and owner-based views. Local drafts have not been sent. Verification records cite supplied evidence; later source batches were fixed inputs, not responses caused by the drafts. A partial repair proves only its fact; queue resolution grants no approval or payment authority.

| Batch | Subject / revision | Item | Change | Evidence / reason |
|---|---|---|---|---|
| 1 | C08 / 1 | RQ-f895ddba6957039d0302b219 | None → open | New or reopened missing fact/return |
| 1 | C08 / 1 | RQ-c55a462825d6240401c54b72 | None → open | New or reopened missing fact/return |
| 1 | C08 / 1 | RQ-3e3add3ada545a7beba8eb02 | None → open | New or reopened missing fact/return |
| 1 | C08 / 1 | RQ-3f8322fa9b6a46e21f977737 | None → open | New or reopened missing fact/return |
| 1 | C08 / 1 | RQ-a0132a1aba31dc268656ca92 | None → open | New or reopened missing fact/return |
| 1 | C09 / 1 | RQ-49889e8a3b21096064cd5cb9 | None → open | New or reopened missing fact/return |
| 1 | C09 / 1 | RQ-cf418ab9f46ec3bd2f886e0e | None → open | New or reopened missing fact/return |
| 1 | C10 / 1 | RQ-bf489729b36a52bc26dcac4d | None → open | New or reopened missing fact/return |
| 1 | C10 / 1 | RQ-cddd09c2978bae4a0d013ba1 | None → open | New or reopened missing fact/return |
| 1 | C10 / 1 | RQ-77808f5cc04728135ccee595 | None → open | New or reopened missing fact/return |
| 1 | C10 / 1 | RQ-c3db3f8af85a78a82017f675 | None → open | New or reopened missing fact/return |
| 1 | C112 / 1 | RQ-faec264a3886cd476fc91f41 | None → open | New or reopened missing fact/return |
| 1 | C112 / 1 | RQ-9efeeb10ea4b56bff60a18a0 | None → open | New or reopened missing fact/return |
| 1 | C112 / 1 | RQ-556e1289c3f69ec5a25d48de | None → open | New or reopened missing fact/return |
| 1 | C112 / 1 | RQ-3686c843248675faae33fa29 | None → open | New or reopened missing fact/return |
| 1 | C113 / 1 | RQ-e688c83699bdf701bf2b111a | None → open | New or reopened missing fact/return |
| 1 | C113 / 1 | RQ-2ec860a3e5a7052fdcb688f5 | None → open | New or reopened missing fact/return |
| 1 | C113 / 1 | RQ-f0e33f488afca975ee5e8fdd | None → open | New or reopened missing fact/return |
| 1 | C113 / 1 | RQ-239614b4a2a1ab967313055c | None → open | New or reopened missing fact/return |
| 1 | C114 / 1 | RQ-7ae596395f54e6ac62c5daa9 | None → open | New or reopened missing fact/return |
| 1 | C114 / 1 | RQ-77bd650a85f5e140b8d6786f | None → open | New or reopened missing fact/return |
| 1 | C114 / 1 | RQ-f95651a361d668226008ac77 | None → open | New or reopened missing fact/return |
| 1 | C114 / 1 | RQ-e21565efd9d340fd30eb1a02 | None → open | New or reopened missing fact/return |
| 1 | C114 / 1 | RQ-33b0d800c689b4211cf0b5fc | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-3828880344e1b778fabff6ff | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-352267d22b0595fe1a598e93 | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-e5a41ec04c664ebfe9ab5177 | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-e89b7003af39be1d19186ffa | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-e6f1485114f8fd1ce25e27e7 | None → open | New or reopened missing fact/return |
| 1 | C116 / 1 | RQ-904ed3501c36a3b670c1e095 | None → open | New or reopened missing fact/return |
| 1 | C117 / 1 | RQ-eb48bb03c67b0db3468a6b27 | None → open | New or reopened missing fact/return |
| 1 | C117 / 1 | RQ-07d5aa92f77f8705edbc6dd2 | None → open | New or reopened missing fact/return |
| 1 | C117 / 1 | RQ-cd0cd03caa1bb7681fbf7515 | None → open | New or reopened missing fact/return |
| 1 | C119 / 1 | RQ-a8af4a4555f0c065ca0fcd17 | None → open | New or reopened missing fact/return |
| 1 | C12 / 1 | RQ-c9a5df8b4a72927bb463bef8 | None → open | New or reopened missing fact/return |
| 1 | C12 / 1 | RQ-fff876c012a27ec4b6f7fda3 | None → open | New or reopened missing fact/return |
| 1 | C12 / 1 | RQ-60f24a5c7d665191ec5602f9 | None → open | New or reopened missing fact/return |
| 1 | C12 / 1 | RQ-ce0fdfe97173c9ce591b9539 | None → open | New or reopened missing fact/return |
| 1 | C121 / 1 | RQ-b7141c644ad06ea04357c6bb | None → open | New or reopened missing fact/return |
| 1 | C121 / 1 | RQ-e3713504b3ecaf10680dfd5d | None → open | New or reopened missing fact/return |
| 1 | C121 / 1 | RQ-534912f6631f82f75b02dea9 | None → open | New or reopened missing fact/return |
| 1 | C121 / 1 | RQ-742c1d6950a0f7df6335d193 | None → open | New or reopened missing fact/return |
| 1 | C21 / 1 | RQ-2422d2620804da715d421edf | None → open | New or reopened missing fact/return |
| 1 | C21 / 1 | RQ-8347b4956ca5c83ac3c2c8a5 | None → open | New or reopened missing fact/return |
| 1 | C22 / 1 | RQ-2324d318b2a2347c6b7a2324 | None → open | New or reopened missing fact/return |
| 1 | C22 / 1 | RQ-cf855451fddd1bce71a9df19 | None → open | New or reopened missing fact/return |
| 1 | C22 / 1 | RQ-6e2be24b7420deb2c522a8ad | None → open | New or reopened missing fact/return |
| 1 | C22 / 1 | RQ-22a95638ed21b0dd530d7aea | None → open | New or reopened missing fact/return |
| 1 | C22 / 1 | RQ-08dd8a56624ce5ba1edef999 | None → open | New or reopened missing fact/return |
| 1 | C23 / 1 | RQ-e339700f026e515fffd7b402 | None → open | New or reopened missing fact/return |
| 1 | C23 / 1 | RQ-b513eb0eeafd707f60ae7675 | None → open | New or reopened missing fact/return |
| 1 | C23 / 1 | RQ-bd0dd498a99765bbb2c7528e | None → open | New or reopened missing fact/return |
| 1 | C23 / 1 | RQ-65c0c9c0b8ee85dd9e08032f | None → open | New or reopened missing fact/return |
| 1 | C23 / 1 | RQ-12c814c2a79766c412675e0b | None → open | New or reopened missing fact/return |
| 1 | C25 / 1 | RQ-a546b5bb7218368da054617a | None → open | New or reopened missing fact/return |
| 1 | C25 / 1 | RQ-86779b359bedb49ba5701c7b | None → open | New or reopened missing fact/return |
| 1 | C25 / 1 | RQ-3f7cbefaf939d656627e24eb | None → open | New or reopened missing fact/return |
| 1 | C25 / 1 | RQ-cdcbe05e60b73e7f79f254f7 | None → open | New or reopened missing fact/return |
| 1 | C26 / 1 | RQ-93f209d4e836fb1d42218c35 | None → open | New or reopened missing fact/return |
| 1 | C26 / 1 | RQ-0afa5118081d0921034926bd | None → open | New or reopened missing fact/return |
| 1 | C26 / 1 | RQ-648bec0ec3d28c06fb39230c | None → open | New or reopened missing fact/return |
| 1 | TC121 / 1 | RQ-6445f80ccdf46aad1b3bc369 | None → open | New or reopened missing fact/return |
| 1 | TC122 / 1 | RQ-d506ea23d238f50ef3326f3a | None → open | New or reopened missing fact/return |

### Returned work: provider and reviewer

The provider supplies the repair; the returning reviewer retains approval authority. Superseded work remains historical.

| Subject / revision | Repair provider | Returning reviewer / decision | Required repair | State |
|---|---|---|---|---|
| C21 / 1 | LEAD-01 | LEAD-01 / D-C21-1-claim-budget_owner-1 | Obtain funding decision. | open |
| C09 / 1 | EMP-01 | LEAD-01 / D-C09-1-claim-budget_owner-1 | Provide revised trip evidence. | open |

### Missing definitions and package escalation

The latest bound interview assigns missing package definitions to the exercise operator and requires the affected claim to stay held without an exception shortcut. Administration coordinates escalation; Finance retains monetary authority. Local drafts have not been sent. INTERVIEW:line609; POLICY:paragraph7.

| Subject / revision / cost | Missing definition | Source references | Next action |
|---|---|---|---|
| C22 / 1 / COST-22 | COST-22 (GBP, paid 2026-09-01): Need exactly one exact payment-date rate for the expense currency | INITIAL:page22, INTERVIEW:line609, POLICY:paragraph7, RECEIPTS:page11, REGISTERS-FX:complete-tab, REGISTERS-MERCHANT-PAYMENTS:row26 | Administration coordinates exercise-operator correction of the missing package definition; Finance retains monetary authority. Keep held; no exception can substitute for the missing definition |
| C116 / 1 / COST-116-2 | COST-116-2 (GBP, paid 2026-09-01): Need exactly one exact payment-date rate for the expense currency | INITIAL:page115, INTERVIEW:line609, POLICY:paragraph7, RECEIPTS:page98, REGISTERS-FX:complete-tab, REGISTERS-MERCHANT-PAYMENTS:row198 | Administration coordinates exercise-operator correction of the missing package definition; Finance retains monetary authority. Keep held; no exception can substitute for the missing definition |
| C116 / 1 / COST-116-1 | COST-116-1 (USD, paid 2026-09-01): Need exactly one applicable destination/category/currency/payment-date cap | INITIAL:page115, INTERVIEW:line609, POLICY:paragraph7, RECEIPTS:page97, REGISTERS-CAPS:complete-tab, REGISTERS-MERCHANT-PAYMENTS:row197 | Administration coordinates exercise-operator correction of the missing package definition; Finance retains monetary authority. Keep held; no exception can substitute for the missing definition |
| C23 / 1 / COST-23 | COST-23 (EUR, paid 2026-09-01): Need exactly one applicable destination/category/currency/payment-date cap | INITIAL:page23, INTERVIEW:line609, POLICY:paragraph7, RECEIPTS:page12, REGISTERS-CAPS:complete-tab, REGISTERS-MERCHANT-PAYMENTS:row27 | Administration coordinates exercise-operator correction of the missing package definition; Finance retains monetary authority. Keep held; no exception can substitute for the missing definition |

Fresh complete-table discrepancy: the lead refers GBP and Belgium/EUR questions to FX/Caps without numerical answers. Actual FX contents: EUR 1 on 2026-09-01 (REGISTERS-FX:row6); USD 0.9 on 2026-09-01 (REGISTERS-FX:row7). Actual Caps contents: NL/EUR lodging 150 (REGISTERS-CAPS:row6); NL/EUR meals 40 (REGISTERS-CAPS:row7). The required GBP rate, BE/EUR lodging cap and NL/USD lodging cap are absent. The table reference supplies none of those missing values; no cap conversion or external rate is assumed.

## Scope and verification boundaries

The original interview is retained byte-for-byte under `interviews/`. Policy paragraphs 2–11 and 13–16 govern the arithmetic, evidence, decision bindings, original requests and cancellation consequences. Each line, issue, decision and financial event retains its exact source identity/locator in the batch result. The learner's captured choices and code/test evidence are mapped in `docs/coverage.md`.

A complete business handoff may include legitimate owned unresolved cases: missing settled proof, applicable rates/caps, unknown categories, eligibility exceptions, returned work, missing discretionary replies or unresolved Finance effects. Implementation/verification gaps are separately recorded in the coverage map; they are not business holds. See README for validation, unchanged replay and safe resume commands. Sealed outputs change only in a new explicitly linked run.
