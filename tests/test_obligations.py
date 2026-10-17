from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import unittest

from travel_expense_claim.finance import summarize_finance
from travel_expense_claim.independence import visible_at
from travel_expense_claim.obligations import reconcile_prior_costs
from travel_expense_claim.recheck import claim_versions
from travel_expense_claim.verify_independence import Sources, field


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/review-20261017033849Z/sources.json"


def claim(identity, costs, *, batch=1, revision=1, related=()):
    return {"id": identity, "revision": revision, "batch": batch, "employee": "EMP-01",
            "trip": "T", "trip_revision": 1, "related_claims": list(related),
            "source_ref": f"isolated-fixture:{identity}:r{revision}",
            "lines": [{"cost_id": cost, "receipt_id": "R-" + cost,
                       "currency": "EUR", "gross": Decimal(str(amount))} for cost, amount in costs]}


def request(identity, claim_id, amount, paid=None, *, batch=1):
    return {"claim_id": claim_id, "accepted_arrival_batch": batch,
            "accepted_time": f"2026-09-{10 + batch:02d}T12:00:00Z", "finance_officer": "FIN-01",
            "initial_obligation_cents": amount, "current_obligation_cents": amount,
            "net_paid_cents": amount if paid is None else paid, "holds": [],
            "source_refs": ["isolated-fixture:" + identity]}


class NativePriorCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources(MANIFEST)
        cls.versions = claim_versions(cls.sources)
        # Bind the explicit source relationship even before the shared parser's
        # related_claims field is integrated by the orchestration component.
        cls.final = next(version for version in cls.versions if version["id"] == "C24")
        page = cls.sources.read("UPDATES-PAGES")[2]
        cls.final["related_claims"] = [field(page["text"], "Related earlier claims")]
        cls.original = next(version for version in cls.versions if version["id"] == "C03")
        people = {row["Employee ID"]: row for row in cls.sources.table("People")}
        rows = [row for row in cls.sources.table("Finance activity") if row["Claim reference"] in {"C03", "C24"}]
        cls.finance = summarize_finance(visible_at(rows, 4), people,
            {version["id"]: version for version in cls.versions},
            cls.sources.data["case_clock"], cls.sources.data["case_timezone"])

    def test_c24_preserves_reviewed_250_but_excludes_prepaid_200_from_new_obligation(self):
        result = reconcile_prior_costs(self.final, self.versions, self.finance)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["exclusion_by_cost_cents"], {"COST-03": 20000})
        self.assertEqual(result["original_request_ids"], ["REQ-C03"])
        reviewed = sum(int(line["gross"] * 100) for line in self.final["lines"])
        self.assertEqual(reviewed, 25000)
        self.assertEqual(reviewed - sum(result["exclusion_by_cost_cents"].values()), 5000)
        self.assertEqual(result["links"][0]["original_claim_id"], "C03")
        self.assertIn("INITIAL:page3", result["source_refs"])
        self.assertIn("UPDATES:page3", result["source_refs"])
        self.assertIn("REGISTERS-FINANCE-ACTIVITY:row8", result["source_refs"])

    def test_later_final_claim_cannot_hold_or_reimburse_the_origin_again(self):
        original = reconcile_prior_costs(self.original, self.versions, self.finance)
        self.assertEqual(original["findings"], [])
        self.assertEqual(original["exclusion_by_cost_cents"], {})
        self.assertEqual(original["original_request_ids"], [])
        self.assertEqual(self.finance["claims"]["C03"]["net_paid_cents"], 20000)
        self.assertEqual(self.finance["claims"]["C24"]["net_paid_cents"], 5000)

    def test_replay_is_deterministic_and_source_histories_are_not_mutated(self):
        before = deepcopy((self.final, self.versions, self.finance))
        first = reconcile_prior_costs(self.final, self.versions, self.finance)
        self.assertEqual(first, reconcile_prior_costs(self.final, self.versions, self.finance))
        self.assertEqual(before, (self.final, self.versions, self.finance))


class PriorCostBindingTests(unittest.TestCase):
    def setUp(self):
        self.original = claim("A", [("X", 100)])
        self.final = claim("B", [("X", 100), ("Z", 20)], batch=3, related=["A"])
        self.versions = [self.original, self.final]
        self.finance = {"requests": {"REQ-A": request("REQ-A", "A", 10000)}}

    def run_case(self, final=None, versions=None, finance=None, evaluated=None):
        return reconcile_prior_costs(final or self.final, versions or self.versions,
                                     finance or self.finance, evaluated)

    def test_receipt_link_or_acceptance_alone_is_not_confirmed_payment(self):
        finance = deepcopy(self.finance)
        finance["requests"]["REQ-A"]["net_paid_cents"] = 0
        result = self.run_case(finance=finance)
        self.assertEqual(result["exclusion_by_cost_cents"], {})
        self.assertEqual(result["findings"][0]["code"], "prior_cost_unsettled")
        missing = self.run_case(finance={"requests": {}})
        self.assertEqual(missing["exclusion_by_cost_cents"], {})
        self.assertEqual(missing["findings"][0]["code"], "prior_cost_unsettled")

    def test_explicit_link_and_every_cost_identity_must_bind(self):
        unlinked = deepcopy(self.final)
        unlinked["related_claims"] = []
        result = self.run_case(final=unlinked)
        self.assertEqual(result["exclusion_by_cost_cents"], {})
        self.assertEqual(result["findings"][0]["code"], "unlinked_shared_cost")
        mutations = [("employee", "EMP-02"), ("trip", "OTHER"), ("trip_revision", 2)]
        for key, value in mutations:
            with self.subTest(key=key):
                final = deepcopy(self.final)
                final[key] = value
                result = self.run_case(final=final)
                self.assertEqual(result["findings"][0]["code"], "prior_cost_identity_conflict")
                self.assertEqual(result["exclusion_by_cost_cents"], {})
        for key, value in [("currency", "USD"), ("gross", Decimal("99.99"))]:
            final = deepcopy(self.final)
            final["lines"][0][key] = value
            self.assertEqual(self.run_case(final=final)["findings"][0]["code"], "prior_cost_identity_conflict")

    def test_only_confirmed_single_cost_partial_payment_is_excluded_and_rest_stays_held(self):
        finance = deepcopy(self.finance)
        finance["requests"]["REQ-A"]["net_paid_cents"] = 4000
        result = self.run_case(finance=finance)
        self.assertEqual(result["exclusion_by_cost_cents"], {"X": 4000})
        self.assertEqual(result["findings"][0]["code"], "prior_cost_unsettled")
        self.assertEqual(result["findings"][0]["owner"], "FIN-01")

    def test_multi_cost_request_needs_exact_accepted_revision_allocation_and_full_settlement(self):
        original = claim("A", [("X", 100), ("Y", 50)])
        versions = [original, self.final]
        finance = {"requests": {"REQ-A": request("REQ-A", "A", 15000)}}
        missing = self.run_case(versions=versions, finance=finance)
        self.assertEqual(missing["findings"][0]["code"], "prior_cost_allocation_unknown")
        evaluated = {"A": {"revision": 1, "lines": [
            {"cost_id": "X", "calculation": {"allowed_cents": 10000}},
            {"cost_id": "Y", "calculation": {"allowed_cents": 5000}}]}}
        result = self.run_case(versions=versions, finance=finance, evaluated=evaluated)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["exclusion_by_cost_cents"], {"X": 10000})
        evaluated["A"]["revision"] = 2
        self.assertEqual(self.run_case(versions=versions, finance=finance, evaluated=evaluated)["findings"][0]["code"], "prior_cost_allocation_unknown")
        evaluated["A"]["revision"] = 1
        finance["requests"]["REQ-A"]["net_paid_cents"] = 5000
        partial = self.run_case(versions=versions, finance=finance, evaluated=evaluated)
        self.assertEqual(partial["exclusion_by_cost_cents"], {})
        self.assertEqual(partial["findings"][0]["code"], "prior_cost_allocation_unknown")

    def test_accepted_basis_does_not_union_unaccepted_old_costs(self):
        revised = claim("A", [("Y", 100)], batch=2, revision=2)
        finance = {"requests": {"REQ-A": request("REQ-A", "A", 10000, batch=2)}}
        result = self.run_case(versions=[self.original, revised, self.final], finance=finance)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["exclusion_by_cost_cents"], {})

    def test_late_old_revision_does_not_replace_the_current_accepted_cost_basis(self):
        current = claim("A", [("X", 100)], batch=1, revision=2)
        late_old = claim("A", [("Y", 100)], batch=2, revision=1)
        finance = {"requests": {"REQ-A": request("REQ-A", "A", 10000, batch=2)}}
        result = self.run_case(versions=[current, late_old, self.final], finance=finance)
        self.assertEqual(result["exclusion_by_cost_cents"], {"X": 10000})

    def test_original_request_employee_cannot_borrow_another_claim_cost_identity(self):
        finance = deepcopy(self.finance)
        finance["requests"]["REQ-A"]["employee_id"] = "EMP-02"
        result = self.run_case(finance=finance)
        self.assertEqual(result["exclusion_by_cost_cents"], {})
        self.assertEqual(result["findings"][0]["code"], "prior_cost_basis_unknown")

    def test_multiple_original_requests_and_changed_obligation_are_not_guessed(self):
        second = claim("A2", [("X", 100)])
        final = deepcopy(self.final)
        final["related_claims"].append("A2")
        finance = deepcopy(self.finance)
        finance["requests"]["REQ-A2"] = request("REQ-A2", "A2", 10000)
        result = self.run_case(final=final, versions=[self.original, second, final], finance=finance)
        self.assertEqual(result["exclusion_by_cost_cents"], {})
        self.assertEqual(result["findings"][0]["code"], "prior_cost_allocation_ambiguous")
        changed = deepcopy(self.finance)
        changed["requests"]["REQ-A"].update(current_obligation_cents=8000, net_paid_cents=8000)
        self.assertEqual(self.run_case(finance=changed)["findings"][0]["code"], "prior_cost_basis_changed")

    def test_missing_self_or_held_prior_basis_stays_owned_and_visible(self):
        for identity in ["MISSING", "B"]:
            final = deepcopy(self.final)
            final["related_claims"] = [identity]
            self.assertIn("invalid_prior_claim_link", {f["code"] for f in self.run_case(final=final)["findings"]})
        held = deepcopy(self.finance)
        held["requests"]["REQ-A"]["holds"] = [{"code": "event_conflict"}]
        result = self.run_case(finance=held)
        self.assertEqual(result["exclusion_by_cost_cents"], {})
        self.assertEqual(result["findings"][0]["code"], "prior_cost_finance_unresolved")


if __name__ == "__main__":
    unittest.main()
