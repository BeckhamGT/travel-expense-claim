"""Isolated serialization fixtures; these are not operational business outputs."""

from copy import deepcopy
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from travel_expense_claim.snapshots import CSV_COLUMNS, SnapshotError, claims_csv, validate_snapshot, write_snapshot


SCHEMA = Path(__file__).resolve().parents[1] / "snapshot.schema.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="travel-snapshot-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        (self.base / "retained").mkdir()
        files = []
        for number in range(1, 6):
            retained = self.base / "retained" / f"source-{number}.txt"
            retained.write_text(f"Isolated fixture source {number}\n", encoding="utf-8")
            files.append(dict(source_id=f"S{number}", path=str(retained.relative_to(self.base)),
                sha256=digest(retained), status="read", error=None,
                url=f"https://example.invalid/native-{number}", locator="Complete isolated fixture",
                observed_at="2026-10-01T12:00:00Z", source_version="fixture/1"))
        self.manifest = dict(run_id="isolated-fixture", source_version="fixture/1", case_clock="2026-11-15", files=files)
        self.sources = self.base / "sources.json"
        self.save_manifest()
        self.first_path = self.base / "batches" / "1.json"
        self.first = dict(schema_version="travel-claim-snapshot/2", run_id="isolated-fixture", batch_id="1",
            predecessor=None, source_binding=dict(path="../sources.json", sha256=digest(self.sources)),
            claims=[dict(claim_id="CLAIM-A", revision=1, trip_id="TRIP-A", trip_revision=1,
                status="pending", lines=[dict(cost_id="COST-A", source_ids=["S1:record-A"],
                status="supported", allowed_cents=1000, reason="Fixture supported cost")],
                allowed_cents=1000, paid_cents=400, balance_cents=600, decision_ids=["DECISION-A"],
                next_owner="FINANCE-A", reason="Await remaining source-backed payment")],
            requests=[dict(request_id="REQUEST-A", claim_id="CLAIM-A", revision=1, amount_cents=1000,
                payee="EMPLOYEE-A", currency="EUR", status="accepted", decision_ids=["DECISION-A"])],
            travel_cancellations=[], admitted_event_ids=["FINANCE-EVENT-A"], issues=[])

    def save_manifest(self):
        self.sources.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def validate(self, data=None, predecessor=None, path=None):
        return validate_snapshot(self.first if data is None else data, SCHEMA, self.sources,
                                 predecessor, snapshot_path=self.first_path if path is None else path)

    def following(self, previous_path, data=None):
        current = deepcopy(self.first if data is None else data)
        previous = json.loads(previous_path.read_text())
        current.update(batch_id=str(int(previous["batch_id"]) + 1),
                       predecessor=dict(path=previous_path.name, sha256=digest(previous_path)))
        return current

    def process(self, *, affected=False):
        return dict(cancellation_id="CANCEL-A", target_type="trip", trip_id="TRIP-A" if affected else "TRIP-NO-CLAIM",
            trip_revision=1, permit_id=None, permit_revision=None, status="confirmed",
            admitted_cancellation_event_ids=["CANCEL-REQUEST-A", "CANCEL-CONFIRM-A"],
            requested_at="2026-10-01T09:00:00Z", confirmed_at="2026-10-02T09:00:00Z",
            effective_at="2026-10-02T09:00:00Z", affected_claim_ids=["CLAIM-A"] if affected else [],
            original_request_ids=["REQUEST-A"] if affected else [],
            financial_status="unresolved" if affected else "no-financial-effect", next_owner="FINANCE-A" if affected else None,
            reason="Isolated cancellation fixture", issue_record_ids=[])

    def test_required_schema_and_formats_validate_without_changing_input(self):
        before = deepcopy(self.first)
        self.assertIsNone(self.validate())
        self.assertEqual(self.first, before)
        self.assertIsNone(validate_snapshot(self.first, SCHEMA, self.sources))
        extra = deepcopy(self.first)
        extra["provenance"] = {"fixture": True}
        self.validate(extra)

    def test_atomic_write_is_utf8_and_unchanged_replay_preserves_bytes_and_mtime(self):
        data = deepcopy(self.first)
        data["claims"][0]["reason"] = "Évidence retained, awaiting response"
        self.assertEqual(write_snapshot(self.first_path, data, SCHEMA, self.sources), self.first_path)
        original, stamp = self.first_path.read_bytes(), self.first_path.stat().st_mtime_ns
        self.assertIn("Évidence".encode(), original)
        self.assertTrue(original.endswith(b"\n"))
        write_snapshot(self.first_path, data, SCHEMA, self.sources)
        self.assertEqual((self.first_path.read_bytes(), self.first_path.stat().st_mtime_ns), (original, stamp))
        self.assertEqual(list(self.first_path.parent.glob(".snapshot-*.tmp")), [])

    def test_distinct_existing_snapshot_is_never_overwritten(self):
        write_snapshot(self.first_path, self.first, SCHEMA, self.sources)
        original = self.first_path.read_bytes()
        changed = deepcopy(self.first)
        changed["claims"][0]["reason"] = "A distinct result belongs to a new run"
        with self.assertRaisesRegex(SnapshotError, "Distinct sealed"):
            write_snapshot(self.first_path, changed, SCHEMA, self.sources)
        self.assertEqual(self.first_path.read_bytes(), original)

    def test_invalid_state_cannot_create_an_output_or_directory(self):
        bad = deepcopy(self.first)
        bad["schema_version"] = "wrong"
        with self.assertRaises(SnapshotError):
            write_snapshot(self.first_path, bad, SCHEMA, self.sources)
        self.assertFalse(self.first_path.parent.exists())

    def test_publish_race_does_not_overwrite_other_writer_or_leave_temporary_file(self):
        def competitor(temporary, destination):
            Path(destination).write_bytes(b"other sealed result\n")
            raise FileExistsError
        with patch("travel_expense_claim.snapshots.os.link", competitor):
            with self.assertRaisesRegex(SnapshotError, "Distinct sealed"):
                write_snapshot(self.first_path, self.first, SCHEMA, self.sources)
        self.assertEqual(self.first_path.read_bytes(), b"other sealed result\n")
        self.assertEqual(list(self.first_path.parent.glob(".snapshot-*.tmp")), [])

    def test_four_immediate_bound_snapshots_and_original_request_revision_are_preserved(self):
        data, previous = deepcopy(self.first), None
        for batch in range(1, 5):
            path = self.base / "batches" / f"{batch}.json"
            if previous is not None:
                data = self.following(previous, data)
                data["claims"][0]["revision"] = batch
            write_snapshot(path, data, SCHEMA, self.sources, previous)
            self.validate(data, previous, path)
            self.assertEqual(data["requests"][0]["revision"], 1)
            previous = path

    def test_missing_tampered_skipped_or_wrong_run_predecessor_is_rejected(self):
        write_snapshot(self.first_path, self.first, SCHEMA, self.sources)
        second = self.following(self.first_path)
        second_path = self.base / "batches" / "2.json"
        for field, value, message in [
            ("predecessor", None, "requires"),
            ("predecessor", dict(path="missing.json", sha256="0" * 64), "Predecessor path"),
            ("predecessor", dict(path="1.json", sha256="0" * 64), "hash mismatch"),
            ("batch_id", "3", "immediately preceding"),
            ("run_id", "other-run", "run IDs"),
        ]:
            with self.subTest(field=field, value=value):
                bad = deepcopy(second)
                bad[field] = value
                with self.assertRaisesRegex(SnapshotError, message):
                    self.validate(bad, self.first_path, second_path)
        missing = deepcopy(second)
        missing["predecessor"]["path"] = "missing.json"
        with self.assertRaisesRegex(SnapshotError, "Missing"):
            self.validate(missing, path=second_path)
        self.first_path.write_bytes(self.first_path.read_bytes() + b" ")
        with self.assertRaisesRegex(SnapshotError, "hash mismatch"):
            self.validate(second, self.first_path, second_path)

    def test_first_predecessor_self_hash_absolute_bindings_and_path_escape_are_rejected(self):
        for field, value in [
            ("predecessor", dict(path="1.json", sha256="0" * 64)),
            ("source_binding", dict(path=str(self.sources), sha256=digest(self.sources))),
            ("source_binding", dict(path="../../outside.json", sha256="0" * 64)),
            ("source_binding", dict(path="1.json", sha256="0" * 64)),
        ]:
            bad = deepcopy(self.first)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(SnapshotError):
                self.validate(bad)
        bad = deepcopy(self.first)
        bad.update(batch_id="2", predecessor=dict(path="2.json", sha256="0" * 64))
        with self.assertRaisesRegex(SnapshotError, "hash itself"):
            self.validate(bad, path=self.base / "batches" / "2.json")

    def test_full_chain_rechecks_the_earlier_source_binding_not_just_immediate_bytes(self):
        write_snapshot(self.first_path, self.first, SCHEMA, self.sources)
        second = self.following(self.first_path)
        second_path = self.base / "batches" / "2.json"
        write_snapshot(second_path, second, SCHEMA, self.sources, self.first_path)
        third = self.following(second_path, second)
        first = deepcopy(self.first)
        first["source_binding"]["sha256"] = "0" * 64
        self.first_path.write_text(json.dumps(first), encoding="utf-8")
        second["predecessor"]["sha256"] = digest(self.first_path)
        second_path.write_text(json.dumps(second), encoding="utf-8")
        third["predecessor"]["sha256"] = digest(second_path)
        with self.assertRaisesRegex(SnapshotError, "Source manifest binding hash mismatch"):
            self.validate(third, second_path, self.base / "batches" / "3.json")

    def test_unique_current_records_and_costs_are_required(self):
        for collection in ["claims", "requests", "issues", "travel_cancellations"]:
            bad = deepcopy(self.first)
            if collection == "issues":
                bad[collection] = [dict(record_id="ISSUE-A", reason="Missing fact", owner="EMPLOYEE-A", resolution_needed="Supply fact")]
            elif collection == "travel_cancellations":
                bad[collection] = [self.process()]
            bad[collection].append(deepcopy(bad[collection][0]))
            with self.subTest(collection=collection), self.assertRaisesRegex(SnapshotError, "Duplicate"):
                self.validate(bad)
        bad = deepcopy(self.first)
        bad["claims"][0]["lines"].append(deepcopy(bad["claims"][0]["lines"][0]))
        with self.assertRaisesRegex(SnapshotError, "Duplicate"):
            self.validate(bad)

    def test_line_source_ids_resolve_and_unavailable_reads_do_not_support_a_line(self):
        for refs in [[], ["UNKNOWN"], ["UNKNOWN:page1"]]:
            bad = deepcopy(self.first)
            bad["claims"][0]["lines"][0]["source_ids"] = refs
            with self.subTest(refs=refs), self.assertRaises(SnapshotError):
                self.validate(bad)
        self.manifest["files"][0].update(path=None, sha256=None, status="unavailable", error="Isolated denied read", source_version=None)
        self.save_manifest()
        bad = deepcopy(self.first)
        bad["source_binding"]["sha256"] = digest(self.sources)
        with self.assertRaisesRegex(SnapshotError, "unavailable"):
            self.validate(bad)
        claim = bad["claims"][0]
        claim["lines"][0].update(status="unresolved", allowed_cents=None)
        claim.update(status="held", allowed_cents=None, balance_cents=None)
        self.validate(bad)

    def test_manifest_read_unavailable_hash_precision_and_coverage_constraints(self):
        mutations = [
            lambda m: m["files"].pop(),
            lambda m: m["files"][1].update(source_id="S1"),
            lambda m: m["files"][0].update(sha256="0" * 64),
            lambda m: m["files"][0].update(path="../outside.txt"),
            lambda m: m["files"][0].update(observed_at="2026-10-01"),
            lambda m: m["files"][0].update(observed_at="2026-10-01T12:00:00+02:00"),
            lambda m: m["files"][0].update(status="unavailable", error=None),
            lambda m: m["files"][0].update(path="sources.json"),
        ]
        original = deepcopy(self.manifest)
        for mutation in mutations:
            self.manifest = deepcopy(original)
            mutation(self.manifest)
            self.save_manifest()
            bad = deepcopy(self.first)
            bad["source_binding"]["sha256"] = digest(self.sources)
            with self.subTest(manifest=self.manifest), self.assertRaises(SnapshotError):
                self.validate(bad)

    def test_exact_cents_line_totals_balances_and_null_are_not_interchangeable(self):
        for target, field, value in [
            ("claim", "paid_cents", True), ("claim", "paid_cents", 400.0),
            ("claim", "allowed_cents", 999), ("claim", "balance_cents", 0),
            ("line", "allowed_cents", 1.5), ("request", "amount_cents", 1000.0),
        ]:
            bad = deepcopy(self.first)
            row = bad["claims"][0] if target == "claim" else bad["requests"][0] if target == "request" else bad["claims"][0]["lines"][0]
            row[field] = value
            with self.subTest(target=target, field=field, value=value), self.assertRaises(SnapshotError):
                self.validate(bad)
        bad = deepcopy(self.first)
        bad["claims"][0]["lines"][0]["allowed_cents"] = None
        with self.assertRaisesRegex(SnapshotError, "line amounts"):
            self.validate(bad)
        bad["claims"][0].update(allowed_cents=None, balance_cents=None)
        self.validate(bad)
        bad["claims"][0]["balance_cents"] = 0
        with self.assertRaisesRegex(SnapshotError, "preserving null"):
            self.validate(bad)

    def test_request_claim_revision_and_cancellation_issue_links_resolve(self):
        for mutation in [
            lambda d: d["requests"][0].update(claim_id="MISSING"),
            lambda d: d["requests"][0].update(revision=2),
            lambda d: d["travel_cancellations"][0].update(affected_claim_ids=["MISSING"]),
            lambda d: d["travel_cancellations"][0].update(original_request_ids=["MISSING"]),
            lambda d: d["travel_cancellations"][0].update(affected_claim_ids=[]),
            lambda d: d["travel_cancellations"][0].update(issue_record_ids=["MISSING"]),
        ]:
            bad = deepcopy(self.first)
            bad["travel_cancellations"] = [self.process(affected=True)]
            mutation(bad)
            with self.subTest(snapshot=bad), self.assertRaises(SnapshotError):
                self.validate(bad)
        good = deepcopy(self.first)
        good["issues"] = [dict(record_id="ISSUE-A", reason="Pending disposition", owner="FINANCE-A", resolution_needed="Provide bound disposition")]
        process = self.process(affected=True)
        process["issue_record_ids"] = ["ISSUE-A"]
        good["travel_cancellations"] = [process]
        self.validate(good)

    def test_cancellation_formats_domains_chronology_and_required_owner(self):
        mutations = [
            dict(requested_at="2026-10-01 09:00:00 UTC"),
            dict(requested_at="2026-10-01T09:00:00+02:00"),
            dict(confirmed_at="2026-10-01T09:00:00Z", effective_at="2026-10-01T09:00:00Z"),
            dict(effective_at="2026-10-03T09:00:00Z"),
            dict(admitted_cancellation_event_ids=["FINANCE-EVENT-A"]),
            dict(financial_status="unresolved", next_owner=None),
            dict(status="requested", confirmed_at=None, effective_at=None, next_owner=None),
        ]
        for changes in mutations:
            bad = deepcopy(self.first)
            process = self.process()
            process.update(changes)
            bad["travel_cancellations"] = [process]
            with self.subTest(changes=changes), self.assertRaises(SnapshotError):
                self.validate(bad)

    def test_chain_preserves_admitted_ids_requests_and_process_history(self):
        first = deepcopy(self.first)
        first["travel_cancellations"] = [self.process()]
        write_snapshot(self.first_path, first, SCHEMA, self.sources)
        for mutation in [
            lambda d: d.update(admitted_event_ids=[]),
            lambda d: d.update(requests=[]),
            lambda d: d.update(travel_cancellations=[]),
            lambda d: d["requests"][0].update(payee="OTHER"),
            lambda d: d["requests"][0].update(amount_cents=2000),
            lambda d: d["claims"][0].update(paid_cents=500, balance_cents=500),
            lambda d: d["travel_cancellations"][0].update(permit_id="P-OTHER", permit_revision=1),
            lambda d: d["travel_cancellations"][0].update(admitted_cancellation_event_ids=["CANCEL-CONFIRM-A"]),
            lambda d: d["travel_cancellations"][0].update(status="requested", confirmed_at=None, effective_at=None, next_owner="SUPERVISOR-A"),
        ]:
            bad = self.following(self.first_path, first)
            mutation(bad)
            with self.subTest(snapshot=bad), self.assertRaises(SnapshotError):
                self.validate(bad, self.first_path, self.base / "batches" / "2.json")

    def test_explicit_zero_authorized_obligation_preserves_reviewed_withdrawn_or_rejected_evidence(self):
        for status in ("withdrawn", "rejected"):
            data = deepcopy(self.first)
            data["claims"][0].update(status=status, authorized_obligation_cents=0,
                paid_cents=0, balance_cents=0, reason="Explicit non-payment outcome; reviewed evidence retained")
            data.update(requests=[], admitted_event_ids=[])
            with self.subTest(status=status):
                self.validate(data)
                self.assertEqual(data["claims"][0]["allowed_cents"], 1000)

    def test_unaccepted_proposal_can_be_rebuilt_for_a_corrected_revision_without_inventing_finance(self):
        first = deepcopy(self.first)
        first["claims"][0].update(paid_cents=0, balance_cents=1000)
        first["requests"][0]["status"] = "proposed"
        first["admitted_event_ids"] = []
        write_snapshot(self.first_path, first, SCHEMA, self.sources)
        second = self.following(self.first_path, first)
        second["claims"][0].update(revision=2, allowed_cents=800, balance_cents=800)
        second["claims"][0]["lines"][0]["allowed_cents"] = 800
        second["requests"][0].update(revision=2, amount_cents=800)
        self.validate(second, self.first_path, self.base / "batches" / "2.json")

    def test_excluded_prepaid_line_does_not_duplicate_incremental_entitlement(self):
        data = deepcopy(self.first)
        claim = data["claims"][0]
        claim["lines"].append(dict(cost_id="PREPAID-COST", source_ids=["S2"], status="excluded",
            allowed_cents=0, previously_paid_cents=20000, reason="Already settled through original obligation"))
        self.validate(data)
        self.assertEqual(claim["allowed_cents"], 1000)

    def test_nonfinite_values_cannot_hide_in_additional_provenance(self):
        for value in (float("nan"), float("inf")):
            data = deepcopy(self.first)
            data["provenance"] = {"bad_value": value}
            with self.subTest(value=value), self.assertRaisesRegex(SnapshotError, "finite"):
                self.validate(data)

    def test_csv_exact_nine_columns_unknown_blank_zero_known_and_unicode_quoted(self):
        data = deepcopy(self.first)
        known = data["claims"][0]
        known.update(reason='Évidence, "quoted"\nsecond line', paid_cents=0, balance_cents=1000)
        unknown = deepcopy(known)
        unknown.update(claim_id="CLAIM-B", allowed_cents=None, balance_cents=None, next_owner=None)
        data["claims"].append(unknown)
        data["travel_cancellations"] = [self.process()]
        rendered = claims_csv(data)
        rows = list(csv.DictReader(io.StringIO(rendered)))
        self.assertEqual(rendered.splitlines()[0], ",".join(CSV_COLUMNS))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["paid_cents"], "0")
        self.assertEqual(rows[0]["reason"], known["reason"])
        self.assertEqual((rows[1]["allowed_cents"], rows[1]["balance_cents"], rows[1]["next_owner"]), ("", "", ""))
        self.assertNotIn("TRIP-NO-CLAIM", rendered)
        self.assertEqual(rendered, claims_csv(data))

    def test_csv_does_not_silently_select_a_duplicate_current_claim(self):
        bad = deepcopy(self.first)
        bad["claims"].append(deepcopy(bad["claims"][0]))
        with self.assertRaisesRegex(SnapshotError, "Duplicate"):
            claims_csv(bad)


if __name__ == "__main__":
    unittest.main()
