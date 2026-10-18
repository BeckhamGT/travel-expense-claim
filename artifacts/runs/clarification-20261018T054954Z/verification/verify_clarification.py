"""Independent preservation and before/after checks; no production imports."""
from hashlib import sha256
from pathlib import Path
import json
import subprocess

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parent.parent
PREVIOUS_COMMIT = '917838bf6d0e1534b53da193b73883a8de4ce7e5'
PREVIOUS = REPO / 'artifacts/runs/revision-20261018T003113Z'
LATEST_NAME = 'project-d-travel-expense-claim-20261018-0547.md'
LATEST_HASH = '3c2958030d76bd4edf0ce76a5b96f93de61fe208e420766d7ad1e8b9d2d55aa9'


def read(path):
    return json.loads(path.read_text())


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


canonical = REPO / 'interviews' / LATEST_NAME
assert [p.name for p in (REPO / 'interviews').glob('*.md')] == [LATEST_NAME]
assert sha256(canonical.read_bytes()).hexdigest() == LATEST_HASH
assert canonical.read_bytes() == (RUN / 'retained/interview-source.txt').read_bytes()
supplied = Path('/Users/user/Downloads') / LATEST_NAME
if supplied.is_file():
    assert canonical.read_bytes() == supplied.read_bytes()
old_export = git('show', PREVIOUS_COMMIT + ':interviews/project-d-travel-expense-claim-20261017-0334.md')
assert sha256(old_export).hexdigest() == '8099acf7f137edf8521c50b3d80c1dd76fe6a4dd175356fa7b1648199b1606e2'
historical = git('ls-tree', '-r', '--name-only', PREVIOUS_COMMIT, '--', 'artifacts').decode().splitlines()
assert all(git('show', PREVIOUS_COMMIT + ':' + path) == (REPO / path).read_bytes() for path in historical)
assert git('show', PREVIOUS_COMMIT + ':snapshot.schema.json') == (REPO / 'snapshot.schema.json').read_bytes()
for path in ('monetary.py', 'finance.py', 'authority.py', 'eligibility.py', 'repair_queue.py', 'continuation.py'):
    relative = 'src/travel_expense_claim/' + path
    assert git('show', PREVIOUS_COMMIT + ':' + relative) == (REPO / relative).read_bytes()
manifest = read(RUN / 'sources.json')
assert manifest['prior_run']['sha256'] == sha256((PREVIOUS / 'sources.json').read_bytes()).hexdigest()
assert len(manifest['files']) == 21 and len(manifest['documents']) == 1
for entry in manifest['files'] + manifest['documents']:
    assert sha256((RUN / entry['path']).read_bytes()).hexdigest() == entry['sha256']
state = read(RUN / 'run-state.json')
implementation = sha256()
for path in sorted((REPO / 'src/travel_expense_claim').glob('*.py')):
    implementation.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
assert implementation.hexdigest() == state['implementation_sha256']
assert sha256((RUN / 'sources.json').read_bytes()).hexdigest() == state['source_sha256']
assert state['current_batch'] == 4

money_keys = ('allowed_cents', 'paid_cents', 'balance_cents', 'authorized_obligation_cents',
              'gross_paid_cents', 'refunded_cents', 'decision_ids', 'status',
              'finance_resolution_required', 'current_resolution_event_ids')
observations = []
for batch in range(1, 5):
    before, after = (read(root / f'batches/{batch}.json') for root in (PREVIOUS, RUN))
    for key in ('requests', 'finance_events', 'travel_cancellations', 'decisions', 'review_packets', 'admitted_event_ids'):
        assert before[key] == after[key], (batch, key)
    old = {c['claim_id']: c for c in before['claims']}
    current = {c['claim_id']: c for c in after['claims']}
    for identity, c in current.items():
        if identity == 'C117':
            continue
        assert all(c[key] == old[identity][key] for key in money_keys), (batch, identity)
    c = current['C117']
    assert [line['allowed_cents'] for line in c['lines']] == [0, 4000]
    assert (c['allowed_cents'], c['paid_cents'], c['balance_cents']) == (4000, 0, 4000)
    assert c['status'] == 'pending' and c['next_owner'] == 'ADMIN-01'
    assert set(c['current_review']['missing_roles']) == {'administration', 'budget_owner', 'supervisor'}
    assert c['decision_ids'] == [] and not c['financial_completion_accepted']
    assert not any(request['claim_id'] == 'C117' for request in after['requests'])
    assert 'INTERVIEW:line669' in c['lines'][0]['source_ids']
    for identity in ('C22', 'C23', 'C116'):
        assert current[identity]['allowed_cents'] is None and current[identity]['status'] == 'held'
        assert current[identity]['next_owner'] == 'Exercise operator'
    observations.append(dict(batch=batch, before_C117={key:old['C117'][key] for key in money_keys},
                             after_C117={key:c[key] for key in money_keys},
                             all_other_claim_money_status_and_authority_unchanged=True,
                             supplied_Finance_decisions_cancellations_unchanged=True))
old_queue, queue = (read(root / 'repair-queue.json') for root in (PREVIOUS, RUN))
approval_ids = lambda q: {i['item_id'] for i in q['items'] if i['subject_id'] == 'C117' and i['code'] == 'approval_reply'}
assert approval_ids(old_queue) == approval_ids(queue) and len(approval_ids(queue)) == 3
assert all(i['status'] == 'open' and not i['responses'] and not any(d['sent'] for d in i['requests'])
           for i in queue['items'] if i['subject_id'] == 'C117')
addressed = [dict(item_id=i['item_id'], historical_code=i['code'], historical_status=i['status'],
                  current_disposition='No longer applicable under the bound new-run category definition; prior sealed item is preserved',
                  new_evidence=['INTERVIEW:line669', 'POLICY:paragraph2'])
             for i in old_queue['items'] if i['subject_id'] == 'C117' and i['code'] in {'unknown_category', 'approval_requirement'}]
assert len(addressed) == 2
assert not {i['item_id'] for i in addressed} & {i['item_id'] for i in queue['items']}
report = (RUN / 'report.md').read_text()
assert '| C117 / 1 | T117 | pending | 4000 / 0 / 4000 | ADMIN-01 |' in report
assert 'INTERVIEW:line669' in report and 'Fresh complete-table discrepancy' in report
assert 'Ran 224 tests' in (RUN / 'verification/full-tests.log').read_text()
assert not read(RUN / 'verification/independent-source-results.json')['errors']
assert read(RUN / 'verification/replay-results.json')['all_bytes_and_exact_mtimes_unchanged']
result = dict(run_id=RUN.name, previous_commit=PREVIOUS_COMMIT,
              source_manifest_sha256=state['source_sha256'], implementation_sha256=implementation.hexdigest(),
              canonical_interview_sha256=LATEST_HASH, one_final_complete_export=True,
              original_export_preserved_in_Git=True, historical_artifact_files_preserved=len(historical),
              immutable_schema_and_existing_money_authority_reducers=True,
              observations=observations, prior_queue_facts_addressed=addressed,
              current_C117_approval_task_ids=sorted(approval_ids(queue)),
              source_numeric_definitions_still_missing=['GBP 2026-09-01', 'BE/EUR lodging', 'NL/USD lodging'],
              final_summary=read(RUN / 'summary.json')[-1], independent_source_mismatches=0,
              tests=224, replay_unchanged_files=69)
(RUN / 'verification/final-checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key:value for key,value in result.items() if key != 'observations'}, indent=2))
