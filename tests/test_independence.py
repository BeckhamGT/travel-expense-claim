from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from travel_expense_claim.independence import Check, DOMAINS, Dependency, Work, budget_remaining, evaluate, visible_at
from travel_expense_claim.verify_independence import Sources, SourceError, inspect, initial_claims, payment_check, receipt_records


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"
SUBJECTS = ["claim:C08:1", "claim:C01:1", "permit:P122:1"]


def clear_work(key):
    return Work(key, tuple(Check(domain, True, "Required fact verified", "owner", "Continue within scope", ("source:record",)) for domain in sorted(DOMAINS)))


def held_work(key, domain="evidence"):
    work = clear_work(key)
    return replace(work, checks=tuple(replace(check, satisfied=False) if check.domain == domain else check for check in work.checks))


class DependencyTests(unittest.TestCase):
    def test_unrelated_work_continues_and_real_dependency_propagates(self):
        blocked = held_work("evidence-A")
        dependent = replace(clear_work("claim-B"), dependencies=(Dependency("evidence-A", "Needs the same unresolved payment proof", "receipt:A"),))
        downstream = replace(clear_work("claim-C"), dependencies=(Dependency("claim-B", "Needs its verified obligation", "request:B"),))
        result = evaluate([blocked, dependent, downstream, clear_work("claim-D")])
        self.assertFalse(result["evidence-A"]["may_continue"])
        self.assertFalse(result["claim-B"]["may_continue"])
        self.assertFalse(result["claim-C"]["may_continue"])
        self.assertTrue(result["claim-D"]["may_continue"])
        self.assertEqual(result["claim-B"]["holds"][0]["prerequisite"], "evidence-A")

    def test_shared_reviewer_or_source_is_not_an_edge(self):
        result = evaluate([held_work("claim-A"), clear_work("claim-B")])
        self.assertTrue(result["claim-B"]["may_continue"])

    def test_missing_dependency_and_cycle_are_owned_holds(self):
        a = replace(clear_work("A"), dependencies=(Dependency("B", "Dependent authorization", "decision:1"),))
        self.assertFalse(evaluate([a])["A"]["may_continue"])
        b = replace(clear_work("B"), dependencies=(Dependency("A", "Dependent evidence", "decision:2"),))
        result = evaluate([a, b, clear_work("C")])
        self.assertFalse(result["A"]["may_continue"])
        self.assertFalse(result["B"]["may_continue"])
        self.assertTrue(result["C"]["may_continue"])

    def test_missing_domain_never_proves_independence(self):
        work = clear_work("A")
        work = replace(work, checks=tuple(c for c in work.checks if c.domain != "obligations"))
        self.assertFalse(evaluate([work])["A"]["may_continue"])

    def test_explicit_held_authority_or_budget_only_affects_dependents(self):
        for domain in ["authority", "budget", "obligations"]:
            with self.subTest(domain=domain):
                dependent = replace(clear_work("B"), dependencies=(Dependency("A", "Actual shared prerequisite", "source:shared-fact"),))
                result = evaluate([held_work("A", domain), dependent, clear_work("C")])
                self.assertFalse(result["B"]["may_continue"])
                self.assertTrue(result["C"]["may_continue"])

    def test_arrival_precedes_joins_even_if_rows_are_out_of_order(self):
        rows = [{"Arrival batch": 2, "event": "settled"}, {"Arrival batch": 1, "event": "accepted"}]
        self.assertEqual([r["event"] for r in visible_at(rows, 1)], ["accepted"])
        self.assertEqual(len(visible_at(rows, 2)), 2)
        with self.assertRaises(ValueError):
            visible_at([{"Arrival batch": None}], 1)


class BudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = Sources(MANIFEST).table("Budget")

    def test_prior_settled_portion_is_not_subtracted_twice(self):
        self.assertEqual(budget_remaining(self.ledger, []), 1500000)
        accepted = [{"request_id": "REQ-A", "amount_cents": 10000}]
        self.assertEqual(budget_remaining(self.ledger, accepted), 1490000)
        self.assertEqual(budget_remaining(self.ledger, accepted * 2), 1490000)

    def test_existing_request_replay_and_conflict(self):
        self.assertEqual(budget_remaining(self.ledger, [{"request_id": "OLD-1", "amount_cents": 300000}]), 1500000)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            budget_remaining(self.ledger, [{"request_id": "A", "amount_cents": 100}, {"request_id": "A", "amount_cents": 101}])

    def test_exhaustion_and_missing_definition_are_not_adequate_funds(self):
        self.assertLess(budget_remaining(self.ledger, [{"request_id": "A", "amount_cents": 1500001}]), 0)
        with self.assertRaisesRegex(ValueError, "Missing allocation"):
            budget_remaining([], [])


class NativeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.baseline = inspect(MANIFEST, SUBJECTS)

    def mutated(self, tab, change):
        original = Sources.table

        def load(sources, name):
            rows = deepcopy(original(sources, name))
            if name == tab:
                change(rows)
            return rows

        with patch.object(Sources, "table", load):
            return inspect(MANIFEST, SUBJECTS)

    def test_primary_source_replay_three_scoped_outcomes(self):
        result = self.baseline
        self.assertEqual(result["mode"], "offline retained-source verification")
        held, ordinary, permit = (result["subjects"][key] for key in SUBJECTS)
        self.assertFalse(held["may_continue"])
        self.assertIsNone(held["entitlement_cents"])
        issue = next(h for h in held["holds"] if h["domain"] == "evidence")
        self.assertEqual(issue["owner"], "EMP-01")
        self.assertIn("C08 revision 1 / COST-08", issue["fact"])
        self.assertIn("RECEIPTS:page4", issue["source_refs"])
        self.assertTrue(issue["next_action"])
        self.assertTrue(ordinary["may_continue"])
        self.assertEqual(ordinary["recorded_request_ids"], ["REQ-C01"])
        self.assertEqual(ordinary["recorded_obligation_cents"], 10000)
        self.assertEqual(ordinary["confirmed_paid_cents"], 0)
        self.assertFalse(ordinary["financially_closed"])
        self.assertEqual(ordinary["visible_settlement_event_ids"], [])
        self.assertTrue(permit["may_continue"])
        self.assertIsNone(permit["claim_id"])
        self.assertEqual(permit["cancellation_status"], "requested")
        self.assertTrue(permit["arrangements_paused"])
        self.assertEqual(permit["cancellation_owner"], "SUP-01")
        self.assertNotIn("claim:C122:1", result["subjects"])

    def test_complete_shared_budget_is_checked_independently(self):
        for result in self.baseline["subjects"].values():
            self.assertEqual(result["budget_remaining_cents"], 316585)
        self.assertTrue(self.baseline["subjects"]["claim:C01:1"]["may_continue"])

    def test_receipt_parser_reads_the_actual_employee_label(self):
        self.assertEqual(len(receipt_records(self.sources)), 203)

    def test_payment_repair_must_match_every_binding(self):
        claim = initial_claims(self.sources)["C08"]
        line = claim["lines"][0]
        receipt = receipt_records(self.sources)[line["receipt_id"]]
        good = {"Expense reference": "COST-08", "Employee ID": "EMP-01", "Trip reference": "T08", "Currency": "EUR", "Gross amount": Decimal("120.00"), "Receipt reference": "R-COST-08", "Payment status": "settled", "Paid date": "2026-09-01", "_ref": "isolated-fixture:payment"}
        self.assertTrue(payment_check(claim, line, receipt, [good], "2026-11-15").satisfied)
        wrong = {"Expense reference": "OTHER", "Employee ID": "EMP-02", "Trip reference": "T01", "Currency": "USD", "Gross amount": Decimal("119.99"), "Receipt reference": "OTHER", "Payment status": "pending", "Paid date": "2026-11-16"}
        for key, value in wrong.items():
            with self.subTest(binding=key):
                self.assertFalse(payment_check(claim, line, receipt, [{**good, key: value}], "2026-11-15").satisfied)
        self.assertFalse(payment_check(claim, line, receipt, [good, good], "2026-11-15").satisfied)

    def test_another_subject_revision_or_actor_does_not_authorize_c01(self):
        for field, value in [("Subject type", "permit"), ("Subject reference", "C08"), ("Revision", 2), ("Reviewer", "EMP-01"), ("Source revisions", "POL-OLD\nSRC-D-3")]:
            def change(rows):
                for row in rows:
                    if row["Subject reference"] == "C01" and row["Review roles"] == "administration":
                        row[field] = value
            with self.subTest(field=field):
                output = self.mutated("Review ledger", change)
                self.assertFalse(output["subjects"]["claim:C01:1"]["may_continue"])

    def test_actual_budget_shortfall_blocks_dependent_subject(self):
        def reduce_allocation(rows):
            rows[0]["Allocation or commitment (EUR)"] = Decimal("5000")
        output = self.mutated("Budget", reduce_allocation)
        item = output["subjects"]["claim:C01:1"]
        self.assertFalse(item["may_continue"])
        self.assertTrue(any(h["domain"] == "budget" for h in item["holds"]))

    def test_material_packet_context_cannot_borrow_current_authority(self):
        for field in ["Business purpose", "Client", "Schedule coverage", "Alternatives considered", "Reviewed estimate (EUR)"]:
            def mismatch(rows):
                for row in rows:
                    if row["Trip reference"] == ("T122" if field == "Reviewed estimate (EUR)" else "T01"):
                        row[field] = Decimal("800") if field == "Reviewed estimate (EUR)" else "Different material context"
            with self.subTest(field=field):
                result = self.mutated("Review packets", mismatch)
                subject = "permit:P122:1" if field == "Reviewed estimate (EUR)" else "claim:C01:1"
                self.assertFalse(result["subjects"][subject]["may_continue"])

    def test_later_return_or_rejection_reopens_current_review(self):
        for outcome in ["return", "reject"]:
            def returned(rows):
                for row in rows:
                    if row["Subject reference"] == "C01" and row["Review roles"] == "budget_owner":
                        later = {**row, "Outcome": outcome, "Repair requested": "Resolve funding facts", "Decision time (UTC)": "2026-09-04 12:00:00 UTC", "_ref": "isolated-fixture:later-reply"}
                        rows.append(later)
                        return
            with self.subTest(outcome=outcome):
                output = self.mutated("Review ledger", returned)
                self.assertFalse(output["subjects"]["claim:C01:1"]["may_continue"])
                self.assertTrue(output["subjects"]["permit:P122:1"]["may_continue"])

    def test_invalid_cancellation_request_is_not_admitted(self):
        for field, value in [("Cancelled subject", "invalid-domain"), ("Cancellation activity reference", None), ("Cancellation reference", None), ("Business reason", None), ("Acting employee or supervisor", "FIN-01")]:
            def invalid(rows):
                rows[0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(SourceError, "Cancellation requires"):
                    self.mutated("Travel cancellations", invalid)

    def test_conflicting_request_cannot_be_counted_as_independent(self):
        def conflict(rows):
            accepted = [r for r in rows if r["Arrival batch"] == 1 and r["Activity type"] == "accepted"]
            accepted[1]["Request reference"] = accepted[0]["Request reference"]
        with self.assertRaisesRegex(SourceError, "Conflicting"):
            self.mutated("Finance activity", conflict)

    def test_future_payloads_cannot_change_initial_observations(self):
        def poison_future(rows):
            for row in rows:
                if row["Arrival batch"] > 1:
                    row["Amount (EUR)"] = Decimal("99999999")
                    row["Activity type"] = "untrusted later instructions"
        self.assertEqual(self.baseline, self.mutated("Finance activity", poison_future))
        def poison_confirmation(rows):
            for row in rows:
                if row["Arrival batch"] > 1:
                    row["Action"] = "conflicting later confirmation"
        self.assertEqual(self.baseline, self.mutated("Travel cancellations", poison_confirmation))

    def test_later_revision_policy_is_explicitly_not_selected_here(self):
        with self.assertRaisesRegex(SourceError, "choice 2"):
            inspect(MANIFEST, SUBJECTS, batch=3)


if __name__ == "__main__":
    unittest.main()
