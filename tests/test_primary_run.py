"""Independent expectations for the complete, freshly retained native exercise.

Expected cents and branches below were transcribed from the five native sources,
not obtained from the monetary, Finance, eligibility or workflow reducers. The
explicit completion flag is exercised only as a proposed-policy test; the actual
source preview defaults to False and records no human adoption.
"""

from hashlib import sha256
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from travel_expense_claim.verify_independence import Sources
from travel_expense_claim.workflow import build_run


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/runs/submission-20261017T154939Z/sources.json"

# INITIAL pp1-23, pp24-25, pp98-120; policy paragraphs 5-11; receipts
# pp1-14 and 87-102. A known amount can still have an eligibility/review hold.
KNOWN_CENTS = {
    "C01": 10000, "C02": 54000, "C03": 20000, "C04": 10000,
    "C05": 100000, "C06": 100001, "C07": 30000, "C09": 8000,
    "C10": 9000, "C11": 6000, "C12": 7000, "C15": 0,
    "C16": 10000, "C17": 10000, "C18": 10000, "C20": 10000,
    "C21": 8000, "C25": 10000, "C26": 10000,
    "C99": 99999, "C100": 100000, "C101": 100001,
    "C102": 14999, "C103": 15000, "C104": 15000,
    "C105": 3999, "C106": 4000, "C107": 4000,
    "C108": 208, "C109": 208,
    "C110": 2500, "C111": 2500, "C112": 2500, "C113": 2500,
    "C115": 1500, "C118": 0, "C119": 100001, "C120": 7500,
}


class PrimaryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A missing fresh collection is a failed prerequisite, never a silent
        # fallback to the older review-only manifest.
        if not MANIFEST.is_file():
            raise AssertionError("Fresh full-source submission manifest is required")
        cls.sources = Sources(MANIFEST)
        cls.result = build_run(MANIFEST)
        cls.snapshots = cls.result["snapshots"]
        cls.schema = json.loads((ROOT / "snapshot.schema.json").read_text())

    def at(self, batch, claim_id):
        return next(row for row in self.snapshots[batch - 1]["claims"] if row["claim_id"] == claim_id)

    def request(self, batch, request_id):
        return next(row for row in self.snapshots[batch - 1]["requests"] if row["request_id"] == request_id)

    def cancellation(self, batch, cancellation_id):
        return next(row for row in self.snapshots[batch - 1]["travel_cancellations"]
                    if row["cancellation_id"] == cancellation_id)

    def codes(self, batch, claim_id):
        return {row["code"] for row in self.snapshots[batch - 1]["issues"]
                if row.get("subject_id") == claim_id and row.get("blocking", True)}

    def test_complete_current_claim_scope_and_schema_in_every_batch(self):
        self.assertEqual([len(s["claims"]) for s in self.snapshots], [120, 120, 121, 121])
        expected = {f"C{n:02}" for n in range(1, 122)}
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        for batch, snapshot in enumerate(self.snapshots, 1):
            with self.subTest(batch=batch):
                self.assertEqual(snapshot["batch_id"], str(batch))
                self.assertEqual(snapshot["run_id"], "submission-20261017T154939Z")
                self.assertEqual({r["claim_id"] for r in snapshot["claims"]},
                                 expected - ({"C24"} if batch < 3 else set()))
                self.assertEqual(list(validator.iter_errors(snapshot)), [])
                self.assertNotIn("C122", {r["claim_id"] for r in snapshot["claims"]})

    def test_source_manifest_binding_and_previous_snapshot_hash_are_exact(self):
        self.assertEqual(len({entry["url"] for entry in self.sources.data["files"]}), 5)
        self.assertTrue(all(entry["status"] == "read" for entry in self.sources.data["files"]))
        for index, snapshot in enumerate(self.snapshots):
            self.assertEqual(snapshot["source_binding"], {
                "path": "../sources.json", "sha256": sha256(MANIFEST.read_bytes()).hexdigest()})
            if index == 0:
                self.assertIsNone(snapshot["predecessor"])
            else:
                previous = (json.dumps(self.snapshots[index - 1], sort_keys=True, indent=2,
                                       ensure_ascii=False, allow_nan=False) + "\n").encode()
                self.assertEqual(snapshot["predecessor"], {
                    "path": f"{index}.json", "sha256": sha256(previous).hexdigest()})

    def test_fresh_corpus_contains_all_pages_and_all_ten_populated_registers(self):
        for identity, count in (("INITIAL-PAGES", 120), ("UPDATES-PAGES", 7), ("RECEIPTS-PAGES", 102)):
            self.assertEqual(len(self.sources.read(identity)), count)
        counts = {"People": 14, "Trips": 123, "Merchant payments": 201,
                  "FX": 2, "Caps": 2, "Budget": 3, "Review ledger": 307,
                  "Review packets": 307, "Finance activity": 220, "Travel cancellations": 9}
        for name, count in counts.items():
            self.assertEqual(len(self.sources.table(name)), count, name)
        self.assertEqual(self.sources.data["source_version"], "SRC-D-3")
        self.assertEqual(next(entry["source_version"] for entry in self.sources.data["files"]
                              if entry["source_id"] == "POLICY"), "POL-2026.2")

    def test_default_preview_does_not_adopt_completion_or_close_money(self):
        for snapshot in self.snapshots:
            self.assertFalse(snapshot["completion_choice_adopted"])
            self.assertFalse(any(row["status"].startswith("closed-") for row in snapshot["claims"]))
            self.assertTrue(all(not row["financial_completion_accepted"] for row in snapshot["claims"]))
        self.assertEqual(self.at(4, "C01")["paid_cents"], 10000)
        self.assertEqual(self.at(4, "C01")["balance_cents"], 0)
        self.assertIsNotNone(self.at(4, "C01")["next_owner"])

    def test_native_finance_is_complete_arrival_bounded_and_exactly_replayed(self):
        raw = self.sources.table("Finance activity")
        self.assertEqual(len(raw), 220)
        for batch, count in enumerate((100, 200, 210, 219), 1):
            snapshot = self.snapshots[batch - 1]
            visible = [row for row in raw if row["Arrival batch"] <= batch]
            self.assertEqual(set(snapshot["admitted_event_ids"]),
                             {row["Activity reference"] for row in visible})
            self.assertEqual(len(snapshot["admitted_event_ids"]), count)
            self.assertEqual(snapshot["rejected_finance_events"], [])
            self.assertEqual({request["request_id"] for request in snapshot["requests"]},
                             {row["Request reference"] for row in visible
                              if row["Activity type"] == "accepted"})
            refs = {ref for event in snapshot["finance_events"] for ref in event["source_refs"]}
            self.assertEqual(refs, {row["_ref"] for row in visible})
        self.assertIn("F-C01-1", self.snapshots[-1]["replayed_finance_event_ids"])
        self.assertEqual(self.at(4, "C01")["gross_paid_cents"], 10000)

    def test_independent_native_finance_totals_and_shared_budget(self):
        # Native settled/refund amounts, unique Activity reference, chronological
        # current commitments. Budget rows6-8: 20,000 allocation; OLD1 3,000
        # commitment incl2,000 settled; OLD2 2,000 unspent => prior burden5,000.
        expected = [
            (0, 0, 0, 1183415, 316585, 100),
            (1153915, 0, 1153915, 1183415, 315585, 100),
            (1164415, 1000, 1163415, 1193415, 304585, 104),
            (1206415, 3000, 1203415, 1193415, 296585, 104),
        ]
        for batch, (gross, refund, net, obligation, remaining, requests) in enumerate(expected, 1):
            with self.subTest(batch=batch):
                summary = self.result["summaries"][batch - 1]
                self.assertEqual((summary["gross_paid_cents"], summary["refunded_cents"],
                                  summary["net_paid_cents"], summary["accepted_obligation_cents"],
                                  summary["budget_remaining_cents"], summary["request_count"]),
                                 (gross, refund, net, obligation, remaining, requests))
                snapshot = self.snapshots[batch - 1]
                self.assertEqual(sum(c["paid_cents"] for c in snapshot["claims"]), net)
                self.assertEqual(len(snapshot["requests"]), requests)
                self.assertFalse(any("shared_budget" in self.codes(batch, identity)
                                     for identity in ("C01", "C03", "C08")))

    def test_stable_request_identity_basis_and_history_are_not_replaced(self):
        before = {r["request_id"]: r for r in self.snapshots[0]["requests"]}
        final = {r["request_id"]: r for r in self.snapshots[3]["requests"]}
        self.assertEqual(set(final) - set(before), {"REQ-C09", "REQ-C12", "REQ-C24", "REQ-C121"})
        for key, request in before.items():
            self.assertEqual(tuple(final[key][field] for field in ("claim_id", "revision", "payee", "currency")),
                             tuple(request[field] for field in ("claim_id", "revision", "payee", "currency")))
        self.assertEqual(self.request(4, "REQ-C19")["revision"], 1)
        self.assertEqual(self.request(4, "REQ-C18")["revision"], 1)
        self.assertEqual(self.request(4, "REQ-C09")["revision"], 2)
        self.assertEqual(self.request(4, "REQ-C19")["original_amount_cents"], 10000)
        self.assertEqual(self.request(4, "REQ-C19")["amount_cents"], 8000)

    def test_supported_arithmetic_and_cap_boundaries_are_source_derived(self):
        for batch in range(1, 5):
            for identity, amount in KNOWN_CENTS.items():
                with self.subTest(batch=batch, claim=identity):
                    self.assertEqual(self.at(batch, identity)["allowed_cents"], amount)
        # Lodging min(360,2*150); transport USD600*.9; caps in original
        # currency. At/below/above cap inputs are INITIAL pp101-106.
        self.assertEqual([self.at(1, f"C{n}")["allowed_cents"] for n in (102, 103, 104)],
                         [14999, 15000, 15000])
        self.assertEqual([self.at(1, f"C{n}")["allowed_cents"] for n in (105, 106, 107)],
                         [3999, 4000, 4000])

    def test_bulk_claims_cover_all_twelve_employees_without_aggregation_loss(self):
        # INITIAL pp26-97: each employee has six two-line claims of35/45/55/
        # 65/75/85 EUR. These inputs total360EUR each and4,320EUR overall.
        expected = (3500, 4500, 5500, 6500, 7500, 8500)
        for employee_index in range(12):
            ids = [f"C{27 + employee_index * 6 + offset}" for offset in range(6)]
            actual = [self.at(4, identity) for identity in ids]
            self.assertEqual([c["allowed_cents"] for c in actual], list(expected))
            self.assertEqual([c["paid_cents"] for c in actual], list(expected))
            self.assertEqual({c["employee_id"] for c in actual}, {f"EMP-{employee_index + 3:02}"})
            self.assertTrue(all(len(c["lines"]) == 2 for c in actual))
        self.assertEqual(sum(self.at(4, f"C{n}")["paid_cents"] for n in range(27, 99)), 432000)

    def test_fx_rounds_each_line_before_the_claim_sum(self):
        # USD1.15*.9=EUR1.035 ->1.04 each, two lines2.08 (not2.07).
        # USD1.16*.9=EUR1.044 ->1.04 each, two lines2.08 (not2.09).
        for identity in ("C108", "C109"):
            self.assertEqual([line["allowed_cents"] for line in self.at(1, identity)["lines"]], [104, 104])
            self.assertEqual(self.at(4, identity)["paid_cents"], 208)

    def test_director_threshold_is_strict_and_permit_estimate_is_independent(self):
        for identity in ("C05", "C99", "C100"):
            self.assertFalse(any("director" in key for key in self.at(1, identity)["decision_ids"]))
            self.assertTrue(self.at(1, identity)["current_review"]["current"])
        for identity in ("C06", "C101"):
            self.assertIn(f"D-{identity}-1-claim-director-1", self.at(1, identity)["decision_ids"])
        self.assertEqual(self.at(1, "C119")["allowed_cents"], 100001)
        self.assertIn("director", self.at(1, "C119")["current_review"]["missing_roles"])
        self.assertFalse(self.at(1, "C119")["source_financial_prerequisites_observed"])
        permit = self.at(1, "C02")["permission"]
        self.assertTrue(permit["historical_permission"])
        self.assertIn("D-C02-1-permit-director-1", permit["current_permit_authority"]["valid_decision_ids"])
        self.assertFalse(any("director" in key for key in self.at(1, "C02")["decision_ids"]))

    def test_combined_roles_are_supported_only_by_the_supplied_combined_reply(self):
        for identity in ("C04", "C120"):
            current = self.at(1, identity)
            self.assertEqual(len(current["decision_ids"]), 2)
            self.assertIn(f"D-{identity}-1-claim-budget_owner-supervisor-1", current["decision_ids"])
            self.assertTrue(current["current_review"]["current"])

    def test_missing_evidence_rate_cap_and_unknown_category_preserve_null(self):
        expected_codes = {
            "C08": "paid_evidence", "C22": "missing_rate", "C23": "missing_cap",
            "C114": "paid_evidence", "C116": "missing_cap", "C117": "unknown_category",
        }
        for batch in range(1, 5):
            for identity, code in expected_codes.items():
                with self.subTest(batch=batch, claim=identity):
                    current = self.at(batch, identity)
                    self.assertIsNone(current["allowed_cents"])
                    self.assertIsNone(current["balance_cents"])
                    self.assertEqual(current["status"], "held")
                    self.assertIn(code, self.codes(batch, identity))
                    self.assertTrue(any(line["allowed_cents"] is None for line in current["lines"]))
        self.assertIn("missing_rate", self.codes(4, "C116"))
        self.assertEqual([line["allowed_cents"] for line in self.at(4, "C114")["lines"]], [2000, None])
        self.assertEqual([line["allowed_cents"] for line in self.at(4, "C117")["lines"]], [None, 4000])
        self.assertEqual(self.at(4, "C08")["next_owner"], "EMP-01")

    def test_personal_zero_is_known_and_does_not_hide_other_lines(self):
        self.assertEqual([line["allowed_cents"] for line in self.at(4, "C115")["lines"]], [0, 1500])
        self.assertEqual(self.at(4, "C115")["paid_cents"], 1500)
        for identity in ("C15", "C118"):
            current = self.at(4, identity)
            self.assertEqual(current["allowed_cents"], 0)
            self.assertEqual(current["paid_cents"], 0)
            self.assertTrue(all(line["status"] == "excluded" for line in current["lines"]))
            self.assertFalse(any(r["claim_id"] == identity for r in self.snapshots[3]["requests"]))

    def test_deadlines_are_inclusive_and_first_filed_dates_survive_repair(self):
        for identity in ("C11", "C110", "C111"):
            self.assertNotIn("late_filing", self.codes(1, identity))
        self.assertIn("late_filing", self.codes(1, "C112"))
        self.assertIn("late_filing", self.codes(1, "C12"))
        self.assertNotIn("late_filing", self.codes(3, "C12"))
        line = self.at(3, "C12")["lines"][0]
        self.assertEqual(line["first_filed"], "2026-09-02")
        self.assertEqual(line["filing_deadline"], "2026-09-01")
        self.assertEqual(line["exception"]["covered_issues"], ["late_filing"])
        self.assertIn("filing_before_evidence", self.codes(4, "C113"))
        self.assertEqual(self.at(4, "C113")["status"], "held")

    def test_international_late_and_missing_permission_are_distinct(self):
        self.assertIn("late_permit", self.codes(4, "C10"))
        self.assertNotIn("permit_unapproved", self.codes(4, "C10"))
        self.assertIn("permit_unapproved", self.codes(4, "C25"))
        self.assertFalse(self.at(4, "C10")["permission"]["historical_permission"])
        self.assertFalse(self.at(4, "C25")["permission"]["historical_permission"])
        self.assertTrue(self.at(4, "C11")["permission"]["historical_permission"])
        self.assertIsNone(self.at(4, "C11")["permission"]["current_permit_authority"])

    def test_prepaid_final_claim_excludes_only_the_confirmed_old_cost(self):
        # INITIAL p3 + UPDATES p3, Finance rows8/30/35/48: oldCOST-03
        # settled200; final claim reviews200+50 and requests onlythe new50.
        for batch in (3, 4):
            old, final = self.at(batch, "C03"), self.at(batch, "C24")
            self.assertEqual((old["allowed_cents"], old["paid_cents"]), (20000, 20000))
            self.assertNotIn(old["status"], {"held", "rejected", "withdrawn"})
            self.assertEqual(final["allowed_cents"], 5000)
            self.assertEqual({line["cost_id"]: line["allowed_cents"] for line in final["lines"]},
                             {"COST-03": 0, "COST-24": 5000})
            self.assertEqual(final["prior_costs"]["exclusion_by_cost_cents"], {"COST-03": 20000})
            self.assertEqual(final["prior_costs"]["original_request_ids"], ["REQ-C03"])
            self.assertEqual(sum(line["reviewed_cents"] for line in final["lines"]), 25000)
            self.assertEqual(self.request(batch, "REQ-C24")["amount_cents"], 5000)
        self.assertEqual(self.at(3, "C24")["paid_cents"], 0)
        self.assertEqual(self.at(4, "C24")["paid_cents"], 5000)

    def test_withdrawal_and_explicit_rejection_remain_source_nonpayment_outcomes(self):
        for batch in range(1, 5):
            self.assertEqual(self.at(batch, "C13")["status"], "withdrawn")
            self.assertIn("withdrew", self.at(batch, "C13")["reason"].lower())
            self.assertEqual(self.at(batch, "C14")["status"], "rejected")
            self.assertIn("Client work was cancelled", self.at(batch, "C14")["reason"])
            for identity in ("C13", "C14"):
                self.assertEqual(self.at(batch, identity)["paid_cents"], 0)
                self.assertFalse(any(r["claim_id"] == identity for r in self.snapshots[batch - 1]["requests"]))

    def test_returned_work_and_missing_replies_do_not_gain_authority_from_budget(self):
        for identity in ("C09", "C21"):
            self.assertEqual(self.at(1, identity)["status"], "held")
            self.assertIn("current_approvals", self.codes(1, identity))
            self.assertFalse(self.at(1, identity)["current_review"]["current"])
        self.assertIn("current_approvals", self.codes(4, "C26"))
        self.assertFalse(self.at(4, "C26")["source_financial_prerequisites_observed"])
        self.assertFalse(any(r["claim_id"] in {"C21", "C26"} for r in self.snapshots[3]["requests"]))

    def test_partial_settlements_and_failed_retry_keep_the_original_request(self):
        for identity, paid in (("C16", [0, 4000, 10000, 10000]),
                               ("C17", [0, 0, 0, 10000]),
                               ("C120", [0, 3000, 7500, 7500])):
            self.assertEqual([self.at(b, identity)["paid_cents"] for b in range(1, 5)], paid)
            self.assertEqual({r["request_id"] for s in self.snapshots for r in s["requests"]
                              if r["claim_id"] == identity}, {f"REQ-{identity}"})
        self.assertEqual(self.request(2, "REQ-C17")["status"], "held")
        self.assertTrue(self.request(3, "REQ-C17")["retry_authorized"])
        self.assertEqual(self.request(4, "REQ-C17")["status"], "settled")

    def test_same_total_c09_revision_is_rechecked_and_first_acceptance_is_current(self):
        self.assertEqual([self.at(b, "C09")["revision"] for b in range(1, 5)], [1, 1, 2, 2])
        current = self.at(3, "C09")
        self.assertEqual(current["trip_id"], "T09B")
        self.assertEqual([line["cost_id"] for line in current["lines"]], ["COST-09B"])
        self.assertEqual(set(current["material_changes"]), {"trip", "lines"})
        self.assertTrue(current["current_review"]["current"])
        self.assertFalse(current["finance_resolution_required"])
        self.assertEqual(current["paid_cents"], 0)
        self.assertEqual(self.request(3, "REQ-C09")["accepted_arrival_batch"], 3)
        self.assertEqual(self.at(4, "C09")["paid_cents"], 8000)

    def test_c19_full_recheck_preserves_old_money_and_requires_current_resolution(self):
        self.assertEqual([self.at(b, "C19")["revision"] for b in range(1, 5)], [1, 1, 2, 3])
        self.assertEqual([self.at(b, "C19")["allowed_cents"] for b in range(1, 5)], [10000, 10000, 8000, 8000])
        self.assertEqual([self.at(b, "C19")["paid_cents"] for b in range(1, 5)], [0, 10000, 10000, 8000])
        current = self.at(3, "C19")
        self.assertEqual(current["status"], "held")
        self.assertEqual(current["balance_cents"], -2000)
        self.assertTrue({"travel_cancellation", "current_approvals", "finance_resolution", "overpayment"}
                        <= self.codes(3, "C19"))
        final = self.at(4, "C19")
        self.assertEqual((final["gross_paid_cents"], final["refunded_cents"], final["paid_cents"]), (10000, 2000, 8000))
        self.assertTrue(final["finance_resolution_required"])
        self.assertEqual(final["current_resolution_event_ids"], ["F-C19-4"])
        self.assertTrue(final["current_review"]["current"])
        self.assertEqual(final["balance_cents"], 0)
        self.assertEqual([row["revision"] for row in final["history"]], [1, 2, 3])

    def test_c20_overpayment_refund_and_resolution_are_separate_facts(self):
        self.assertEqual([self.at(b, "C20")["paid_cents"] for b in range(1, 5)], [0, 11000, 10000, 10000])
        self.assertEqual(self.at(2, "C20")["balance_cents"], -1000)
        self.assertIn("overpayment", self.codes(2, "C20"))
        self.assertEqual(self.at(3, "C20")["refunded_cents"], 1000)
        self.assertEqual(self.at(4, "C20")["current_resolution_event_ids"], ["F-C20-3"])
        refund = next(event for event in self.snapshots[2]["finance_events"] if event["event_id"] == "F-C20-2")
        self.assertEqual(refund["original_event_id"], "F-C20-1")

    def test_old_c18_trip_cancellation_does_not_retire_replacement_trip_or_erase_late_money(self):
        process = self.cancellation(4, "TC018")
        self.assertEqual((process["target_type"], process["trip_id"], process["trip_revision"]), ("trip", "T18", 1))
        self.assertEqual(process["original_request_ids"], ["REQ-C18"])
        current = self.at(4, "C18")
        self.assertEqual((current["revision"], current["trip_id"]), (2, "T18B"))
        self.assertFalse(current["trip_retired_for_future_arrangements"])
        self.assertEqual((current["gross_paid_cents"], current["paid_cents"]), (10000, 10000))
        self.assertEqual(self.request(4, "REQ-C18")["amount_cents"], 0)
        self.assertEqual(self.request(4, "REQ-C18")["status"], "held")
        self.assertEqual(current["status"], "held")
        self.assertNotIn(self.at(4, "C01")["status"], {"held", "rejected", "withdrawn"})

    def test_permit_only_c121_cancellation_keeps_trip_and_historical_permission(self):
        process = self.cancellation(4, "TC121")
        self.assertEqual((process["target_type"], process["trip_id"], process["permit_id"]), ("permit", "T121", "P121"))
        self.assertTrue(process["permit_retired"])
        self.assertFalse(process["trip_retired"])
        for batch in range(1, 5):
            self.assertTrue(self.at(batch, "C121")["permission"]["historical_permission"])
            self.assertNotIn("permit_unapproved", self.codes(batch, "C121"))
        final = self.at(4, "C121")
        self.assertFalse(final["trip_retired_for_future_arrangements"])
        self.assertFalse(final["permission"]["arrangements_authorized"])
        self.assertEqual((final["allowed_cents"], final["paid_cents"]), (2000, 2000))
        self.assertFalse(final["finance_resolution_required"])
        self.assertEqual(self.request(4, "REQ-C121")["accepted_arrival_batch"], 3)

    def test_no_claim_p122_cancellation_is_independent_and_financially_empty(self):
        requested, confirmed = self.cancellation(1, "TC122"), self.cancellation(4, "TC122")
        self.assertEqual(requested["status"], "requested")
        self.assertEqual(requested["next_owner"], "SUP-01")
        self.assertIsNone(requested["effective_at"])
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual((confirmed["trip_id"], confirmed["permit_id"]), ("T122", "P122"))
        self.assertEqual(confirmed["financial_status"], "no-financial-effect")
        self.assertEqual(confirmed["affected_claim_ids"], [])
        self.assertEqual(confirmed["original_request_ids"], [])
        self.assertTrue(confirmed["trip_retired"])
        self.assertTrue(confirmed["permit_retired"])
        self.assertEqual(len(confirmed["admitted_cancellation_event_ids"]), 2)
        final = self.snapshots[-1]
        self.assertEqual({row["cancellation_id"] for row in final["travel_cancellations"]},
                         {"TC018", "TC019", "TC121", "TC122"})
        cancellation_ids = {key for row in final["travel_cancellations"] for key in row["admitted_cancellation_event_ids"]}
        self.assertEqual(len(cancellation_ids), 8)
        self.assertFalse(cancellation_ids & set(final["admitted_event_ids"]))

    def test_isolated_completion_policy_floor_cannot_close_accepted_unpaid_or_held_work(self):
        proposed = build_run(MANIFEST, completion_accepted=True)
        def selected(batch, identity):
            return next(row for row in proposed["snapshots"][batch - 1]["claims"] if row["claim_id"] == identity)
        self.assertNotEqual(selected(1, "C01")["status"], "closed-reimbursed")
        self.assertEqual(selected(2, "C01")["status"], "closed-reimbursed")
        self.assertEqual(selected(3, "C19")["status"], "held")
        self.assertEqual(selected(4, "C19")["status"], "closed-reimbursed")
        self.assertEqual(selected(4, "C18")["status"], "held")
        self.assertEqual(selected(4, "C08")["status"], "held")
        self.assertEqual(selected(4, "C118")["status"], "closed-no-payment")
        self.assertEqual(selected(4, "C13")["status"], "withdrawn")
        self.assertEqual(selected(4, "C14")["status"], "rejected")
        self.assertTrue(all(not row["financial_completion_accepted"]
                            for snapshot in self.snapshots for row in snapshot["claims"]))

    def test_repeated_preview_is_deterministic_and_does_not_change_source_bytes(self):
        before = sha256(MANIFEST.read_bytes()).hexdigest()
        self.assertEqual(build_run(MANIFEST), self.result)
        self.assertEqual(sha256(MANIFEST.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
