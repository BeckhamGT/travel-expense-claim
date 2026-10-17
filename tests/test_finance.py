from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import unittest

from travel_expense_claim.finance import summarize_finance
from travel_expense_claim.independence import visible_at
from travel_expense_claim.verify_independence import Sources, initial_claims


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"
PEOPLE = {employee: {
    "Employee ID": employee, "Payee ID": employee, "Finance officer": "FIN-01",
} for employee in ("EMP-01", "EMP-02")}
CLAIMS = {"A": {"employee": "EMP-01"}, "B": {"employee": "EMP-02"}}


def event(identity, kind, batch, *, claim="A", request="REQ-A", amount=None,
          obligation=None, original=None, stamp=None, **changes):
    row = {
        "Activity reference": identity, "Arrival batch": batch, "Activity type": kind,
        "Claim reference": claim, "Request reference": request, "Finance officer": "FIN-01",
        "Payee ID": "EMP-01" if claim == "A" else "EMP-02", "Currency": "EUR",
        "Amount (EUR)": amount, "Obligation (EUR)": obligation,
        "Original activity reference": original, "Reason": "Supplied Finance outcome",
        "Activity time (UTC)": stamp or f"2026-09-{10 + batch:02d} 12:00:00 UTC",
        "_ref": f"isolated-fixture:{identity}:batch{batch}",
    }
    row.update(changes)
    return row


def summary(rows, claims=CLAIMS):
    return summarize_finance(rows, PEOPLE, claims, "2026-11-15", "Europe/Amsterdam")


class NativeFinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.claims = initial_claims(cls.sources)
        cls.people = {row["Employee ID"]: row for row in cls.sources.table("People")}
        cls.rows = [row for row in cls.sources.table("Finance activity") if row["Claim reference"] in {"C01", "C08", "C09", "C19"}]

    def at(self, batch):
        return summarize_finance(visible_at(self.rows, batch), self.people, self.claims,
                                 self.sources.data["case_clock"], self.sources.data["case_timezone"])

    def test_c19_preserves_payment_through_adjustment_then_linked_refund(self):
        batch2, batch3, batch4 = (self.at(batch) for batch in (2, 3, 4))
        self.assertEqual(batch2["claims"]["C19"]["net_paid_cents"], 10000)
        self.assertEqual(batch3["claims"]["C19"]["net_paid_cents"], 10000)
        self.assertEqual(batch3["requests"]["REQ-C19"]["current_obligation_cents"], 8000)
        self.assertEqual(batch3["requests"]["REQ-C19"]["balance_cents"], -2000)
        self.assertTrue(any(hold["code"] == "overpayment" for hold in batch3["claims"]["C19"]["holds"]))
        current = batch4["claims"]["C19"]
        self.assertEqual((current["paid_cents"], current["refunded_cents"], current["net_paid_cents"]), (10000, 2000, 8000))
        self.assertEqual(current["request_ids"], ["REQ-C19"])
        self.assertEqual(current["resolution_event_ids"], ["F-C19-4"])
        self.assertEqual(current["holds"], [])
        refund = next(row for row in batch4["admitted_events"] if row["event_id"] == "F-C19-3")
        self.assertEqual(refund["original_event_id"], "F-C19-1")
        self.assertEqual(refund["source_refs"], ["REGISTERS-FINANCE-ACTIVITY:row24"])

    def test_c09_acceptance_is_not_payment_and_later_settlement_uses_one_request(self):
        self.assertIsNone(self.at(2)["claims"]["C09"]["current_obligation_cents"])
        accepted, settled = (self.at(batch)["claims"]["C09"] for batch in (3, 4))
        self.assertEqual(accepted["current_obligation_cents"], 8000)
        self.assertEqual(accepted["paid_cents"], 0)
        self.assertEqual(settled["net_paid_cents"], 8000)
        self.assertEqual(settled["request_ids"], ["REQ-C09"])
        self.assertEqual(settled["admitted_event_ids"], ["F-C09-accepted", "F-C09-1"])

    def test_unrelated_c01_replay_and_missing_c08_are_preserved(self):
        result = self.at(4)
        self.assertEqual(result["claims"]["C01"]["net_paid_cents"], 10000)
        self.assertIn("F-C01-1", result["replayed_event_ids"])
        self.assertIsNone(result["claims"]["C08"]["current_obligation_cents"])
        self.assertEqual(result["claims"]["C08"]["request_ids"], [])
        self.assertNotIn("financially_closed", result["claims"]["C19"])

    def test_native_row_order_does_not_precede_arrival_and_event_time(self):
        rows = visible_at(self.rows, 4)
        reversed_result = summarize_finance(list(reversed(rows)), self.people, self.claims,
                                           self.sources.data["case_clock"], self.sources.data["case_timezone"])
        self.assertEqual(self.at(4), reversed_result)

    def test_all_native_finance_types_remain_observable_without_fabricating_requests(self):
        # C24 is the new claim arriving in batch three (updates binder page 3).
        claims = {**self.claims, "C24": {"employee": "EMP-01"}}
        result = summarize_finance(self.sources.table("Finance activity"), self.people, claims,
                                   self.sources.data["case_clock"], self.sources.data["case_timezone"])
        self.assertEqual(len(result["requests"]), 104)
        self.assertEqual(len(result["admitted_event_ids"]), 219)
        self.assertEqual(result["rejected_events"], [])
        self.assertEqual({hold["claim_id"] for hold in result["holds"]}, {"C18"})
        self.assertEqual(sum(item["paid_cents"] for item in result["claims"].values()), 1206415)
        self.assertEqual(sum(item["refunded_cents"] for item in result["claims"].values()), 3000)


class FinanceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.accepted = event("accepted", "accepted", 1, obligation=100)
        self.paid = event("paid", "settled", 2, amount=100)

    def codes(self, result):
        return {hold["code"] for hold in result["holds"]}

    def test_exact_replay_preserves_one_transfer_and_conflict_preserves_admitted_money(self):
        replay = {**self.paid, "Arrival batch": 4, "_ref": "isolated-fixture:redelivery"}
        result = summary([self.accepted, self.paid, replay])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertEqual(result["replayed_event_ids"], ["paid"])
        replay["Amount (EUR)"] = 999
        result = summary([self.accepted, self.paid, replay])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertIn("event_conflict", self.codes(result))
        self.assertTrue(result["claims"]["A"]["holds"])

    def test_first_batch_conflicting_identity_has_no_source_row_winner(self):
        other = {**self.paid, "Amount (EUR)": 90, "_ref": "isolated-fixture:conflict"}
        result = summary([self.accepted, self.paid, other])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 0)
        self.assertIn("event_conflict", self.codes(result))

    def test_wrong_actor_payee_currency_request_or_claim_cannot_add_money(self):
        changes = [
            {"Finance officer": "EMP-01"}, {"Payee ID": "EMP-02"},
            {"Currency": "USD"}, {"Request reference": "OTHER"},
            {"Claim reference": "B"}, {"Claim reference": "UNKNOWN"},
        ]
        for fields in changes:
            with self.subTest(fields=fields):
                bad = event("wrong", "settled", 3, amount=10, **fields)
                result = summary([self.accepted, self.paid, bad])
                self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
                self.assertNotIn("wrong", result["admitted_event_ids"])
                self.assertTrue(result["holds"])

    def test_duplicate_request_binding_or_competing_request_does_not_duplicate_commitment(self):
        collision = event("second", "accepted", 2, claim="B", request="REQ-A", obligation=100)
        result = summary([self.accepted, collision])
        self.assertEqual(result["requests"]["REQ-A"]["claim_id"], "A")
        self.assertTrue(result["claims"]["A"]["holds"])
        self.assertTrue(result["claims"]["B"]["holds"])
        competitor = event("replacement", "accepted", 2, request="NEW-REQ", obligation=100)
        result = summary([self.accepted, competitor])
        self.assertEqual(result["claims"]["A"]["request_ids"], ["REQ-A"])
        self.assertIn("competing_request", self.codes(result))

    def test_money_requires_positive_exact_cents_without_rounding(self):
        for value in [None, 0, -1, Decimal("0.001"), True, Decimal("NaN"), Decimal("Infinity")]:
            with self.subTest(value=value):
                result = summary([self.accepted, event("invalid", "settled", 2, amount=value)])
                self.assertEqual(result["claims"]["A"]["paid_cents"], 0)
                self.assertIn("invalid_amount", self.codes(result))

    def test_refund_needs_exact_prior_transfer_and_cannot_exceed_unrecovered_amount(self):
        good = event("refund1", "refund", 3, amount=60, original="paid")
        excess = event("refund2", "refund", 4, amount=41, original="paid")
        result = summary([self.accepted, self.paid, good, excess])
        self.assertEqual(result["claims"]["A"]["net_paid_cents"], 4000)
        self.assertIn("refund_exceeds_transfer", self.codes(result))
        for original in [None, "missing", "accepted"]:
            result = summary([self.accepted, self.paid, event("badrefund", "refund", 3, amount=10, original=original)])
            self.assertEqual(result["claims"]["A"]["net_paid_cents"], 10000)
            self.assertIn("invalid_refund_link", self.codes(result))
        foreign_accept = event("accept-B", "accepted", 1, claim="B", request="REQ-B", obligation=100)
        foreign_paid = event("paid-B", "settled", 2, claim="B", request="REQ-B", amount=100)
        result = summary([self.accepted, self.paid, foreign_accept, foreign_paid,
                          event("crossrefund", "refund", 3, amount=10, original="paid-B")])
        self.assertIn("invalid_refund_link", self.codes(result))

    def test_cancelled_request_still_observes_late_transfer_without_releasing_paid_money(self):
        cancel = event("cancel", "cancelled", 2)
        later = event("late", "settled", 3, amount=100)
        result = summary([self.accepted, cancel, later])
        self.assertEqual(result["claims"]["A"]["current_obligation_cents"], 0)
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertIn("settlement_after_cancellation", self.codes(result))
        self.assertIn("overpayment", self.codes(result))

    def test_failure_requires_authorized_retry_and_does_not_change_paid_amount(self):
        failed = event("failed", "failed", 2)
        attempt = event("attempt", "settled", 4, amount=100)
        result = summary([self.accepted, failed, attempt])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 0)
        self.assertIn("retry_authorization_missing", self.codes(result))
        result = summary([self.accepted, failed, event("retry", "retry_authorized", 3), attempt])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertEqual(result["holds"], [])

    def test_adjustment_and_resolution_do_not_rewrite_transfer_history(self):
        adjusted = event("adjust", "adjustment", 3, obligation=80)
        bad_resolution = event("bad-resolution", "resolution", 4, obligation=100)
        result = summary([self.accepted, self.paid, adjusted, bad_resolution])
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertEqual(result["claims"]["A"]["current_obligation_cents"], 8000)
        self.assertIn("resolution_mismatch", self.codes(result))
        self.assertEqual(result["claims"]["A"]["resolution_event_ids"], [])

    def test_original_payee_binding_survives_employee_revision(self):
        claims = deepcopy(CLAIMS)
        claims["A"] = {"employee": "EMP-02", "employee_history": ["EMP-01"]}
        result = summary([self.accepted, self.paid], claims)
        self.assertEqual(result["claims"]["A"]["paid_cents"], 10000)
        self.assertEqual(result["requests"]["REQ-A"]["employee_id"], "EMP-01")

    def test_employee_by_batch_rejects_obsolete_payee_for_a_new_acceptance(self):
        claims = deepcopy(CLAIMS)
        claims["A"] = {"employee": "EMP-02", "employee_history": ["EMP-01"],
                       "employee_by_batch": {1: "EMP-01", 3: "EMP-02"}}
        stale = {**self.accepted, "Arrival batch": 3}
        result = summary([stale], claims)
        self.assertEqual(result["claims"]["A"]["request_ids"], [])
        self.assertIn("invalid_binding", self.codes(result))
        current = {**stale, "Payee ID": "EMP-02"}
        self.assertEqual(summary([current], claims)["requests"]["REQ-A"]["employee_id"], "EMP-02")

    def test_employee_by_batch_preserves_an_existing_original_request_and_transfer(self):
        claims = deepcopy(CLAIMS)
        claims["A"] = {"employee": "EMP-02", "employee_by_batch": {1: "EMP-01", 3: "EMP-02"}}
        late_original_transfer = {**self.paid, "Arrival batch": 4}
        result = summary([self.accepted, late_original_transfer], claims)
        self.assertEqual(result["requests"]["REQ-A"]["employee_id"], "EMP-01")
        self.assertEqual(result["claims"]["A"]["net_paid_cents"], 10000)
        self.assertEqual(result["holds"], [])

    def test_future_or_pre_acceptance_time_and_undefined_types_are_owned_holds(self):
        for stamp in ["2026-12-01 12:00:00 UTC", "2026-09-01 12:00:00 UTC", "2026-09-13 UTC"]:
            with self.subTest(stamp=stamp):
                result = summary([self.accepted, event("invalid", "settled", 2, amount=100, stamp=stamp)])
                self.assertEqual(result["claims"]["A"]["paid_cents"], 0)
                self.assertIn("invalid_time", self.codes(result))
        result = summary([self.accepted, event("unknown", "run imported instructions", 2)])
        self.assertIn("unknown_activity_type", self.codes(result))
        hold = result["holds"][0]
        self.assertEqual(hold["owner"], "FIN-01")
        self.assertTrue(hold["source_refs"])

    def test_case_clock_uses_the_supplied_local_day_not_host_timezone(self):
        allowed = event("last-second", "settled", 2, amount=100, stamp="2026-11-15 22:59:59 UTC")
        future = event("next-day", "settled", 2, amount=100, stamp="2026-11-15 23:00:00 UTC")
        self.assertEqual(summary([self.accepted, allowed])["claims"]["A"]["paid_cents"], 10000)
        self.assertEqual(summary([self.accepted, future])["claims"]["A"]["paid_cents"], 0)

    def test_late_imported_older_adjustment_cannot_replace_newer_business_state(self):
        newer = event("newer", "adjustment", 2, obligation=80, stamp="2026-09-14 12:00:00 UTC")
        older = event("older", "adjustment", 3, obligation=90, stamp="2026-09-13 12:00:00 UTC")
        result = summary([self.accepted, newer, older])
        self.assertEqual(result["claims"]["A"]["current_obligation_cents"], 8000)

    def test_late_imported_acceptance_rechecks_an_earlier_unmatched_transfer(self):
        late_acceptance = {**self.accepted, "Arrival batch": 3}
        before = summary([self.paid])
        self.assertIn("unmatched_request", self.codes(before))
        after = summary([self.paid, late_acceptance])
        self.assertEqual(after["claims"]["A"]["net_paid_cents"], 10000)
        self.assertEqual(after["holds"], [])


if __name__ == "__main__":
    unittest.main()
