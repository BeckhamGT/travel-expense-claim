"""Operational regressions using explicitly supplemental offline corpus copies."""
from pathlib import Path
from hashlib import sha256
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
GRADED = REPO / 'artifacts/runs/submission-20261017T154939Z'


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='travel-continuation-supplemental-', dir='/private/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.prior = self.base / GRADED.name
        shutil.copytree(GRADED, self.prior)
        self.run = self.new_run('supplemental-staged', self.prior)

    def new_run(self, identity, prior):
        root = self.base / identity
        shutil.copytree(GRADED / 'retained', root / 'retained')
        data = json.loads((GRADED / 'sources.json').read_text())
        data.update(run_id=identity,
                    prior_run={'run_id': json.loads((prior / 'sources.json').read_text())['run_id'],
                               'path': '../' + prior.name + '/sources.json',
                               'sha256': sha256((prior / 'sources.json').read_bytes()).hexdigest()},
                    change_reason='Supplemental offline integration fixture, not a fresh business collection',
                    acquisition_mode='supplemental-offline-fixture')
        (root / 'sources.json').write_text(json.dumps(data, indent=2) + '\n')
        return root

    def cli(self, mode, *extra, root=None, success=True):
        root = root or self.run
        args = [sys.executable, '-m', 'travel_expense_claim.workflow', mode,
                '--sources', str(root / 'sources.json'), '--schema', str(REPO / 'snapshot.schema.json'),
                '--completion-accepted', *map(str, extra)]
        result = subprocess.run(args, cwd=REPO, env={**os.environ, 'PYTHONPATH': str(REPO / 'src')},
                                text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def start(self, through=1):
        self.cli('seal', '--batch', 1)
        for number in range(2, through + 1):
            self.cli('continue', '--batch', number)

    def state(self, root=None):
        return {str(p.relative_to(root or self.run)): (sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in (root or self.run).rglob('*') if p.is_file()}

    def test_one_batch_seals_then_stops_with_owned_waits(self):
        result = self.cli('seal', '--batch', 1)
        self.assertEqual(result['consumed_batch'], 1)
        self.assertEqual(result['next_batch'], 2)
        self.assertEqual([p.name for p in (self.run / 'batches').glob('*.json')], ['1.json'])
        self.assertTrue((self.run / 'stages/1/repair-queue.json').exists())
        self.assertFalse((self.run / 'stages/2').exists())
        batch = json.loads((self.run / 'batches/1.json').read_text())
        claims = {c['claim_id']: c for c in batch['claims']}
        self.assertEqual(claims['C01']['paid_cents'], 0)
        self.assertNotEqual(claims['C01']['status'], 'closed-reimbursed')
        self.assertIsNone(claims['C08']['allowed_cents'])
        status = self.cli('status')
        self.assertEqual(status['current_batch'], 1)
        self.assertEqual(status['next_batch'], 2)
        self.assertIn('EMP-01', status['open_work_by_owner'])

    def test_continuation_requires_validated_immediate_prior_and_cannot_skip(self):
        self.cli('continue', '--batch', 2, success=False)
        self.assertFalse((self.run / 'batches').exists())
        self.start()
        before = self.state()
        self.cli('continue', '--batch', 3, success=False)
        self.assertEqual(self.state(), before)
        self.cli('continue', '--batch', 2)
        first = json.loads((self.run / 'batches/1.json').read_text())
        second = json.loads((self.run / 'batches/2.json').read_text())
        self.assertEqual({r['request_id'] for r in first['requests']}, {r['request_id'] for r in second['requests']})
        self.assertEqual(next(c for c in second['claims'] if c['claim_id'] == 'C01')['paid_cents'], 10000)

    def test_identical_continuation_replay_preserves_bytes_and_mtimes(self):
        self.start(2)
        before = self.state()
        result = self.cli('continue', '--batch', 2)
        self.assertTrue(result['replay'])
        self.cli('verify')
        self.assertEqual(self.state(), before)

    def test_native_c20_partial_facts_resume_separately_across_batches(self):
        self.start(2)
        queue = json.loads((self.run / 'repair-queue.json').read_text())
        partial = next(i for i in queue['items'] if i['subject_id'] == 'C20' and i['code'] == 'overpayment')
        final = next(i for i in queue['items'] if i['subject_id'] == 'C20' and i['code'] == 'finance_resolution')
        before_two = self.state()
        self.cli('continue', '--batch', 3, '--task', partial['item_id'])
        queue = {i['item_id']: i for i in json.loads((self.run / 'repair-queue.json').read_text())['items']}
        self.assertEqual(queue[partial['item_id']]['status'], 'resolved')
        self.assertEqual(queue[final['item_id']]['status'], 'open')
        claim = next(c for c in json.loads((self.run / 'batches/3.json').read_text())['claims'] if c['claim_id'] == 'C20')
        self.assertEqual((claim['paid_cents'], claim['balance_cents'], claim['status']), (10000, 0, 'held'))
        self.cli('continue', '--batch', 4, '--task', final['item_id'])
        claim = next(c for c in json.loads((self.run / 'batches/4.json').read_text())['claims'] if c['claim_id'] == 'C20')
        self.assertEqual((claim['paid_cents'], claim['status']), (10000, 'closed-reimbursed'))
        for name, saved in before_two.items():
            if name.startswith(('batches/', 'stages/')):
                self.assertEqual(self.state()[name], saved)
        self.cli('verify')

    def test_missing_or_corrupt_predecessor_never_repairs_same_run(self):
        self.start()
        path = self.run / 'batches/1.json'
        raw = path.read_bytes()
        path.unlink()
        damaged = self.state()
        self.cli('continue', '--batch', 2, success=False)
        self.cli('seal', '--batch', 1, success=False)
        self.assertEqual(self.state(), damaged)
        path.write_bytes(raw + b' ')
        damaged = self.state()
        self.cli('verify', success=False)
        self.cli('continue', '--batch', 2, success=False)
        self.assertEqual(self.state(), damaged)

    def test_explicit_recovery_requires_distinct_linked_run_and_preserves_damage(self):
        self.start(2)
        (self.run / 'batches/1.json').write_text('damaged supplemental copy')
        before = self.state()
        self.cli('recover', '--through-batch', 2, '--from-run', self.run / 'sources.json', success=False)
        recovery = self.new_run('supplemental-recovery', self.run)
        result = self.cli('recover', '--through-batch', 2, '--from-run', self.run / 'sources.json', root=recovery)
        self.assertEqual(result['current_batch'], 2)
        self.assertTrue((recovery / 'stages/2/operation.json').exists())
        self.assertEqual(self.state(), before)
        operation = json.loads((recovery / 'stages/2/operation.json').read_text())
        self.assertEqual(operation['operation'], 'recover')
        self.assertEqual(operation['recovery_from']['run_id'], 'supplemental-staged')
        self.assertIn('observed_at', operation)
        self.cli('verify', root=recovery)

    def test_projection_corruption_or_orphaned_snapshot_requires_new_run_recovery(self):
        self.start()
        (self.run / 'claims.csv').write_text('corrupt projection')
        before = self.state()
        self.cli('continue', '--batch', 2, success=False)
        self.assertEqual(self.state(), before)

    def test_legacy_sealed_run_is_never_silently_adopted_or_rebuilt(self):
        before = self.state(self.prior)
        self.cli('seal', '--batch', 1, root=self.prior, success=False)
        self.assertEqual(self.state(self.prior), before)

    def test_task_ids_must_exist_in_prior_operational_queue(self):
        self.start()
        before = self.state()
        self.cli('continue', '--batch', 2, '--task', 'RQ-NOT-SUPPLIED', success=False)
        self.assertEqual(self.state(), before)

    def test_prior_manifest_binding_is_rechecked_before_continuation(self):
        self.start()
        prior = self.prior / 'sources.json'
        prior.write_bytes(prior.read_bytes() + b' ')
        before = self.state()
        self.cli('continue', '--batch', 2, success=False)
        self.assertEqual(self.state(), before)

    def test_orphaned_snapshot_after_interruption_is_not_silently_adopted(self):
        self.start()
        shutil.copy2(GRADED / 'batches/2.json', self.run / 'batches/2.json')
        before = self.state()
        self.cli('continue', '--batch', 2, success=False)
        self.assertEqual(self.state(), before)

    def test_stage_directory_symlink_cannot_write_outside_run(self):
        external = self.base / 'external-history'
        external.mkdir()
        (self.run / 'stages').symlink_to(external, target_is_directory=True)
        self.cli('seal', '--batch', 1, success=False)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse((self.run / 'batches').exists())


if __name__ == '__main__':
    unittest.main()
