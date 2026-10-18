"""Source-backed clarification checks on supplemental offline corpus copies.

C117 facts and the complete interview bytes are real supplied exercise records.
Altered quotes, categories, speakers and payment rows below are deliberately
supplemental negative fixtures, never newly observed business evidence.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from travel_expense_claim.snapshots import validate_snapshot
from travel_expense_claim.verify_independence import Sources
from travel_expense_claim.workflow import build_run


ROOT = Path(__file__).resolve().parents[1]
GRADED = ROOT / "artifacts/runs/submission-20261017T154939Z"
INTERVIEW = ROOT / "interviews/project-d-travel-expense-claim-20261018-0547.md"
INTERVIEW_HASH = "3c2958030d76bd4edf0ce76a5b96f93de61fe208e420766d7ad1e8b9d2d55aa9"


class BusinessDefinitionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="travel-definitions-supplemental-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        shutil.copytree(GRADED / "retained", self.base / "retained")
        original = INTERVIEW.read_bytes()
        self.assertEqual(sha256(original).hexdigest(), INTERVIEW_HASH)
        self.document = self.base / "retained/final-interview.md"
        self.document.write_bytes(original)
        self.lines = original.decode("utf-8").splitlines()
        self.data = json.loads((GRADED / "sources.json").read_text())
        self.data.update(run_id="supplemental-bound-clarification",
                         acquisition_mode="supplemental-offline-fixture",
                         purpose="Retained native corpus and actual interview; no fresh access claimed")
        self.data["documents"] = [dict(
            source_id="INTERVIEW", path="retained/final-interview.md",
            sha256=INTERVIEW_HASH, status="read", error=None,
            source_version="interview-20261018-0547",
            url="WorkSim", locator="Complete original same-conversation final export, lines1-669")]
        self.data["business_definitions"] = dict(
            category_classifications=[dict(
                category="entertainment", policy_category="personal",
                source_ref="INTERVIEW:line669", statement=self.lines[668],
                speaker="Travel Administration Lead")],
            missing_definition_route=dict(
                owner="Exercise operator", source_ref="INTERVIEW:line609",
                statement=self.lines[608], speaker="Travel Administration Lead"))
        self.manifest = self.base / "sources.json"
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.data, indent=2) + "\n")

    @staticmethod
    def claim(result, batch, identity):
        return next(row for row in result["snapshots"][batch - 1]["claims"] if row["claim_id"] == identity)

    def bound(self, *, through=4):
        return build_run(self.manifest, completion_accepted=True, through_batch=through)

    def test_historical_manifest_keeps_undefined_entertainment_unknown(self):
        historical = build_run(GRADED / "sources.json", through_batch=1)
        claim = self.claim(historical, 1, "C117")
        self.assertEqual([line["allowed_cents"] for line in claim["lines"]], [None, 4000])
        self.assertIsNone(claim["allowed_cents"])

    def test_actual_c117_classification_changes_calculation_without_granting_authority(self):
        result = self.bound()
        for batch in range(1, 5):
            with self.subTest(batch=batch):
                claim = self.claim(result, batch, "C117")
                self.assertEqual([line["allowed_cents"] for line in claim["lines"]], [0, 4000])
                self.assertEqual((claim["allowed_cents"], claim["paid_cents"], claim["balance_cents"]),
                                 (4000, 0, 4000))
                self.assertEqual((claim["status"], claim["next_owner"]), ("pending", "ADMIN-01"))
                self.assertFalse(claim["current_review"]["current"])
                self.assertEqual(set(claim["current_review"]["missing_roles"]),
                                 {"administration", "budget_owner", "supervisor"})
                self.assertEqual(claim["decision_ids"], [])
                self.assertFalse(claim["financial_completion_accepted"])
                self.assertFalse(any(request["claim_id"] == "C117"
                                     for request in result["snapshots"][batch - 1]["requests"]))
                personal = claim["lines"][0]
                self.assertEqual(personal["status"], "excluded")
                self.assertIn("INTERVIEW:line669", personal["source_ids"])
                self.assertTrue(any(reference.startswith("POLICY") for reference in personal["source_ids"]))
                self.assertIn("category_classified", {finding["code"] for finding in personal["findings"]})
                self.assertIn("RECEIPTS:page98", personal["source_ids"])
                self.assertIn("REGISTERS-MERCHANT-PAYMENTS:row199", personal["source_ids"])
        items = [item for item in result["queue"]["items"]
                 if item["subject_id"] == "C117" and item["status"] == "open"]
        self.assertEqual({item["code"] for item in items}, {"approval_reply"})
        self.assertEqual({tuple(item["roles"]) for item in items},
                         {("administration",), ("budget_owner",), ("supervisor",)})
        self.assertTrue(all(not item["responses"] for item in items))

    def test_bound_interview_provenance_resolves_in_snapshot_validation(self):
        sources = Sources(self.manifest)
        self.assertIn("INTERVIEW", sources.files)
        self.assertEqual(len({entry["url"] for entry in self.data["files"]}), 5)
        snapshot = self.bound(through=1)["snapshots"][0]
        self.assertIsNone(validate_snapshot(snapshot, ROOT / "snapshot.schema.json", self.manifest,
                                          snapshot_path=self.base / "batches/1.json"))

    def test_missing_numeric_definitions_stay_unknown_and_owned_by_operator(self):
        result = self.bound()
        for identity in ("C22", "C23", "C116"):
            with self.subTest(claim=identity):
                claim = self.claim(result, 4, identity)
                self.assertIsNone(claim["allowed_cents"])
                self.assertEqual((claim["status"], claim["next_owner"]), ("held", "Exercise operator"))
        missing = [item for item in result["queue"]["items"] if item["status"] == "open"
                   and item["subject_id"] in {"C22", "C23", "C116"}
                   and item["code"] in {"missing_rate", "missing_cap"}]
        self.assertEqual(len(missing), 4)
        self.assertEqual({item["owner"] for item in missing}, {"Exercise operator"})
        for item in missing:
            self.assertIn("INTERVIEW:line609", item["source_refs"])
            self.assertIn("Finance", item["next_action"])
            self.assertEqual(item["responses"], [])

    def test_classification_cannot_replace_missing_settled_payment_proof(self):
        original = Sources.table

        def changed(sources, name):
            rows = deepcopy(original(sources, name))
            if name == "Merchant payments":
                for row in rows:
                    if row["Transaction reference"] == "M-COST-117-1":
                        row["Payment status"] = "pending"
            return rows

        with patch.object(Sources, "table", changed):
            claim = self.claim(self.bound(through=1), 1, "C117")
        self.assertIsNone(claim["lines"][0]["allowed_cents"])
        self.assertIsNone(claim["allowed_cents"])
        self.assertEqual(claim["status"], "held")
        self.assertEqual(claim["paid_cents"], 0)

    def test_unmapped_category_remains_unknown(self):
        original = Sources.read

        def changed(sources, identity):
            rows = deepcopy(original(sources, identity))
            if identity == "RECEIPTS-PAGES":
                for page in rows:
                    page["text"] = page["text"].replace("Category: entertainment", "Category: undefined-category")
            return rows

        with patch.object(Sources, "read", changed):
            claim = self.claim(self.bound(through=1), 1, "C117")
        self.assertIsNone(claim["lines"][0]["allowed_cents"])
        self.assertIn("unknown_category", {finding["code"] for finding in claim["lines"][0]["findings"]})

    def test_interview_hash_mismatch_fails_before_processing(self):
        self.document.write_bytes(self.document.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_claimed_excerpt_must_match_original_line_exactly(self):
        record = self.data["business_definitions"]["category_classifications"][0]
        record["statement"] = "Entertainment has a reimbursement entitlement of ten Euros."
        self.save()
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_learner_statement_cannot_supply_lead_category_authority(self):
        record = self.data["business_definitions"]["category_classifications"][0]
        record.update(source_ref="INTERVIEW:line665", statement=self.lines[664], speaker="Beckham Vo")
        self.save()
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_claimed_lead_speaker_must_match_original_message(self):
        altered = self.lines[:]
        altered[666] = altered[666].replace("Travel Administration Lead", "Beckham Vo")
        self.document.write_text("\n".join(altered) + "\n")
        self.data["documents"][0]["sha256"] = sha256(self.document.read_bytes()).hexdigest()
        self.save()
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_existing_eligible_category_cannot_be_overridden_by_unrelated_clarification(self):
        record = self.data["business_definitions"]["category_classifications"][0]
        record["category"] = "transport"
        self.save()
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_weak_generally_personal_text_is_not_the_explicit_classification(self):
        record = self.data["business_definitions"]["category_classifications"][0]
        record.update(source_ref="INTERVIEW:line601", statement=self.lines[600])
        self.save()
        with self.assertRaises(ValueError):
            Sources(self.manifest)

    def test_category_clarification_preserves_actual_finance_and_unrelated_closure(self):
        result = self.bound()
        historical = build_run(GRADED / "sources.json", completion_accepted=True)
        for batch in range(1, 5):
            current = result["snapshots"][batch - 1]
            old = historical["snapshots"][batch - 1]
            self.assertEqual(current["finance_events"], old["finance_events"])
            self.assertEqual(current["requests"], old["requests"])
            for identity in ("C18", "C19", "C20"):
                observed, previous = (self.claim(run, batch, identity) for run in (result, historical))
                for field in ("status", "allowed_cents", "paid_cents", "gross_paid_cents", "refunded_cents",
                              "authorized_obligation_cents", "balance_cents", "decision_ids",
                              "finance_resolution_required", "current_resolution_event_ids"):
                    self.assertEqual(observed[field], previous[field], (batch, identity, field))
        late = self.claim(result, 4, "C18")
        self.assertEqual((late["status"], late["paid_cents"], late["balance_cents"]), ("held", 10000, -10000))
        self.assertEqual(self.claim(result, 4, "C19")["status"], "closed-reimbursed")
        self.assertEqual(self.claim(result, 4, "C20")["status"], "closed-reimbursed")


if __name__ == "__main__":
    unittest.main()
