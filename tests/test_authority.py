from copy import deepcopy
from pathlib import Path
import re
import unittest

from travel_expense_claim.authority import recheck_authority
from travel_expense_claim.independence import visible_at
from travel_expense_claim.verify_independence import Sources, field, initial_claims


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"


class AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.claims = {(item["id"], 1): item for item in initial_claims(cls.sources).values()}
        for page in cls.sources.read("UPDATES-PAGES"):
            text = page["text"]
            item = dict(id=field(text, "Claim reference"), revision=int(field(text, "Revision")),
                        employee=field(text, "Employee"), trip=field(text, "Trip reference"),
                        trip_revision=int(field(text, "Trip revision")), source_ref=f"UPDATES:page{page['page']}",
                        lines=[{"cost_id": cost} for cost in re.findall(r"^\s*\d+\s+(COST-\S+)\s+R-COST-", text, re.M)])
            cls.claims[item["id"], item["revision"]] = item
        cls.trips = cls.sources.table("Trips")
        cls.person = cls.sources.table("People")[0]
        cls.reviews = cls.sources.table("Review ledger")
        cls.packets = cls.sources.table("Review packets")
        cls.cancellation = dict(cancellation_id="TC019", target_type="trip", trip="T19", trip_revision=1,
                                permit=None, permit_revision=None, requested_time="2026-09-13 08:00:00 UTC",
                                confirmed_time="2026-09-13 09:00:00 UTC", status="confirmed",
                                source_refs=["REGISTERS-TRAVEL-CANCELLATIONS:row12", "REGISTERS-TRAVEL-CANCELLATIONS:row13"])

    def inputs(self, claim_id="C09", revision=2, batch=3, amount=8000):
        claim = deepcopy(self.claims[claim_id, revision])
        trip = deepcopy(next(row for row in self.trips if row["Trip reference"] == claim["trip"] and row["Trip revision"] == claim["trip_revision"]))
        return dict(claim=claim, trip=trip, person=deepcopy(self.person), entitlement_cents=amount,
                    reviews=deepcopy(visible_at(self.reviews, batch)), packets=deepcopy(self.packets),
                    cancellations=[deepcopy(self.cancellation)] if claim_id == "C19" and batch >= 3 else [],
                    sources=self.sources)

    def test_native_unchanged_amount_corrected_identity_needs_current_reply_set(self):
        old = recheck_authority(**self.inputs(revision=1, batch=1))
        self.assertFalse(old["current"])
        self.assertEqual(old["missing_roles"], ["budget_owner", "supervisor"])
        result = recheck_authority(**self.inputs())
        self.assertTrue(result["current"])
        self.assertEqual(result["valid_decision_ids"], [f"D-C09-2-claim-{role}-3" for role in ["administration", "budget_owner", "supervisor"]])
        self.assertEqual(len(result["rejected_decisions"]), 2)
        self.assertTrue(all("stale claim revision" in item["reason"] for item in result["rejected_decisions"]))

    def test_native_c19_old_amount_only_reply_is_not_cancellation_authority(self):
        initial = recheck_authority(**self.inputs("C19", 1, 1, 10000))
        self.assertTrue(initial["current"])
        result = recheck_authority(**self.inputs("C19", 2, 3))
        self.assertFalse(result["current"])
        self.assertEqual(len(result["valid_decision_ids"]), 0)
        self.assertTrue(any("cancellation context" in item["reason"] for item in result["rejected_decisions"]))
        current = recheck_authority(**self.inputs("C19", 3, 4))
        self.assertTrue(current["current"])
        self.assertEqual(len(current["valid_decision_ids"]), 3)
        self.assertIn("REGISTERS-TRAVEL-CANCELLATIONS:row13", current["source_refs"])

    def test_wrong_packet_identity_current_context_and_source_version_are_rejected(self):
        changes = [("Employee ID", "EMP-02"), ("Trip reference", "T09"), ("Trip revision", 2),
                   ("Permit reference", "P-UNRELATED"), ("Expense references", "COST-09"),
                   ("Business purpose", "Other purpose"), ("Client", "Other client"),
                   ("Schedule coverage", "Other coverage"), ("Alternatives considered", "Other alternatives"),
                   ("Policy revision", "POL-OLD"), ("Budget record references", "B-ALLOC")]
        for name, value in changes:
            with self.subTest(field=name):
                args = self.inputs()
                next(row for row in args["packets"] if row["Decision reference"] == "D-C09-2-claim-administration-3")[name] = value
                result = recheck_authority(**args)
                self.assertFalse(result["current"])
                self.assertIn("administration", result["missing_roles"])
                self.assertTrue(any(item["decision_id"] == "D-C09-2-claim-administration-3" and item["source_refs"] for item in result["rejected_decisions"]))

    def test_wrong_actor_role_subject_and_mixed_source_versions_cannot_authorize(self):
        for name, value in [("Reviewer", "EMP-01"), ("Review roles", "director"), ("Subject type", "permit"),
                            ("Source revisions", "POL-OLD\nSRC-D-3"),
                            ("Source revisions", "POL-2026.2\nPOL-OLD\nSRC-D-3")]:
            with self.subTest(field=name, value=value):
                args = self.inputs()
                next(row for row in args["reviews"] if row["Decision reference"] == "D-C09-2-claim-administration-3")[name] = value
                self.assertFalse(recheck_authority(**args)["current"])

    def test_unknown_and_strict_director_threshold(self):
        self.assertTrue(recheck_authority(**self.inputs(amount=100000))["current"])
        result = recheck_authority(**self.inputs(amount=100001))
        self.assertFalse(result["current"])
        self.assertEqual(result["missing_roles"], ["director"])
        result = recheck_authority(**self.inputs(amount=None))
        self.assertFalse(result["current"])
        self.assertIn("director_requirement_unknown", result["missing_roles"])

    def test_explicit_combined_owner_supervisor_only_for_the_same_stable_actor(self):
        args = self.inputs()
        args["person"]["Supervisor"] = args["person"]["Budget owner"]
        args["reviews"] = [row for row in args["reviews"] if row["Decision reference"] != "D-C09-2-claim-supervisor-3"]
        row = next(row for row in args["reviews"] if row["Decision reference"] == "D-C09-2-claim-budget_owner-3")
        row["Review roles"] = "budget_owner\nsupervisor"
        self.assertTrue(recheck_authority(**args)["current"])
        row["Review roles"] = "budget_owner\nadministration"
        self.assertFalse(recheck_authority(**args)["current"])

    def test_later_valid_return_reject_or_conflict_holds_only_affected_review(self):
        for outcome in ["return", "reject", "approve"]:
            with self.subTest(outcome=outcome):
                args = self.inputs()
                original = next(row for row in args["reviews"] if row["Decision reference"] == "D-C09-2-claim-budget_owner-3")
                later = {**original, "Decision reference": "D-C09-later", "Outcome": outcome,
                         "Reason": "Supplied human review", "Repair requested": "Obtain funding decision",
                         "Decision time (UTC)": "2026-09-04 12:00:00 UTC", "_ref": "isolated:later-review"}
                args["reviews"].append(later)
                original_packet = next(row for row in args["packets"] if row["Decision reference"] == original["Decision reference"])
                args["packets"].append({**original_packet, "Decision reference": "D-C09-later", "_ref": "isolated:later-packet"})
                result = recheck_authority(**args)
                self.assertEqual(result["current"], outcome == "approve")
                if outcome != "approve":
                    self.assertEqual(result["missing_roles"], ["budget_owner"])
                if outcome == "approve":
                    args["reviews"].append({**later, "Decision reference": "D-C09-conflict", "Outcome": "return"})
                    args["packets"].append({**original_packet, "Decision reference": "D-C09-conflict"})
                    self.assertFalse(recheck_authority(**args)["current"])

    def test_cancellation_ids_alone_do_not_make_preconfirmation_review_current(self):
        args = self.inputs("C19", 3, 4)
        for row in args["reviews"]:
            if row["Subject reference"] == "C19" and row["Revision"] == 3:
                row["Decision time (UTC)"] = "2026-09-13 08:30:00 UTC"
        result = recheck_authority(**args)
        self.assertFalse(result["current"])
        self.assertTrue(any("predates" in item["reason"] for item in result["rejected_decisions"]))

    def test_extra_old_trip_cancellation_does_not_follow_reassigned_claim(self):
        args = self.inputs()
        args["cancellations"] = [{**self.cancellation, "trip": "T09", "cancellation_id": "TC-OLD"}]
        self.assertTrue(recheck_authority(**args)["current"])

    def test_future_reply_ambiguous_packet_and_conflicting_decision_do_not_authorize(self):
        args = self.inputs()
        row = next(row for row in args["reviews"] if row["Decision reference"] == "D-C09-2-claim-administration-3")
        row["Decision time (UTC)"] = "2026-11-16 00:00:00 UTC"
        self.assertFalse(recheck_authority(**args)["current"])
        args = self.inputs()
        packet = next(row for row in args["packets"] if row["Decision reference"] == "D-C09-2-claim-administration-3")
        args["packets"].append({**packet, "Client": "Different client"})
        self.assertFalse(recheck_authority(**args)["current"])
        args = self.inputs()
        row = next(row for row in args["reviews"] if row["Decision reference"] == "D-C09-2-claim-administration-3")
        args["reviews"].append({**row, "Outcome": "reject"})
        self.assertFalse(recheck_authority(**args)["current"])

    def test_dictionary_packets_supported_and_inputs_unchanged(self):
        args = self.inputs()
        args["packets"] = {row["Decision reference"]: row for row in args["packets"]}
        before = deepcopy({key: value for key, value in args.items() if key != "sources"})
        self.assertTrue(recheck_authority(**args)["current"])
        self.assertEqual({key: value for key, value in args.items() if key != "sources"}, before)


if __name__ == "__main__":
    unittest.main()
