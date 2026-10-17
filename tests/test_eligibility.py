from copy import deepcopy
from pathlib import Path
import unittest

from travel_expense_claim.cancellations import reduce_cancellations
from travel_expense_claim.eligibility import assess_permission
from travel_expense_claim.independence import visible_at
from travel_expense_claim.verify_independence import Sources, initial_claims


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"


class PermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.claims = initial_claims(cls.sources)
        cls.trips = cls.sources.table("Trips")
        cls.people = {row["Employee ID"]: row for row in cls.sources.table("People")}
        cls.reviews = cls.sources.table("Review ledger")
        cls.packets = cls.sources.table("Review packets")
        cls.cancellations = cls.sources.table("Travel cancellations")

    def inputs(self, claim_id="C02", batch=1, trip_id=None):
        if trip_id is None:
            claim = deepcopy(self.claims[claim_id])
            trip_id = claim["trip"]
        else:
            claim = dict(subject_type="permit", id="unused", employee="EMP-01", source_ref="REGISTERS-TRIPS:row128")
        trip = deepcopy(next(row for row in self.trips if row["Trip reference"] == trip_id))
        return dict(claim=claim, trip=trip, person=deepcopy(self.people[trip["Employee ID"]]),
                    reviews=deepcopy(visible_at(self.reviews, batch)), packets=deepcopy(self.packets),
                    cancellations=reduce_cancellations(visible_at(self.cancellations, batch), self.people, self.trips, self.sources),
                    sources=self.sources)

    def codes(self, result):
        return {item["code"] for item in result["findings"]}

    def test_native_timely_high_estimate_permit_uses_its_own_four_roles(self):
        result = assess_permission(**self.inputs())
        self.assertTrue(result["historical_permission"])
        self.assertTrue(result["arrangements_authorized"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(len(result["current_permit_authority"]["valid_decision_ids"]), 4)
        self.assertTrue(all("-permit-" in key for key in result["current_permit_authority"]["valid_decision_ids"]))

    def test_native_late_permit_and_missing_permit_route_remain_distinct(self):
        late = assess_permission(**self.inputs("C10"))
        self.assertFalse(late["historical_permission"])
        self.assertFalse(late["arrangements_authorized"])
        self.assertTrue(late["current_permit_authority"]["current"])
        self.assertEqual(self.codes(late), {"late_permit"})
        missing = assess_permission(**self.inputs("C25"))
        self.assertEqual(self.codes(missing), {"permit_unapproved"})

    def test_native_domestic_c11_needs_no_permit_and_cancellation_still_pauses(self):
        result = assess_permission(**self.inputs("C11"))
        self.assertEqual(result["findings"], [])
        self.assertTrue(result["historical_permission"])
        self.assertTrue(result["arrangements_authorized"])
        self.assertIsNone(result["current_permit_authority"])
        cancelled = assess_permission(**self.inputs("C19", batch=4))
        self.assertEqual(cancelled["findings"], [])
        self.assertFalse(cancelled["arrangements_authorized"])

    def test_later_native_permit_cancellation_does_not_rewrite_timely_paid_permission(self):
        for batch in (1, 2, 3, 4):
            with self.subTest(batch=batch):
                result = assess_permission(**self.inputs("C121", batch=batch))
                self.assertTrue(result["historical_permission"])
                self.assertFalse(result["arrangements_authorized"])
                self.assertEqual(result["findings"], [])
                self.assertNotIn("permit_unapproved", self.codes(result))

    def test_native_no_claim_permit_retains_historical_route_and_paused_arrangements(self):
        for batch in (1, 2, 4):
            result = assess_permission(**self.inputs(trip_id="T122", batch=batch))
            self.assertTrue(result["historical_permission"])
            self.assertFalse(result["arrangements_authorized"])
            self.assertEqual(result["findings"], [])
            self.assertIn("REGISTERS-TRAVEL-CANCELLATIONS:row6", result["source_refs"])

    def test_claim_approvals_never_fill_a_missing_permit_position(self):
        args = self.inputs()
        args["reviews"] = [row for row in args["reviews"] if row["Subject type"] != "permit"]
        result = assess_permission(**args)
        self.assertFalse(result["historical_permission"])
        self.assertIn("permit_unapproved", self.codes(result))

    def test_permit_estimate_threshold_is_independent_of_claim_amount(self):
        args = self.inputs()
        args["reviews"] = [row for row in args["reviews"] if row["Decision reference"] != "D-C02-1-permit-director-1"]
        self.assertIn("permit_unapproved", self.codes(assess_permission(**args)))
        args["trip"]["Estimate (EUR)"] = 1000
        for packet in args["packets"]:
            if packet["Permit reference"] == "P02":
                packet["Reviewed estimate (EUR)"] = 1000
        result = assess_permission(**args)
        self.assertTrue(result["historical_permission"])
        self.assertEqual(len(result["current_permit_authority"]["valid_decision_ids"]), 3)

    def test_same_day_ordering_uses_amsterdam_not_the_utc_calendar_date(self):
        for utc, expected in [("2026-08-31 21:30:00 UTC", True), ("2026-08-31 22:30:00 UTC", False),
                              ("2026-09-01 12:00:00 UTC", False)]:
            with self.subTest(utc=utc):
                args = self.inputs()
                for row in args["reviews"]:
                    if row["Subject reference"] == "P02":
                        row["Decision time (UTC)"] = utc
                result = assess_permission(**args)
                self.assertEqual(result["historical_permission"], expected)
                self.assertEqual(self.codes(result), set() if expected else {"permit_ordering_uncertain"})

    def test_late_permit_finding_survives_a_later_cancellation(self):
        args = self.inputs("C10")
        args["cancellations"] = [dict(cancellation_id="TC-LATER", target_type="permit", trip="T10", trip_revision=1,
                                     permit="P10", permit_revision=1, requested_time="2026-09-10 09:00:00 UTC",
                                     confirmed_time="2026-09-12 09:00:00 UTC", status="confirmed", source_refs=["isolated:cancellation"])]
        result = assess_permission(**args)
        self.assertEqual(self.codes(result), {"late_permit"})
        self.assertFalse(result["arrangements_authorized"])

    def test_missing_permission_is_not_relabelled_as_ordering_uncertainty(self):
        args = self.inputs("C25")
        args["cancellations"] = [dict(cancellation_id="TC-SAME-DAY", target_type="permit", trip="T25", trip_revision=1,
                                     permit="P25", permit_revision=1, requested_time="2026-09-01 09:00:00 UTC",
                                     confirmed_time=None, status="requested", source_refs=["isolated:cancellation"])]
        self.assertEqual(self.codes(assess_permission(**args)), {"permit_unapproved"})

    def test_postcancellation_replies_do_not_resurrect_a_retired_permit(self):
        args = self.inputs("C121", batch=3)
        for row in args["reviews"]:
            if row["Subject reference"] == "P121":
                row["Decision time (UTC)"] = "2026-09-14 12:00:00 UTC"
        for packet in args["packets"]:
            if packet["Permit reference"] == "P121" and "-permit-" in packet["Decision reference"]:
                packet["Travel cancellation references"] = "TC121"
        result = assess_permission(**args)
        self.assertFalse(result["arrangements_authorized"])
        self.assertFalse(result["historical_permission"])
        self.assertIn("permit_unapproved", self.codes(result))

    def test_later_visible_approval_does_not_leak_into_an_earlier_call(self):
        args = self.inputs()
        permit_rows = [row for row in args["reviews"] if row["Subject reference"] == "P02"]
        early = {**args, "reviews": [row for row in args["reviews"] if row not in permit_rows]}
        self.assertIn("permit_unapproved", self.codes(assess_permission(**early)))
        self.assertTrue(assess_permission(**args)["historical_permission"])

    def test_current_estimate_identity_and_material_packet_fields_are_rechecked(self):
        for field, value in [("Reviewed estimate (EUR)", 100), ("Trip revision", 2), ("Employee ID", "EMP-02"),
                             ("Business purpose", "Different purpose"), ("Budget record references", "B-ALLOC")]:
            with self.subTest(field=field):
                args = self.inputs()
                for packet in args["packets"]:
                    if packet["Permit reference"] == "P02":
                        packet[field] = value
                self.assertIn("permit_unapproved", self.codes(assess_permission(**args)))

    def test_missing_estimate_and_unknown_timing_never_imply_authorization(self):
        args = self.inputs()
        args["trip"]["Estimate (EUR)"] = None
        self.assertIn("permit_estimate_unknown", self.codes(assess_permission(**args)))
        args = self.inputs()
        args["trip"]["First commitment date"] = "invalid"
        result = assess_permission(**args)
        self.assertFalse(result["arrangements_authorized"])
        self.assertIn("permission_timing_unknown", self.codes(result))

    def test_independent_claim_expense_change_does_not_change_trip_permission(self):
        args = self.inputs()
        args["claim"]["lines"] = [{"cost_id": "A-NEW-CLAIM-COST"}]
        self.assertTrue(assess_permission(**args)["historical_permission"])


if __name__ == "__main__":
    unittest.main()
