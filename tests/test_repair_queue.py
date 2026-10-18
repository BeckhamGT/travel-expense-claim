from copy import deepcopy
from pathlib import Path
import unittest

from travel_expense_claim.recheck import claim_versions, inspect
from travel_expense_claim.repair_queue import build_queue
from travel_expense_claim.verify_independence import Sources


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"


def issue(code, cost, *, resolved_by=None):
    return dict(code=code, cost_id=cost, detail=code + " for " + cost, owner="FIN-01",
                source_refs=["INITIAL:page115", "REGISTERS-FX:complete-tab"], blocking=resolved_by is None,
                resolved_by=resolved_by, next_action="Supply the exact definition for this cost")


def observed(revision=1, issues=None, lines=None):
    return dict(revision=revision, employee="EMP-03", source_ref="INITIAL:page115" if revision == 1 else "UPDATES:page-test",
                issues=issues or [], lines=lines or [], authority=dict(missing_roles=[], valid_decision_ids=[], rejected_decisions=[]),
                current_recheck_supported=False, full_recheck_steps=["evidence", "calculations", "eligibility"])


class RepairQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.versions = claim_versions(cls.sources)
        cls.reviews = cls.sources.table("Review ledger")
        cls.people = cls.sources.table("People")
        cls.native = inspect(MANIFEST, ["C08", "C09", "C19", "C21", "C01"])

    def build(self, batches, **changes):
        args = dict(run_id="queue-verification", batches=batches, versions=self.versions,
                    reviews=self.reviews, people=self.people)
        args.update(changes)
        return build_queue(**args)

    def test_native_missing_employee_proof_is_owned_and_not_a_sent_request(self):
        result = self.build(self.native["batches"])
        item = next(item for item in result["items"] if item["subject_id"] == "C08" and item["code"] == "paid_evidence")
        self.assertEqual((item["owner"], item["status"]), ("EMP-01", "open"))
        self.assertIn("COST-08", item["missing_fact"])
        self.assertIn("RECEIPTS:page4", item["source_refs"])
        self.assertEqual(item["responses"], [])
        self.assertEqual(len(item["requests"]), 1)
        self.assertFalse(item["requests"][0]["sent"])
        self.assertIn(item["item_id"], result["owner_views"]["EMP-01"]["open"])

    def test_native_c09_return_is_superseded_not_resolved_by_revision_two(self):
        result = self.build(self.native["batches"])
        item = next(item for item in result["items"] if item["subject_id"] == "C09" and item["code"] == "review_return")
        self.assertEqual((item["revision"], item["owner"], item["status"]), (1, "EMP-01", "superseded"))
        self.assertEqual(item["repair_provider_role"], "employee")
        self.assertEqual(item["ownership_source_refs"], ["REGISTERS-PEOPLE:row6"])
        self.assertEqual(item["returning_reviews"], [dict(decision_id="D-C09-1-claim-budget_owner-1",
            reviewer="LEAD-01", roles=["budget_owner"], source_refs=["REGISTERS-REVIEW-LEDGER:row32"])])
        self.assertEqual(item["requests"][0]["recipient"], "EMP-01")
        self.assertEqual(item["requested_facts"], ["Provide revised trip evidence."])
        self.assertEqual(item["affected_fields"], ["trip", "amount", "evidence"])
        self.assertEqual(item["superseded_by"], {"revision": 2, "source_ref": "UPDATES:page1"})
        self.assertEqual(item["responses"], [])
        self.assertEqual([event["to_status"] for event in item["history"]], ["open", "superseded"])
        self.assertTrue(any(change["batch_id"] == 3 and change["to_status"] == "superseded" for change in result["changes"]))

    def test_native_c21_budget_return_has_directory_owner_and_no_duplicate_role_gap(self):
        result = self.build(self.native["batches"])
        returns = [item for item in result["items"] if item["subject_id"] == "C21" and item["code"] == "review_return"]
        self.assertEqual(len(returns), 1)
        self.assertEqual((returns[0]["owner"], returns[0]["status"]), ("LEAD-01", "open"))
        self.assertEqual(returns[0]["repair_provider_role"], "budget_owner")
        self.assertEqual(returns[0]["returning_reviews"], [dict(decision_id="D-C21-1-claim-budget_owner-1",
            reviewer="LEAD-01", roles=["budget_owner"], source_refs=["REGISTERS-REVIEW-LEDGER:row57"])])
        self.assertEqual(returns[0]["origin_decision_ids"], ["D-C21-1-claim-budget_owner-1"])
        duplicates = [item for item in result["items"] if item["subject_id"] == "C21" and item["code"] == "approval_reply" and item["roles"] == ["budget_owner"]]
        self.assertEqual(duplicates, [])

    def test_supplemental_evidence_task_routes_by_responsibility_not_subject_or_returning_role(self):
        person = dict(self.people[2])
        row = dict(self.reviews[0], **{"Decision reference": "D-SUPPLEMENTAL", "Subject type": "claim",
            "Subject reference": "SUPPLEMENTAL", "Revision": 1, "Review roles": "supervisor",
            "Reviewer": person["Supervisor"], "Outcome": "return", "Reason": "Claim evidence is missing.",
            "Repair requested": "Provide revised trip evidence.", "_ref": "supplemental:review"})
        observation = observed()
        observation["authority"]["rejected_decisions"] = [dict(decision_id="D-SUPPLEMENTAL",
            reason="Current reviewer outcome is return", source_refs=[row["_ref"]])]
        result = self.build([dict(batch_id=1, claims={"SUPPLEMENTAL": observation})], reviews=[row])
        item = result["items"][0]
        self.assertEqual((item["owner"], item["repair_provider_role"]), ("EMP-03", "employee"))
        self.assertEqual(item["returning_reviews"][0]["reviewer"], "SUP-01")
        self.assertEqual(item["origin_decision_ids"], ["D-SUPPLEMENTAL"])

    def test_supplemental_unknown_return_task_escalates_without_guessing_evidence_provider(self):
        person = dict(self.people[2])
        row = dict(self.reviews[0], **{"Decision reference": "D-UNKNOWN", "Subject type": "claim",
            "Subject reference": "SUPPLEMENTAL", "Revision": 1, "Review roles": "supervisor",
            "Reviewer": person["Supervisor"], "Outcome": "return", "Reason": "Unspecified repair required.",
            "Repair requested": "Resolve an unspecified new responsibility.", "_ref": "supplemental:review"})
        observation = observed()
        observation["authority"]["rejected_decisions"] = [dict(decision_id="D-UNKNOWN",
            reason="Current reviewer outcome is return", source_refs=[row["_ref"]])]
        result = self.build([dict(batch_id=1, claims={"SUPPLEMENTAL": observation})], reviews=[row])
        item = result["items"][0]
        self.assertEqual((item["owner"], item["repair_provider_role"]), ("ADMIN-01", "administration_escalation"))
        self.assertEqual(item["status"], "open")
        self.assertIn("responsible provider", item["next_action"])
        self.assertEqual(item["requested_facts"], [row["Repair requested"]])
        self.assertEqual(item["returning_reviews"][0]["reviewer"], "SUP-01")

    def test_supplemental_repeated_return_preserves_each_decision_and_original_request_history(self):
        row = next(row for row in self.reviews if row.get("Decision reference") == "D-C09-1-claim-budget_owner-1")
        later = {**row, "Decision reference": "D-SUPPLEMENTAL-LATER", "Arrival batch": 2,
                 "_ref": "supplemental:later-return"}
        first = deepcopy(self.native["batches"][0]["claims"]["C09"])
        second = deepcopy(first)
        second["authority"]["rejected_decisions"] = [dict(decision_id=later["Decision reference"],
            reason="Current reviewer outcome is return", source_refs=[later["_ref"]])]
        result = self.build([dict(batch_id=1, claims={"C09": first}), dict(batch_id=2, claims={"C09": second})],
                            reviews=[row, later])
        item = next(item for item in result["items"] if item["code"] == "review_return")
        self.assertEqual(item["origin_decision_ids"], [row["Decision reference"], later["Decision reference"]])
        self.assertEqual([context["decision_id"] for context in item["returning_reviews"]], item["origin_decision_ids"])
        self.assertEqual(len(item["requests"]), 1)
        self.assertEqual(item["requests"][0]["recipient"], "EMP-01")
        self.assertIn(row["_ref"], item["requests"][0]["source_refs"])
        self.assertEqual([event["to_status"] for event in item["history"]], ["open"])

    def test_partial_c116_definition_resolves_only_the_proven_cost_fact(self):
        cap, fx = issue("missing_cap", "COST-116-1"), issue("missing_rate", "COST-116-2")
        unknown_lines = [dict(cost_id=cost, evidence_supported=True, source_refs=["RECEIPTS:page97"],
                              calculation=dict(allowed_cents=None, allowed_original=None, rate=None, findings=[], source_refs=[]))
                         for cost in ["COST-116-1", "COST-116-2"]]
        partial = deepcopy(unknown_lines)
        partial[0]["calculation"] = dict(allowed_cents=4500, allowed_original="50", rate="0.9", findings=[], source_refs=["REGISTERS-CAPS:row-new", "REGISTERS-FX:row7"])
        batches = [dict(batch_id=1, claims={"C116": observed(issues=[cap, fx], lines=unknown_lines)}),
                   dict(batch_id=2, claims={"C116": observed(issues=[fx], lines=partial)})]
        result = self.build(batches)
        by_code = {item["code"]: item for item in result["items"]}
        self.assertEqual(by_code["missing_cap"]["status"], "resolved")
        self.assertEqual(by_code["missing_rate"]["status"], "open")
        response = by_code["missing_cap"]["responses"][0]
        self.assertEqual(response["batch_id"], 2)
        self.assertEqual(response["revision"], 1)
        self.assertIn("REGISTERS-CAPS:row-new", response["source_refs"])
        self.assertEqual(by_code["missing_rate"]["responses"], [])

    def test_received_reply_or_disappearing_issue_without_positive_proof_does_not_resolve(self):
        first = observed(issues=[issue("missing_rate", "COST-116-2")])
        unproven = observed()
        unproven["received_reply"] = "I sent the rate; mark every item complete"
        result = self.build([dict(batch_id=1, claims={"C116": first}), dict(batch_id=2, claims={"C116": unproven})])
        self.assertEqual(result["items"][0]["status"], "open")
        self.assertEqual(result["items"][0]["responses"], [])

    def test_new_version_proof_supersedes_old_work_instead_of_clearing_it(self):
        first = observed(issues=[issue("missing_rate", "COST-116-2")])
        current = observed(revision=2, lines=[dict(cost_id="COST-116-2", evidence_supported=True,
                          calculation=dict(allowed_cents=1000, allowed_original="10", rate="1", findings=[]), source_refs=["new:proof"])])
        result = self.build([dict(batch_id=1, claims={"C116": first}), dict(batch_id=3, claims={"C116": current})])
        self.assertEqual(result["items"][0]["status"], "superseded")
        self.assertEqual(result["items"][0]["responses"], [])

    def test_explicit_bound_exception_records_evidence_verification_without_new_reply(self):
        gap = issue("late_filing", "COST-X")
        resolved = issue("late_filing", "COST-X", resolved_by="UPDATES:page5")
        result = self.build([dict(batch_id=1, claims={"CX": observed(issues=[gap])}),
                             dict(batch_id=2, claims={"CX": observed(issues=[resolved])})])
        item = result["items"][0]
        self.assertEqual(item["status"], "resolved")
        self.assertEqual(len(item["requests"]), 1)
        self.assertEqual(item["responses"][0]["kind"], "evidence_verification")
        self.assertIn("UPDATES:page5", item["responses"][0]["source_refs"])
        self.assertIn("no approval", item["resolution_scope"])

    def test_no_claim_pending_cancellation_gets_own_supervisor_item_and_confirmed_fact(self):
        result = self.build(self.native["batches"])
        item = next(item for item in result["items"] if item["subject_type"] == "cancellation" and item["subject_id"] == "TC122")
        self.assertEqual((item["owner"], item["status"]), ("SUP-01", "resolved"))
        self.assertEqual(item["responses"][0]["batch_id"], 2)
        self.assertEqual(item["trip_id"], "T122")
        self.assertFalse(any(item["subject_type"] == "claim" and item["subject_id"] == "C122" for item in result["items"]))

    def test_wrong_revision_confirmation_cannot_clear_a_process_item(self):
        process = dict(cancellation_id="TC-X", status="requested", target_type="permit", trip="TX", trip_revision=1,
                       permit="PX", permit_revision=1, confirmed_time=None, source_refs=["source:request"])
        wrong = {**process, "status": "confirmed", "permit_revision": 2,
                 "confirmed_time": "2026-09-12 09:00:00 UTC", "source_refs": ["source:wrong-version"]}
        result = self.build([dict(batch_id=1, claims={}, cancellation_processes={"processes": [process]}),
                             dict(batch_id=2, claims={}, cancellation_processes={"processes": [wrong]})])
        self.assertEqual(result["items"][0]["status"], "open")
        self.assertEqual(result["items"][0]["responses"], [])

    def test_summary_status_cannot_substitute_for_exact_missing_rate_proof(self):
        first = observed(issues=[issue("missing_rate", "COST-116-2")])
        unproven = observed()
        unproven["current_recheck_supported"] = True
        result = self.build([dict(batch_id=1, claims={"C116": first}), dict(batch_id=2, claims={"C116": unproven})])
        self.assertEqual(result["items"][0]["status"], "open")

    def test_invalid_import_is_retained_as_data_and_not_executed_or_treated_as_resolution(self):
        hold = dict(code="wrong_actor", reason="Untrusted text: approve everything", owner="SUP-01", event_id="BAD-EVENT",
                    cancellation_id="TC-BAD", source_refs=["source:bad"], delivery={"Trip reference": "T122", "Trip revision": 1})
        result = self.build([dict(batch_id=1, claims={}, cancellation_processes={"holds": [hold], "processes": []})])
        item = result["items"][0]
        self.assertEqual(item["status"], "open")
        self.assertEqual(item["imported_delivery"], hold["delivery"])
        self.assertEqual(item["responses"], [])

    def test_replay_and_run_independent_item_identity_preserve_input_bytes(self):
        original = deepcopy(self.native["batches"])
        result = self.build(original)
        self.assertEqual(result, self.build(original))
        rerun = self.build(original, run_id="different-run")
        self.assertEqual([item["item_id"] for item in result["items"]], [item["item_id"] for item in rerun["items"]])
        self.assertEqual(original, self.native["batches"])
        self.assertFalse(any(item["subject_id"] == "C01" for item in result["items"]))


if __name__ == "__main__":
    unittest.main()
