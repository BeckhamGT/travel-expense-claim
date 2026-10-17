from copy import deepcopy
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from travel_expense_claim.snapshots import CSV_COLUMNS, SnapshotError, claims_csv, validate_snapshot, write_snapshot
from travel_expense_claim.verify_independence import Sources
from travel_expense_claim.workflow import build_run, render_report


MANIFEST = Path(__file__).resolve().parents[1] / "artifacts/runs/submission-20261017T154939Z/sources.json"


class WorkflowHandoffTests(unittest.TestCase):
    def test_full_source_chain_is_immutable_and_csv_agrees(self):
        # This offline temporary copy exercises the real corpus without sealing
        # production batches or asserting the learner's pending choice 3.
        original_manifest_hash = sha256(MANIFEST.read_bytes()).hexdigest()
        schema = MANIFEST.parents[3] / "snapshot.schema.json"
        with tempfile.TemporaryDirectory(prefix="travel-full-source-offline-", dir="/private/tmp") as temporary:
            run = Path(temporary) / MANIFEST.parent.name
            shutil.copytree(MANIFEST.parent / "retained", run / "retained")
            manifest = run / "sources.json"
            shutil.copy2(MANIFEST, manifest)
            source_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(source_data["files"]), 21)
            retained_hashes = {}
            for entry in source_data["files"]:
                self.assertEqual(entry["status"], "read")
                retained = run / entry["path"]
                retained_hashes[retained] = sha256(retained.read_bytes()).hexdigest()
                self.assertEqual(retained_hashes[retained], entry["sha256"])
            self.assertEqual(sha256(manifest.read_bytes()).hexdigest(), original_manifest_hash)

            result = build_run(manifest, completion_accepted=False)
            self.assertEqual([len(snapshot["claims"]) for snapshot in result["snapshots"]], [120, 120, 121, 121])
            self.assertEqual([len(snapshot["admitted_event_ids"]) for snapshot in result["snapshots"]], [100, 200, 210, 219])
            previous, saved = None, {}
            for snapshot in result["snapshots"]:
                self.assertFalse(snapshot["completion_choice_adopted"])
                self.assertFalse(any(claim["financial_completion_accepted"] or claim["status"].startswith("closed-") for claim in snapshot["claims"]))
                path = run / "batches" / (snapshot["batch_id"] + ".json")
                write_snapshot(path, snapshot, schema, manifest, previous)
                validate_snapshot(snapshot, schema, manifest, previous, snapshot_path=path)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot)
                self.assertEqual((path.parent / snapshot["source_binding"]["path"]).resolve(), manifest)
                self.assertEqual(snapshot["source_binding"]["sha256"], original_manifest_hash)
                if previous is None:
                    self.assertIsNone(snapshot["predecessor"])
                else:
                    self.assertEqual((path.parent / snapshot["predecessor"]["path"]).resolve(), previous)
                    self.assertEqual(snapshot["predecessor"]["sha256"], sha256(previous.read_bytes()).hexdigest())
                issue_ids = {item["record_id"] for item in snapshot["issues"]}
                cancellation_events = set()
                for process in snapshot["travel_cancellations"]:
                    self.assertLessEqual(set(process["issue_record_ids"]), issue_ids)
                    cancellation_events.update(process["admitted_cancellation_event_ids"])
                self.assertFalse(set(snapshot["admitted_event_ids"]) & cancellation_events)
                saved[path] = (path.read_bytes(), path.stat().st_mtime_ns)
                previous = path

            previous = None
            for snapshot in result["snapshots"]:
                path = run / "batches" / (snapshot["batch_id"] + ".json")
                write_snapshot(path, snapshot, schema, manifest, previous)
                self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), saved[path])
                previous = path
            distinct = deepcopy(result["snapshots"][-1])
            distinct["claims"][0]["reason"] += "; isolated changed replay must be refused"
            with self.assertRaisesRegex(SnapshotError, "Distinct sealed"):
                write_snapshot(previous, distinct, schema, manifest, run / "batches" / "3.json")
            self.assertEqual((previous.read_bytes(), previous.stat().st_mtime_ns), saved[previous])

            final = result["snapshots"][-1]
            csv_rows = list(csv.DictReader(io.StringIO(claims_csv(final))))
            self.assertEqual(len(csv_rows), 121)
            self.assertEqual(tuple(csv_rows[0]), CSV_COLUMNS)
            self.assertEqual({row["claim_id"] for row in csv_rows}, {claim["claim_id"] for claim in final["claims"]})
            self.assertNotIn("C122", {row["claim_id"] for row in csv_rows})
            claims = {claim["claim_id"]: claim for claim in final["claims"]}
            unknown = {identity for identity, claim in claims.items() if claim["allowed_cents"] is None}
            self.assertEqual(len(unknown), 6)
            self.assertEqual({row["claim_id"] for row in csv_rows if row["allowed_cents"] == ""}, unknown)
            for row in csv_rows:
                claim = claims[row["claim_id"]]
                self.assertEqual(len(row), 9)
                for column in CSV_COLUMNS:
                    self.assertEqual(row[column], "" if claim[column] is None else str(claim[column]))
            for retained, original_hash in retained_hashes.items():
                self.assertEqual(sha256(retained.read_bytes()).hexdigest(), original_hash)
            self.assertEqual(sha256(manifest.read_bytes()).hexdigest(), original_manifest_hash)
        self.assertEqual(sha256(MANIFEST.read_bytes()).hexdigest(), original_manifest_hash)

    def test_report_uses_exact_cancellation_target_and_traceable_queue_changes(self):
        result = build_run(MANIFEST)
        report = render_report(result, MANIFEST, preview=True)
        self.assertIn("| TC122 | trip T122 / 1 |", report)
        self.assertNotIn("trip P122", report)
        self.assertIn("| TC121 | permit P121 / 1 |", report)
        self.assertIn("| 1 | C21 / 1 |", report)
        claims = {row["claim_id"]: row for row in result["snapshots"][-1]["claims"]}
        self.assertEqual(claims["C21"]["next_owner"], "LEAD-01")
        self.assertEqual(claims["C119"]["next_owner"], "DIR-01")
        self.assertEqual(claims["C18"]["next_owner"], "FIN-01")
        processes = {row['cancellation_id']:row for row in result['snapshots'][-1]['travel_cancellations']}
        for identity in ['TC019','TC121']:
            self.assertEqual(processes[identity]['next_owner'], 'Learner')
            self.assertTrue(processes[identity]['source_financial_prerequisites_observed'])
        self.assertEqual(processes['TC018']['next_owner'], 'FIN-01')

    def test_confirmed_refund_alone_does_not_resolve_the_earlier_overpayment(self):
        original = Sources.table
        def changed(sources, name):
            rows = deepcopy(original(sources, name))
            if name == "Finance activity":
                rows = [row for row in rows if row["Activity reference"] != "F-C20-3"]
            return rows
        with patch.object(Sources, "table", changed):
            result = build_run(MANIFEST, completion_accepted=True)
        final = next(claim for claim in result["snapshots"][-1]["claims"] if claim["claim_id"] == "C20")
        self.assertEqual(final["paid_cents"], 10000)
        self.assertEqual(final["balance_cents"], 0)
        self.assertTrue(final["finance_resolution_required"])
        self.assertEqual(final["status"], "held")
        self.assertFalse(final["financial_completion_accepted"])


if __name__ == "__main__":
    unittest.main()
