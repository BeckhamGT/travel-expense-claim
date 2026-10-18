"""Read-only final pairing/preservation checks; writes only its verification JSON."""
from pathlib import Path
from hashlib import sha256
import json
import subprocess

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parent.parent
OUT = RUN / 'verification'
GRADED = 'd11fb0607cded870f51308226cdc2db686460c0a'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=REPO)


historical = git('ls-tree', '-r', '--name-only', GRADED, '--', 'artifacts', 'interviews').decode().splitlines()
preserved = {name: sha256(git('show', GRADED + ':' + name)).hexdigest() for name in historical}
assert len(preserved) == 79
assert all(digest(REPO / name) == value for name, value in preserved.items())
interview = REPO / 'interviews/project-d-travel-expense-claim-20261017-0334.md'
assert digest(interview) == '8099acf7f137edf8521c50b3d80c1dd76fe6a4dd175356fa7b1648199b1606e2'
supplied = Path('/Users/user/Downloads/project-d-travel-expense-claim-20261017-0334.md')
supplied_comparison = 'Original supplied path unavailable on this host; recorded SHA-256 still required'
if supplied.is_file():
    assert interview.read_bytes() == supplied.read_bytes()
    supplied_comparison = 'Byte-identical to the original user-supplied export on this host'
assert not git('diff', GRADED, '--', 'snapshot.schema.json')
manifest = read(RUN / 'sources.json')
prior = (RUN / manifest['prior_run']['path']).resolve()
assert digest(prior) == manifest['prior_run']['sha256']
assert all(digest(RUN / f['path']) == f['sha256'] and f['status'] == 'read' for f in manifest['files'])
state = read(RUN / 'run-state.json')
implementation = sha256()
for path in sorted((REPO / 'src/travel_expense_claim').glob('*.py')):
    implementation.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
assert state['implementation_sha256'] == implementation.hexdigest()
assert state['source_sha256'] == digest(RUN / 'sources.json')
assert state['current_batch'] == 4
operations = [read(RUN / f'stages/{b}/operation.json') for b in range(1, 5)]
assert [o['operation'] for o in operations] == ['seal', 'continue', 'continue', 'continue']
assert operations[2]['resumed_tasks'][0]['from_status'] == 'open'
assert operations[2]['resumed_tasks'][0]['to_status'] == 'resolved'
assert operations[3]['resumed_tasks'][0]['to_status'] == 'resolved'
assert [o['observed_at'] for o in operations] == sorted(o['observed_at'] for o in operations)
for name in ('claims.csv', 'repair-queue.json', 'report.md', 'summary.json'):
    assert (RUN / name).read_bytes() == (RUN / 'stages/4' / name).read_bytes()
old_queue = read(prior.parent / 'repair-queue.json')
new_queue = read(RUN / 'stages/1/repair-queue.json')
returns = {}
for identity in ('C09', 'C21'):
    old = next(i for i in old_queue['items'] if i['subject_id'] == identity and i['code'] == 'review_return')
    new = next(i for i in new_queue['items'] if i['subject_id'] == identity and i['code'] == 'review_return')
    returns[identity] = dict(item_id=new['item_id'], before_owner=old['owner'], after_owner=new['owner'],
                             returning_reviews=new['returning_reviews'], requested_facts=new['requested_facts'],
                             ownership_basis=new['ownership_basis'], source_refs=new['source_refs'])
assert returns['C09']['before_owner'] == 'LEAD-01' and returns['C09']['after_owner'] == 'EMP-01'
assert returns['C21']['before_owner'] == returns['C21']['after_owner'] == 'LEAD-01'
assert not read(OUT / 'independent-source-results.json')['errors']
focused = read(OUT / 'focused-tests.json')
assert all(r['exit_code'] == 0 for r in focused)
assert read(OUT / 'replay-results.json')['all_bytes_and_mtimes_unchanged']
result = dict(mode='Current uncommitted implementation/run pairing checked before final commit; final Git/Entire publication verified separately',
              graded_commit=GRADED, HEAD_observed=git('rev-parse', 'HEAD').decode().strip(),
              run_id=manifest['run_id'], source_sha256=digest(RUN / 'sources.json'),
              implementation_sha256=implementation.hexdigest(), original_interview_sha256=digest(interview),
              original_supplied_export_comparison=supplied_comparison,
              historical_79_files_unchanged=preserved, original_schema_unchanged=True,
              source_bindings_verified=len(manifest['files']), operations=operations,
              repair_ownership=returns, independent_source_errors=0, focused_tests=focused,
              output_hashes={name:digest(RUN / name) for name in ('claims.csv','repair-queue.json','report.md','summary.json','run-state.json')})
(OUT / 'final-checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('historical_79_files_unchanged','operations','focused_tests')}, indent=2))
