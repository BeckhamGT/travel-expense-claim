from copy import deepcopy
from decimal import Decimal
import unittest

from travel_expense_claim.monetary import calculate_line


FX = [{"Rate reference": "FX-USD", "Rate date": "2026-09-01", "Currency": "USD",
       "EUR per currency unit": Decimal("0.9"), "_ref": "REGISTERS-FX:row7"}]
CAPS = [
    {"Cap reference": "CAP-lodging", "Destination": "NL", "Category": "lodging", "Currency": "EUR",
     "Effective from": "2026-01-01", "Effective to": "2026-12-31", "Amount per unit": Decimal("150"), "_ref": "REGISTERS-CAPS:row6"},
    {"Cap reference": "CAP-meals", "Destination": "NL", "Category": "meals", "Currency": "EUR",
     "Effective from": "2026-01-01", "Effective to": "2026-12-31", "Amount per unit": Decimal("40"), "_ref": "REGISTERS-CAPS:row7"},
]


def line(**changes):
    values = dict(gross=Decimal("80"), currency="EUR", category="transport", units=1,
                  destination="NL", payment_date="2026-09-01", fx_rows=FX, caps_rows=CAPS)
    values.update(changes)
    return calculate_line(**values)


def codes(result):
    return {finding["code"] for finding in result["findings"]}


class MonetaryTests(unittest.TestCase):
    def test_provided_c09_and_c19_values_and_replacement(self):
        self.assertEqual(line()["allowed_cents"], 8000)
        self.assertEqual(line(gross="100")["allowed_cents"], 10000)
        corrected = line(gross="100", replacement_allowed="80")
        self.assertEqual(corrected["allowed_cents"], 8000)
        self.assertEqual(corrected["allowed_original"], "80")
        self.assertEqual(corrected["rate"], "1")
        self.assertEqual(corrected["findings"][0]["ordinary_allowed_original"], "100")

    def test_finance_replacement_has_no_invented_paid_gross_upper_bound(self):
        self.assertEqual(line(gross="80", replacement_allowed="90")["allowed_cents"], 9000)
        for amount in ["-1", "NaN", "Infinity"]:
            with self.subTest(amount=amount):
                self.assertIsNone(line(replacement_allowed=amount)["allowed_cents"])

    def test_transport_conference_threshold_values_are_not_caps(self):
        for category in ["transport", "conference"]:
            for gross, expected in [("999.99", 99999), ("1000.00", 100000), ("1000.01", 100001)]:
                with self.subTest(category=category, gross=gross):
                    self.assertEqual(line(category=category, gross=gross)["allowed_cents"], expected)

    def test_lodging_meal_cap_boundaries_and_units(self):
        for category, amounts in [("lodging", [("149.99", 14999), ("150", 15000), ("150.01", 15000)]),
                                  ("meals", [("39.99", 3999), ("40", 4000), ("40.01", 4000)])]:
            for gross, expected in amounts:
                with self.subTest(category=category, gross=gross):
                    self.assertEqual(line(category=category, gross=gross)["allowed_cents"], expected)
        self.assertEqual(line(category="lodging", gross="360", units=2)["allowed_cents"], 30000)

    def test_cap_uses_original_currency_destination_and_inclusive_payment_date(self):
        for paid in ["2026-01-01", "2026-12-31"]:
            self.assertEqual(line(category="lodging", gross="200", payment_date=paid)["allowed_cents"], 15000)
        for change in [dict(destination="BE"), dict(currency="USD"), dict(payment_date="2027-01-01")]:
            with self.subTest(change=change):
                result = line(category="lodging", gross="200", **change)
                self.assertIsNone(result["allowed_cents"])
                self.assertIn("missing_cap", codes(result))
        usd_cap = {**CAPS[0], "Currency": "USD", "Amount per unit": Decimal("50")}
        result = line(category="lodging", currency="USD", gross="100", caps_rows=[usd_cap])
        self.assertEqual(result["allowed_cents"], 4500)
        self.assertEqual(result["allowed_original"], "50")

    def test_missing_ambiguous_cap_never_becomes_zero_even_with_replacement(self):
        for rows, code in [([], "missing_cap"), ([CAPS[0], CAPS[0]], "ambiguous_cap")]:
            result = line(category="lodging", caps_rows=rows, replacement_allowed="20")
            self.assertIsNone(result["allowed_cents"])
            self.assertIsNone(result["allowed_original"])
            self.assertIn(code, codes(result))

    def test_original_cap_finding_survives_replacement(self):
        result = line(category="lodging", gross="200", replacement_allowed="180")
        self.assertEqual(result["allowed_cents"], 18000)
        self.assertEqual(codes(result), {"cap_applied", "replacement_applied"})
        self.assertTrue(all(not f["blocking"] for f in result["findings"]))
        self.assertIn("REGISTERS-CAPS:row6", result["source_refs"])

    def test_eur_zero_personal_zero_and_unknown_are_distinct(self):
        self.assertEqual(line(gross=0, fx_rows=[])["allowed_cents"], 0)
        personal = line(category="personal", currency="GBP", fx_rows=[])
        self.assertEqual(personal["allowed_cents"], 0)
        self.assertIsNone(personal["rate"])
        self.assertIn("personal_excluded", codes(personal))
        unknown = line(category="entertainment", gross=0, replacement_allowed=0)
        self.assertIsNone(unknown["allowed_cents"])
        self.assertIn("unknown_category", codes(unknown))

    def test_fx_needs_unique_exact_payment_date_currency_and_positive_value(self):
        result = line(currency="USD", gross="600")
        self.assertEqual(result["allowed_cents"], 54000)
        self.assertEqual(result["rate"], "0.9")
        self.assertEqual(result["source_refs"], ["REGISTERS-FX:row7"])
        for change in [dict(currency="GBP"), dict(payment_date="2026-09-02"), dict(fx_rows=[])]:
            with self.subTest(change=change):
                result = line(**{"currency": "USD", **change})
                self.assertIsNone(result["allowed_cents"])
                self.assertIn("missing_rate", codes(result))
                self.assertIsNotNone(result["allowed_original"])
        result = line(currency="USD", fx_rows=FX * 2)
        self.assertIsNone(result["allowed_cents"])
        self.assertIn("ambiguous_rate", codes(result))
        for rate in ["0", "-1", "NaN", "Infinity"]:
            with self.subTest(rate=rate):
                self.assertIn("invalid_rate", codes(line(currency="USD", fx_rows=[{**FX[0], "EUR per currency unit": rate}])))

    def test_half_up_happens_per_line_before_summing(self):
        lines = [line(currency="USD", gross="1.15", category=category) for category in ["transport", "conference"]]
        self.assertEqual([r["allowed_cents"] for r in lines], [104, 104])
        self.assertEqual(sum(r["allowed_cents"] for r in lines), 208)
        self.assertEqual(line(currency="USD", gross="2.30")["allowed_cents"], 207)
        self.assertEqual([line(currency="USD", gross="1.16")["allowed_cents"] for _ in range(2)], [104, 104])

    def test_invalid_inputs_and_definitions_remain_unresolved(self):
        for change in [dict(gross="-1"), dict(gross="NaN"), dict(units=0), dict(units="1.5"),
                       dict(units=True), dict(currency="eur"), dict(payment_date="2026-02-30")]:
            with self.subTest(change=change):
                self.assertIn("invalid_input", codes(line(**change)))
        for field, value in [("Amount per unit", "-1"), ("Effective from", "bad-date"), ("Effective to", "2025-01-01")]:
            with self.subTest(field=field):
                self.assertIn("invalid_cap", codes(line(category="lodging", caps_rows=[{**CAPS[0], field: value}])))
        self.assertIn("invalid_rate", codes(line(currency="USD", fx_rows=[{**FX[0], "Rate date": "bad-date"}])))

    def test_inputs_are_not_mutated_and_decimal_precision_is_preserved(self):
        caps, fx = deepcopy(CAPS), deepcopy(FX)
        before = deepcopy((caps, fx))
        result = line(currency="USD", gross="123456789012345678901234567890.15", caps_rows=caps, fx_rows=fx)
        self.assertEqual(result["allowed_cents"], 11111111011111111101111111110114)
        self.assertEqual((caps, fx), before)


if __name__ == "__main__":
    unittest.main()
