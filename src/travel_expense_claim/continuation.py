"""One-batch operational continuation with immutable stage evidence.

Business reductions stay in workflow.build_run. This module binds consumption,
waits, current projections and explicit new-run recovery to validated bytes.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from .snapshots import claims_csv, validate_snapshot, write_snapshot
from .verify_independence import Sources, SourceError
from .workflow import build_run, encoded, immutable, render_report


OUTPUTS = ('claims.csv', 'repair-queue.json', 'report.md', 'summary.json')
STATE_VERSION = 'travel-claim-continuation/1'


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _implementation():
    digest = sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def _error(detail):
    raise SourceError(detail + '; preserve this run and use explicit recover with a new linked source run')


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        _error('Missing or corrupt operational state ' + str(path) + ': ' + str(error))


def _replace(path, content):
    """Publish a current projection/cursor; sealed stages never use replacement."""
    path = Path(path)
    if path.is_symlink():
        _error('Unsafe current projection symlink: ' + str(path))
    data = content if isinstance(content, bytes) else content.encode('utf-8')
    descriptor, temporary = tempfile.mkstemp(prefix='.current-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _linked_prior(sources, required=False):
    link = sources.data.get('prior_run')
    if link is None and not required:
        return None
    if not isinstance(link, dict) or not all(isinstance(link.get(k), str) and link[k] for k in ('run_id', 'path', 'sha256')):
        _error('A linked run needs prior_run run_id/path/sha256')
    prior = (sources.base / link['path']).resolve()
    if (Path(link['path']).is_absolute() or not prior.is_relative_to(sources.base.parent)
            or prior == sources.path or link['run_id'] == sources.data['run_id']):
        _error('Recovery/prior link must identify a distinct retained sibling run')
    data = _read(prior)
    if data.get('run_id') != link['run_id'] or _hash(prior) != link['sha256']:
        _error('Prior source manifest link/hash does not agree')
    if not isinstance(sources.data.get('change_reason'), str) or not sources.data['change_reason'].strip():
        _error('A new linked run needs an explicit change_reason')
    return dict(link, resolved_path=str(prior))


def _empty(root):
    if (root / 'run-state.json').exists() or any((root / name).exists() for name in OUTPUTS):
        _error('Run already has operational state or projections')
    for directory in ('batches', 'stages'):
        if (root / directory).exists() and any((root / directory).iterdir()):
            _error('Unpaired sealed state already exists in ' + directory)


def _contained_layout(root):
    """Keep new stage/projection publications inside their identified run."""
    paths = [root / name for name in ('batches', 'stages', 'run-state.json', *OUTPUTS)]
    stages = root / 'stages'
    if stages.is_dir() and not stages.is_symlink():
        paths.extend(stages.iterdir())
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            _error('Operational paths must be real contained paths: ' + str(path))


def _state(root, sources):
    cursor = _read(root / 'run-state.json')
    if (cursor.get('schema_version') != STATE_VERSION or cursor.get('run_id') != sources.data['run_id']
            or cursor.get('source_sha256') != _hash(sources.path)
            or cursor.get('implementation_sha256') != _implementation()
            or cursor.get('completion_choice_adopted') is not True):
        _error('Run source/implementation/adoption binding differs')
    number = cursor.get('current_batch')
    if type(number) is not int or not 1 <= number <= 4:
        _error('Invalid consumed-batch cursor')
    expected = {str(n) for n in range(1, number + 1)}
    if set(cursor.get('stages', {})) != expected:
        _error('Operational stage chain is incomplete')
    if {p.name for p in (root / 'batches').glob('*.json')} != {n + '.json' for n in expected}:
        _error('Missing or unpaired sealed snapshot')
    if not (root / 'stages').is_dir() or {p.name for p in (root / 'stages').iterdir()} != expected:
        _error('Missing or unpaired stage view')
    for n in expected:
        binding = cursor['stages'][n]
        files = {'snapshot': root / 'batches' / (n + '.json'),
                 **{name: root / 'stages' / n / name for name in (*OUTPUTS, 'operation.json')}}
        if set(binding) != set(files):
            _error('Incomplete stage file bindings')
        for key, path in files.items():
            if not path.is_file() or path.is_symlink() or _hash(path) != binding[key]:
                _error('Missing, corrupt or distinct stage file: ' + str(path))
    for name in OUTPUTS:
        path = root / name
        if not path.is_file() or path.is_symlink() or _hash(path) != cursor['stages'][str(number)][name]:
            _error('Current projection differs from its sealed stage: ' + name)
    return cursor


def _outputs(result, manifest):
    return dict(zip(OUTPUTS, (claims_csv(result['snapshots'][-1]).encode('utf-8'),
                             encoded(result['queue']), render_report(result, manifest).encode('utf-8'),
                             encoded(result['summaries']))))


def _verify(root, sources, schema, cursor):
    """Recheck every consumed prefix, never a later unconsumed arrival."""
    previous = None
    for number in range(1, cursor['current_batch'] + 1):
        result = build_run(sources.path, True, through_batch=number)
        snapshot = result['snapshots'][-1]
        path = root / 'batches' / f'{number}.json'
        if path.read_bytes() != encoded(snapshot):
            _error('Sealed batch differs on retained-source replay: ' + str(number))
        validate_snapshot(snapshot, schema, sources.path, previous, snapshot_path=path)
        for name, data in _outputs(result, sources.path).items():
            if (root / 'stages' / str(number) / name).read_bytes() != data:
                _error('Sealed stage output differs on replay: ' + str(number) + '/' + name)
        operation = _read(root / 'stages' / str(number) / 'operation.json')
        if (operation.get('batch_id') != number or operation.get('run_id') != sources.data['run_id']
                or operation.get('source_sha256') != _hash(sources.path)
                or operation.get('implementation_sha256') != _implementation()
                or operation.get('operation') not in {'seal', 'continue', 'recover'}):
            _error('Stage operation binding differs')
        if number > 1:
            if operation.get('predecessor_sha256') != _hash(previous):
                _error('Operation does not bind its actual consumed predecessor')
        previous = path
    return result


def _task_changes(before, after, identities):
    prior = {item['item_id']: item for item in before['items']}
    latest = {item['item_id']: item for item in after['items']}
    if len(set(identities)) != len(identities) or any(identity not in prior for identity in identities):
        raise SourceError('A resumed task must identify a distinct item in the previous operational queue')
    return [dict(item_id=identity, subject_id=prior[identity]['subject_id'], revision=prior[identity]['revision'],
                 from_status=prior[identity]['status'], to_status=latest[identity]['status'],
                 owner=latest[identity]['owner'], source_refs=latest[identity]['source_refs'],
                 resolution_scope='This fact only; other facts, approval and Finance conditions remain independent')
            for identity in identities]


def _append(root, sources, schema, number, cursor, *, tasks=(), recovery=None):
    result = build_run(sources.path, True, through_batch=number)
    prior_queue = _read(root / 'repair-queue.json') if cursor else {'items': []}
    changes = _task_changes(prior_queue, result['queue'], tasks)
    operation = dict(operation='recover' if recovery else 'seal' if number == 1 else 'continue',
                     run_id=sources.data['run_id'], batch_id=number,
                     observed_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                     source_sha256=_hash(sources.path), implementation_sha256=_implementation(),
                     predecessor_sha256=None if number == 1 else _hash(root / 'batches' / f'{number - 1}.json'),
                     resumed_tasks=changes, observation='Actual current execution; source business times are retained separately')
    if recovery:
        operation.update(recovery_from=recovery, change_reason=sources.data['change_reason'],
                         reconstruction='Complete retained source/event history; historical execution times are not invented')
    # Publish immutable business state and stage views before advancing the cursor.
    path = root / 'batches' / f'{number}.json'
    write_snapshot(path, result['snapshots'][-1], schema, sources.path,
                   None if number == 1 else root / 'batches' / f'{number - 1}.json')
    outputs = _outputs(result, sources.path)
    stage = root / 'stages' / str(number)
    for name, content in outputs.items():
        immutable(stage / name, content)
    immutable(stage / 'operation.json', encoded(operation))
    binding = {'snapshot': _hash(path), **{name: _hash(stage / name) for name in (*OUTPUTS, 'operation.json')}}
    cursor = cursor or dict(schema_version=STATE_VERSION, run_id=sources.data['run_id'],
                            source_sha256=_hash(sources.path), implementation_sha256=_implementation(),
                            completion_choice_adopted=True, stages={})
    cursor['stages'][str(number)] = binding
    cursor['current_batch'] = number
    for name, data in outputs.items():
        _replace(root / name, data)
    # Any interrupted publication is detected on the next invocation and owned
    # by explicit recovery into a new linked run, never silently repaired here.
    _replace(root / 'run-state.json', encoded(cursor))
    return cursor, changes


def _status(root, cursor, tasks=()):
    queue = _read(root / 'repair-queue.json')
    items = {item['item_id']: item for item in queue['items']}
    if any(identity not in items for identity in tasks):
        raise SourceError('Unknown operational repair item')
    number = cursor['current_batch']
    return dict(run_id=cursor['run_id'], current_batch=number, next_batch=number + 1 if number < 4 else None,
                state='awaiting-explicit-continuation' if number < 4 else 'all-batches-consumed-owned-work-remains',
                open_work_by_owner=dict(Counter(item['owner'] for item in items.values() if item['status'] == 'open')),
                selected_tasks=[items[identity] for identity in tasks])


def operate(args):
    sources = Sources(args.sources)
    root = sources.base
    _contained_layout(root)
    _linked_prior(sources, required=args.mode == 'recover')
    if args.mode in {'status', 'verify'}:
        if args.through_batch is not None or args.from_run is not None or (args.mode == 'status' and args.batch is not None):
            raise SourceError('Status/verify inspect consumed state; they do not advance or recover a run')
        cursor = _state(root, sources)
        _verify(root, sources, args.schema, cursor)
        if args.batch is not None and args.batch > cursor['current_batch']:
            raise SourceError('Cannot verify an unconsumed batch')
        return dict(mode=args.mode, verified_batches=list(range(1, cursor['current_batch'] + 1)),
                    **_status(root, cursor, args.task))
    if args.mode == 'recover':
        if args.from_run is None or args.through_batch is None or args.batch is not None or args.task:
            raise SourceError('Recovery requires --from-run and --through-batch in a new linked run')
        recovery = _linked_prior(sources, required=True)
        if Path(recovery['resolved_path']) != args.from_run.resolve():
            raise SourceError('--from-run does not match the new manifest prior_run binding')
        _empty(root)
        cursor = None
        for number in range(1, args.through_batch + 1):
            cursor, _ = _append(root, sources, args.schema, number, cursor, recovery=recovery)
        return dict(mode='recover', **_status(root, cursor))
    if args.batch is None or args.through_batch is not None or args.from_run is not None:
        raise SourceError('Use seal --batch 1 or continue --batch <next>; recovery is an explicit separate mode')
    if args.mode == 'seal' and args.batch != 1:
        raise SourceError('Seal starts batch 1; continue consumes the next supplied batch')
    if (root / 'run-state.json').exists():
        cursor = _state(root, sources)
        _verify(root, sources, args.schema, cursor)
    else:
        if args.mode != 'seal' or args.batch != 1:
            _error('No validated prior consumption state')
        _empty(root)
        _linked_prior(sources)
        cursor = None
    number = cursor['current_batch'] if cursor else 0
    if args.batch <= number:
        before = {'items': []} if args.batch == 1 else _read(root / 'stages' / str(args.batch - 1) / 'repair-queue.json')
        after = _read(root / 'stages' / str(args.batch) / 'repair-queue.json')
        changes = _task_changes(before, after, args.task)
        return dict(mode=args.mode, consumed_batch=args.batch, replay=True, resumed_tasks=changes, **_status(root, cursor))
    if args.batch != number + 1:
        raise SourceError('Consume the immediately next batch; skipped or future arrivals are not available')
    cursor, changes = _append(root, sources, args.schema, args.batch, cursor, tasks=args.task)
    return dict(mode=args.mode, consumed_batch=args.batch, replay=False, resumed_tasks=changes, **_status(root, cursor))
