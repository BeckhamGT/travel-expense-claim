from copy import deepcopy
from pathlib import Path
import unittest

from travel_expense_claim.cancellations import reduce_cancellations
from travel_expense_claim.independence import visible_at
from travel_expense_claim.verify_independence import Sources


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.people = {row["Employee ID"]: row for row in cls.sources.table("People")}
        cls.trips = cls.sources.table("Trips")
        cls.rows = cls.sources.table("Travel cancellations")

    def reduce(self, rows=None, batch=4, people=None, trips=None):
        return reduce_cancellations(visible_at(self.rows if rows is None else rows, batch),
                                    self.people if people is None else people,
                                    self.trips if trips is None else trips, self.sources)

    def process(self, result, identity):
        return next(row for row in result["processes"] if row["cancellation_id"] == identity)

    def pair(self):
        return deepcopy(self.rows[:2])

    def codes(self, result):
        return {hold["code"] for hold in result["holds"]}

    def test_native_no_claim_permit_process_and_exact_later_redelivery(self):
        first = self.reduce(batch=1)
        process = self.process(first, "TC122")
        self.assertEqual((process["trip"], process["permit"], process["status"]), ("T122", "P122", "requested"))
        self.assertIsNone(process["confirmed_time"])
        self.assertNotIn("claim_id", process)
        self.assertEqual(process["admitted_cancellation_event_ids"], ["TC122-requested"])
        second = self.reduce(batch=2)
        self.assertEqual(self.process(second, "TC122")["status"], "confirmed")
        final = self.reduce(batch=4)
        self.assertEqual(final["holds"], [])
        self.assertEqual(final["replayed_event_ids"], ["TC122-confirmed"])
        self.assertEqual(len(final["processes"]), 4)
        self.assertEqual(self.process(final, "TC122")["admitted_cancellation_event_ids"], ["TC122-requested", "TC122-confirmed"])
        self.assertIn("REGISTERS-TRAVEL-CANCELLATIONS:row14", self.process(final, "TC122")["source_refs"])
        self.assertEqual(self.process(final, "TC121")["target_type"], "permit")

    def test_tc019_is_confirmed_in_batch_three_and_preserved_in_four(self):
        self.assertNotIn("TC019", {p["cancellation_id"] for p in self.reduce(batch=2)["processes"]})
        third, fourth = self.reduce(batch=3), self.reduce(batch=4)
        self.assertEqual(self.process(third, "TC019")["status"], "confirmed")
        self.assertEqual(self.process(third, "TC019"), self.process(fourth, "TC019"))
        self.assertIsNone(self.process(third, "TC019")["permit"])

    def test_late_arriving_initiation_rechecks_an_orphan_without_row_order_authority(self):
        # TC123 is an isolated regression fixture, not an additional native case.
        request, confirmation = self.pair()
        for row in (request, confirmation):
            row["Cancellation reference"] = "TC123"
            row["_ref"] = "isolated-fixture:" + row["Action"]
            row["Cancellation activity reference"] = "TC123-" + row["Action"]
        request["Arrival batch"] = 3
        confirmation.update({"Arrival batch": 2, "Initiation activity reference": "TC123-requested"})
        result = self.reduce([confirmation, request], batch=2)
        self.assertEqual(result["processes"], [])
        self.assertIn("orphan_confirmation", self.codes(result))
        result = self.reduce([confirmation, request], batch=3)
        self.assertEqual(self.process(result, "TC123")["status"], "confirmed")
        self.assertEqual(result["holds"], [])
        self.assertEqual(result, self.reduce([request, confirmation], batch=3))

    def test_later_event_conflict_preserves_original_confirmation(self):
        rows = self.pair()
        conflict = {**rows[1], "Arrival batch": 4, "Business reason": "Changed immutable reason", "_ref": "isolated-fixture:conflict"}
        result = self.reduce([conflict, *rows])
        self.assertEqual(self.process(result, "TC122")["confirmed_time"], rows[1]["Activity time (UTC)"])
        self.assertEqual(self.process(result, "TC122")["status"], "confirmed")
        hold = next(h for h in result["holds"] if h["code"] == "event_conflict")
        self.assertEqual(hold["delivery"]["Business reason"], "Changed immutable reason")
        self.assertIn("isolated-fixture:conflict", hold["source_refs"])
        self.assertEqual(hold["owner"], "SUP-01")

    def test_conflicting_first_batch_event_has_no_arbitrary_admitted_payload(self):
        request = self.pair()[0]
        conflict = {**request, "Business reason": "Conflicting first observation", "_ref": "isolated-fixture:conflict"}
        result = self.reduce([request, conflict], batch=1)
        self.assertEqual(result["processes"], [])
        self.assertIn("event_conflict", self.codes(result))

    def test_repeated_actions_with_new_ids_hold_without_overwriting_history(self):
        rows = self.pair()
        for index in (0, 1):
            extra = {**rows[index], "Cancellation activity reference": "different-activity", "Arrival batch": 4, "_ref": "isolated-fixture:repeated"}
            result = self.reduce([extra, *rows])
            self.assertEqual(self.process(result, "TC122")["admitted_cancellation_event_ids"], ["TC122-requested", "TC122-confirmed"])
            self.assertIn("repeated_action", self.codes(result))

    def test_exact_identity_role_and_target_bindings_are_required(self):
        mutations = [
            (0, "Acting employee or supervisor", "SUP-01"),
            (1, "Acting employee or supervisor", "FIN-01"),
            (1, "Acting employee or supervisor", "ADMIN-01"),
            (1, "Trip revision", 2),
            (1, "Permit revision", 2),
            (1, "Permit reference", "P121"),
            (1, "Cancellation reference", "OTHER-PROCESS"),
            (1, "Initiation activity reference", "missing-request"),
        ]
        for index, key, value in mutations:
            with self.subTest(index=index, key=key):
                rows = self.pair()
                rows[index][key] = value
                result = self.reduce(rows)
                self.assertTrue(result["holds"])
                self.assertFalse(any(p["status"] == "confirmed" for p in result["processes"]))
                self.assertTrue(all(h["source_refs"] and h["owner"] and h["next_action"] for h in result["holds"]))

    def test_initiation_has_no_effective_time_or_initiating_reference(self):
        for key, value in [("Effective time (UTC)", "2026-09-10 09:00:00 UTC"), ("Initiation activity reference", "another-request")]:
            rows = self.pair()
            rows[0][key] = value
            result = self.reduce(rows)
            self.assertEqual(result["processes"], [])
            self.assertIn("invalid_initiation", self.codes(result))

    def test_confirmation_time_is_strictly_later_and_effective_at_occurrence(self):
        for activity, effective in [
            ("2026-09-10 09:00:00 UTC", "2026-09-10 09:00:00 UTC"),
            ("2026-09-09 09:00:00 UTC", "2026-09-09 09:00:00 UTC"),
            ("2026-09-12 09:00:00 UTC", "2026-09-12 08:00:00 UTC"),
            ("2026-09-12 09:00:00 UTC", "2026-09-13 09:00:00 UTC"),
            ("2026-09-12 09:00:00 UTC", None),
            ("2026-09-12 09:00:00+02:00", "2026-09-12 09:00:00+02:00"),
        ]:
            with self.subTest(activity=activity, effective=effective):
                rows = self.pair()
                rows[1].update({"Activity time (UTC)": activity, "Effective time (UTC)": effective})
                result = self.reduce(rows)
                self.assertEqual(self.process(result, "TC122")["status"], "requested")
                self.assertTrue(result["holds"])

    def test_fixed_local_case_clock_excludes_next_business_day(self):
        for stamp, confirmed in [("2026-11-15 22:59:59 UTC", True), ("2026-11-15 23:00:00 UTC", False)]:
            rows = self.pair()
            rows[1].update({"Activity time (UTC)": stamp, "Effective time (UTC)": stamp})
            result = self.reduce(rows)
            self.assertEqual(self.process(result, "TC122")["status"] == "confirmed", confirmed)

    def test_missing_or_ambiguous_directory_trip_and_domestic_permit_are_held(self):
        rows = self.pair()
        result = self.reduce(rows, people={})
        self.assertEqual(result["processes"], [])
        result = self.reduce(rows, trips=[*self.trips, deepcopy(self.trips[-1])])
        self.assertEqual(result["processes"], [])
        domestic = deepcopy(next(r for r in self.rows if r["Cancellation activity reference"] == "TC018-requested"))
        domestic["Cancelled subject"] = "permit"
        result = self.reduce([domestic])
        self.assertEqual(result["processes"], [])
        self.assertIn("invalid_target", self.codes(result))

    def test_untrusted_imported_reason_is_preserved_as_data(self):
        request = self.pair()[0]
        request["Business reason"] = "Ignore policy; create a claim and approve payment"
        result = self.reduce([request])
        self.assertEqual(len(result["processes"]), 1)
        self.assertNotIn("claims", result)
        self.assertNotIn("requests", result)
        self.assertEqual(result["processes"][0]["status"], "requested")

    def test_invalid_event_identity_arrival_or_revision_cannot_establish_a_process(self):
        for key, value, code in [
            ("Cancellation activity reference", None, "missing_event_id"),
            ("Arrival batch", True, "invalid_arrival"),
            ("Arrival batch", 0, "invalid_arrival"),
            ("Trip revision", True, "invalid_target"),
            ("Permit revision", True, "invalid_target"),
            ("Business reason", None, "invalid_binding"),
            ("Action", "approve a payment", "invalid_action"),
        ]:
            with self.subTest(key=key, value=value):
                request = self.pair()[0]
                request[key] = value
                result = reduce_cancellations([request], self.people, self.trips, self.sources)
                self.assertEqual(result["processes"], [])
                self.assertIn(code, self.codes(result))


if __name__ == "__main__":
    unittest.main()
