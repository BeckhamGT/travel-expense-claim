from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch

from travel_expense_claim.recheck import claim_versions, filing_deadline, inspect, material_changes
from travel_expense_claim.verify_independence import Sources


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/runs/review-20261017033849Z/sources.json"
SUBJECTS = ["C09", "C19", "C01", "C08"]


class FullRecheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = inspect(MANIFEST, SUBJECTS)

    def at(self, batch, claim):
        return self.result["batches"][batch - 1]["claims"][claim]

    def test_c09_same_total_identity_change_rechecks_new_evidence_and_roles(self):
        old, current, settled = (self.at(batch, "C09") for batch in (1, 3, 4))
        self.assertEqual(old["calculated_entitlement_cents"], 8000)
        self.assertFalse(old["authority"]["current"])
        self.assertEqual(current["calculated_entitlement_cents"], 8000)
        self.assertEqual(current["trip"], "T09B")
        self.assertEqual(current["lines"][0]["cost_id"], "COST-09B")
        self.assertEqual(set(current["material_changes"]), {"trip", "lines"})
        self.assertTrue(current["current_recheck_supported"])
        self.assertEqual(len(current["authority"]["valid_decision_ids"]), 3)
        self.assertEqual(current["finance"]["request_ids"], ["REQ-C09"])
        self.assertEqual(current["finance"]["net_paid_cents"], 0)
        self.assertFalse(current["finance_resolution_required"])
        self.assertEqual(settled["finance"]["net_paid_cents"], 8000)
        self.assertEqual([v["revision"] for v in settled["revision_history"]], [1, 2])

    def test_c19_amount_only_correction_preserves_payment_and_holds_cancellation(self):
        previous, current = (self.at(batch, "C19") for batch in (2, 3))
        self.assertEqual(previous["calculated_entitlement_cents"], 10000)
        self.assertEqual(previous["finance"]["net_paid_cents"], 10000)
        self.assertEqual(current["revision"], 2)
        self.assertEqual(current["calculated_entitlement_cents"], 8000)
        self.assertEqual(current["finance"]["net_paid_cents"], 10000)
        self.assertEqual(current["calculated_balance_cents"], -2000)
        self.assertFalse(current["authority"]["current"])
        self.assertFalse(current["current_recheck_supported"])
        self.assertTrue(current["competing_replacement_requests_held"])
        codes = {item["code"] for item in current["issues"] if item["blocking"]}
        self.assertTrue({"travel_cancellation", "current_approvals", "finance_resolution", "overpayment"} <= codes)
        self.assertEqual(current["lines"][0]["exception"]["covered_issues"], [])

    def test_c19_current_revision_refund_resolution_and_reviews_agree_without_acceptance(self):
        current = self.at(4, "C19")
        self.assertEqual(current["revision"], 3)
        self.assertTrue(current["current_recheck_supported"])
        self.assertEqual(current["calculated_entitlement_cents"], 8000)
        self.assertEqual((current["finance"]["paid_cents"], current["finance"]["refunded_cents"], current["finance"]["net_paid_cents"]), (10000, 2000, 8000))
        self.assertEqual(current["calculated_balance_cents"], 0)
        self.assertTrue(current["finance_resolution_required"])
        self.assertEqual(current["current_resolution_event_ids"], ["F-C19-4"])
        self.assertEqual(current["finance"]["request_ids"], ["REQ-C19"])
        self.assertTrue(current["trip_retired_for_future_arrangements"])
        self.assertEqual([v["revision"] for v in current["revision_history"]], [1, 2, 3])
        self.assertFalse(current["financial_completion_accepted"])
        original = current["original_requests"]["REQ-C19"]
        self.assertEqual(original["initial_obligation_cents"], 10000)
        self.assertEqual(original["current_obligation_cents"], 8000)
        finding = next(item for item in current["issues"] if item["code"] == "travel_cancellation")
        self.assertEqual(finding["resolved_by"], "UPDATES:page7")
        self.assertIn("REGISTERS-TRAVEL-CANCELLATIONS:row13", finding["source_refs"])

    def test_batch_one_is_identical_to_replay_without_later_batches(self):
        early = inspect(MANIFEST, SUBJECTS, through_batch=1)
        self.assertEqual(early["batches"][0], self.result["batches"][0])
        self.assertEqual(self.at(1, "C19")["revision"], 1)
        self.assertEqual(self.at(1, "C01")["finance"]["net_paid_cents"], 0)
        self.assertEqual(self.at(1, "C01")["finance"]["admitted_event_ids"], ["F-C01-accepted"])
        self.assertEqual(self.at(1, "C09")["revision_history"], [dict(revision=1, arrival_batch=1, source_ref="INITIAL:page9", trip="T09", employee="EMP-01")])

    def test_invalid_future_exception_cannot_stop_batch_one_or_unrelated_claim(self):
        original = Sources.read
        def changed(sources, identity):
            result = deepcopy(original(sources, identity))
            if identity == "UPDATES-PAGES":
                result[-1]["text"] = result[-1]["text"].replace("Allowed original amount: 80.00", "Allowed original amount: INVALID")
            return result
        with patch.object(Sources, "read", changed):
            early = inspect(MANIFEST, SUBJECTS, through_batch=1)
            full = inspect(MANIFEST, SUBJECTS)
        self.assertEqual(early["batches"][0], self.result["batches"][0])
        self.assertTrue(full["batches"][3]["claims"]["C01"]["current_recheck_supported"])
        current = full["batches"][3]["claims"]["C19"]
        self.assertIsNone(current["calculated_entitlement_cents"])
        self.assertIn("claim_payload", {issue["code"] for issue in current["issues"]})

    def test_independent_controls_and_no_claim_cancellation_remain_independent(self):
        for batch in range(1, 5):
            self.assertTrue(self.at(batch, "C01")["current_recheck_supported"])
            self.assertIsNone(self.at(batch, "C08")["calculated_entitlement_cents"])
            self.assertFalse(self.at(batch, "C08")["current_recheck_supported"])
            c08 = next(issue for issue in self.at(batch, "C08")["issues"] if issue["code"] == "paid_evidence")
            self.assertEqual(c08["owner"], "EMP-01")
            self.assertIn("R-COST-08", c08["next_action"])
        self.assertEqual(self.at(4, "C01")["finance"]["net_paid_cents"], 10000)
        self.assertIn("F-C01-1", self.result["batches"][3]["finance_replayed_event_ids"])
        processes = self.result["batches"][3]["cancellation_processes"]["processes"]
        permit = next(process for process in processes if process["cancellation_id"] == "TC122")
        self.assertEqual(permit["status"], "confirmed")
        self.assertEqual(permit["permit"], "P122")
        self.assertNotIn("C122", self.result["batches"][3]["claims"])

    def test_shared_budget_charges_overpaid_c19_once_until_refund(self):
        for batch, charge in ((1, 10000), (2, 10000), (3, 10000), (4, 8000)):
            budget = self.at(batch, "C01")["budget"]
            self.assertTrue(budget["sufficient"])
            c19 = [item for item in budget["charges"] if item["request_id"] == "REQ-C19"]
            self.assertEqual(len(c19), 1)
            self.assertEqual(c19[0]["charged_cents"], charge)

    def test_shared_cost_dependencies_use_accepted_basis_not_superseded_unaccepted_costs(self):
        versions = claim_versions(Sources(MANIFEST))
        for revision, should_hold in ((1, False), (2, True)):
            with self.subTest(revision=revision):
                changed = deepcopy(versions)
                selected = next(v for v in changed if v["id"] == "C09" and v["revision"] == revision)
                selected["lines"][0]["cost_id"] = "COST-01"
                with patch("travel_expense_claim.recheck.claim_versions", return_value=changed):
                    current = inspect(MANIFEST, ["C01", "C09"])["batches"][2]["claims"]
                self.assertTrue(current["C01"]["current_recheck_supported"])
                self.assertEqual("REQ-C01" in current["C09"]["shared_cost_request_ids"], should_hold)
                self.assertEqual(current["C09"]["current_recheck_supported"], not should_hold)

    def with_tables(self, transform):
        original = Sources.table
        def changed(sources, name):
            rows = deepcopy(original(sources, name))
            transform(name, rows)
            return rows
        with patch.object(Sources, "table", changed):
            return inspect(MANIFEST, SUBJECTS)

    def test_real_budget_deficit_holds_dependent_work_without_forging_authority(self):
        def transform(name, rows):
            if name == "Budget":
                rows[0]["Allocation or commitment (EUR)"] = 5000
        result = self.with_tables(transform)
        c01 = result["batches"][0]["claims"]["C01"]
        self.assertFalse(c01["current_recheck_supported"])
        self.assertTrue(c01["authority"]["current"])
        self.assertIn("shared_budget", {issue["code"] for issue in c01["issues"]})

    def test_unadmitted_conflicting_commitment_creates_real_shared_budget_uncertainty(self):
        def transform(name, rows):
            if name == "Finance activity":
                original = next(row for row in rows if row["Activity reference"] == "F-C19-accepted")
                rows.append({**original, "Arrival batch": 3, "Obligation (EUR)": 99999, "_ref": "isolated-fixture:conflict"})
        result = self.with_tables(transform)
        c01 = result["batches"][2]["claims"]["C01"]
        self.assertFalse(c01["budget"]["sufficient"])
        self.assertTrue(c01["budget"]["uncertainty"])
        self.assertEqual(c01["finance"]["net_paid_cents"], 10000)

    def test_amount_exception_cannot_waive_unpaid_evidence(self):
        def transform(name, rows):
            if name == "Merchant payments":
                rows[:] = [row for row in rows if row["Expense reference"] != "COST-19"]
        result = self.with_tables(transform)
        c19 = result["batches"][3]["claims"]["C19"]
        self.assertIsNone(c19["calculated_entitlement_cents"])
        self.assertEqual(c19["finance"]["net_paid_cents"], 8000)
        self.assertIn("paid_evidence", {issue["code"] for issue in c19["issues"]})

    def test_cancellation_conflict_follows_admitted_identity_after_target_tampering(self):
        def transform(name, rows):
            if name == "Travel cancellations":
                confirmed = next(row for row in rows if row["Cancellation activity reference"] == "TC019-confirmed")
                rows.append({**confirmed, "Arrival batch": 4, "Trip reference": "T122", "Permit reference": "P122", "Permit revision": 1, "_ref": "isolated-fixture:conflict"})
        result = self.with_tables(transform)
        current = result["batches"][3]["claims"]["C19"]
        self.assertFalse(current["current_recheck_supported"])
        self.assertEqual(current["finance"]["net_paid_cents"], 8000)
        self.assertIn("cancellation_import", {issue["code"] for issue in current["issues"]})

    def test_invalid_other_trip_revision_does_not_block_current_revision(self):
        def transform(name, rows):
            if name == "Travel cancellations":
                requested = next(row for row in rows if row["Cancellation activity reference"] == "TC019-requested")
                rows.append({**requested, "Arrival batch": 4, "Trip revision": 2,
                             "Cancellation reference": "OTHER", "Cancellation activity reference": "OTHER-requested",
                             "_ref": "isolated-fixture:other-revision"})
        result = self.with_tables(transform)
        self.assertTrue(result["batches"][3]["claims"]["C19"]["current_recheck_supported"])

    def test_wrong_cancellation_reference_does_not_waive_current_finding(self):
        sources = Sources(MANIFEST)
        versions = deepcopy(claim_versions(sources))
        next(v for v in versions if v["id"] == "C19" and v["revision"] == 3)["exception"]["cancellation_id"] = "TC122"
        with patch("travel_expense_claim.recheck.claim_versions", return_value=versions):
            result = inspect(MANIFEST, ["C19"])
        issue = next(item for item in result["batches"][3]["claims"]["C19"]["issues"] if item["code"] == "travel_cancellation")
        self.assertTrue(issue["blocking"])

    def test_late_imported_old_resolution_is_not_current_revision_proof(self):
        def transform(name, rows):
            if name == "Finance activity":
                resolution = next(row for row in rows if row["Activity reference"] == "F-C19-4")
                resolution["Activity time (UTC)"] = "2026-09-13 13:00:00 UTC"
        result = self.with_tables(transform)
        current = result["batches"][3]["claims"]["C19"]
        self.assertEqual(current["finance"]["resolution_event_ids"], ["F-C19-4"])
        self.assertEqual(current["finance"]["net_paid_cents"], 8000)
        self.assertEqual(current["current_resolution_event_ids"], [])
        self.assertFalse(current["current_recheck_supported"])
        self.assertIn("finance_resolution", {issue["code"] for issue in current["issues"]})

    def test_exception_actor_and_cost_cannot_substitute_for_current_authority(self):
        versions = claim_versions(Sources(MANIFEST))
        for key, value in (("actor", "EMP-01"), ("cost_id", "COST-09B")):
            with self.subTest(key=key):
                changed = deepcopy(versions)
                latest = next(v for v in changed if v["id"] == "C19" and v["revision"] == 3)
                latest["exception"][key] = value
                with patch("travel_expense_claim.recheck.claim_versions", return_value=changed):
                    current = inspect(MANIFEST, ["C19"])["batches"][3]["claims"]["C19"]
                self.assertFalse(current["current_recheck_supported"])
                self.assertIn("invalid_exception", {issue["code"] for issue in current["issues"]})

    def test_same_total_trip_change_is_material_and_old_exception_cannot_bind_new_revision(self):
        versions = claim_versions(Sources(MANIFEST))
        old, current = [v for v in versions if v["id"] == "C09"]
        self.assertIn("trip", material_changes(old, current))
        changed = deepcopy(versions)
        latest = next(v for v in changed if v["id"] == "C19" and v["revision"] == 3)
        latest["exception"]["revision"] = 2
        with patch("travel_expense_claim.recheck.claim_versions", return_value=changed):
            result = inspect(MANIFEST, ["C19"])
        item = result["batches"][3]["claims"]["C19"]
        self.assertEqual(item["calculated_entitlement_cents"], 10000)
        self.assertFalse(item["current_recheck_supported"])
        self.assertIn("invalid_exception", {issue["code"] for issue in item["issues"]})

    def test_replay_is_deterministic_and_retained_history_bytes_remain_unchanged(self):
        paths = [MANIFEST, ROOT / "interviews/project-d-travel-expense-claim-20261017-0334.md",
                 ROOT / "artifacts/verification/choice-1/independence.json"]
        before = [sha256(path.read_bytes()).hexdigest() for path in paths]
        self.assertEqual(inspect(MANIFEST, SUBJECTS), self.result)
        self.assertEqual(before, [sha256(path.read_bytes()).hexdigest() for path in paths])
        self.assertEqual(before[0], "23895ede4a65fa089ad8b73812b9182e4f1d8aff85516aa5d93d4b8a43aff5a5")
        self.assertEqual(before[1], "8099acf7f137edf8521c50b3d80c1dd76fe6a4dd175356fa7b1648199b1606e2")

    def test_deadline_uses_calendar_months_and_clamps_nonexistent_day(self):
        self.assertEqual(filing_deadline("2026-07-31"), date(2026, 9, 30))
        self.assertEqual(filing_deadline("2026-08-31"), date(2026, 10, 31))
        self.assertEqual(filing_deadline("2026-12-31"), date(2027, 2, 28))


if __name__ == "__main__":
    unittest.main()
