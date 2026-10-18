"""Compare actual Entire payloads to genuine local rollouts; never edit either."""
from pathlib import Path
from hashlib import sha256
import copy
import json
import subprocess

REF = 'refs/entire/checkpoints/EX/01M56WJEYZETEBYWDQBM56MREX'
OUT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args])


def stored(path):
    return git('show', REF + ':' + path)


def portable(row):
    """Pinned Entire sanitizer removes nonportable encrypted history fragments."""
    row = copy.deepcopy(row)
    payload = row.get('payload', {})
    if row.get('type') == 'response_item' and payload.get('type') in {'reasoning', 'compaction', 'compaction_summary'}:
        payload.pop('encrypted_content', None)
    if row.get('type') == 'compacted' and isinstance(payload.get('replacement_history'), list):
        history = []
        for item in payload['replacement_history']:
            if isinstance(item, dict) and item.get('type') in {'compaction', 'compaction_summary'}:
                continue
            if isinstance(item, dict) and item.get('type') == 'reasoning':
                item.pop('encrypted_content', None)
            history.append(item)
        payload['replacement_history'] = history
    return row


def compatible(original, capture, redactions, location=''):
    if original == capture:
        return True
    # The supported attachment also applies Entire's own redactor. We record
    # where stored strings carry its explicit marker, never restore those bytes.
    if isinstance(capture, str) and 'REDACTED' in capture:
        redactions.append(location)
        return True
    if isinstance(original, dict) and isinstance(capture, dict) and original.keys() == capture.keys():
        return all(compatible(original[key], capture[key], redactions, location + '.' + key) for key in original)
    if isinstance(original, list) and isinstance(capture, list) and len(original) == len(capture):
        return all(compatible(a, b, redactions, location + '.' + str(n)) for n, (a, b) in enumerate(zip(original, capture)))
    return False


investigation = json.loads((OUT / 'entire-investigation.json').read_text())
entries = []
tree = set(git('ls-tree', '-r', '--name-only', REF).decode().splitlines())
for task in investigation['tasks']:
    identity = task['agent_id']
    capture_path = f'tasks/{identity}/agent-{identity}.jsonl'
    if capture_path in tree:
        entries.append((identity, Path(task['genuine_local_rollout']['path']), capture_path, 'normal checkpoint materialization'))
current = [('01a14d8e-e097-7681-9f82-470d34741668', '01-49-31'),
           ('01a14d8f-0113-77b1-aa66-9a39e03f183a', '01-49-40'),
           ('01a14d8f-18b9-7c32-9ac7-7a774b0940a6', '01-49-46')]
for n, (identity, time) in enumerate(current, 1):
    metadata = json.loads(stored(f'{n}/metadata.json'))
    assert metadata['session_id'] == identity
    entries.append((identity, Path(f'/Users/user/.codex/sessions/2026/10/18/rollout-2026-10-18T{time}-{identity}.jsonl'), f'{n}/full.jsonl', 'supported Entire session attach'))
assert len(entries) == 7
checks = []
for identity, native_path, capture_path, method in entries:
    raw, capture = native_path.read_bytes(), stored(capture_path)
    original, saved = ([json.loads(line) for line in data.splitlines()] for data in (raw, capture))
    assert len(original) == len(saved), (identity, len(original), len(saved))
    redactions = []
    assert all(compatible(portable(a), b, redactions, str(n)) for n, (a, b) in enumerate(zip(original, saved))), identity
    checks.append(dict(session_id=identity, method=method, path_in_checkpoint=capture_path,
                       native_bytes=len(raw), native_sha256=sha256(raw).hexdigest(),
                       stored_bytes=len(capture), stored_sha256=sha256(capture).hexdigest(),
                       records=len(saved), all_record_positions_present=True,
                       nonredacted_fields_match_original_after_portable_sanitization=True,
                       Entire_redacted_string_paths=redactions))
root = stored('0/full.jsonl')
records = [json.loads(line) for line in root.splitlines()]
assert any(r.get('payload', {}).get('role') == 'user' and 'latest complete interview export' in json.dumps(r) for r in records)
assert any(r.get('payload', {}).get('type') in {'custom_tool_call_output', 'function_call_output'} and 'Ran 224 tests' in json.dumps(r) for r in records)
metadata = json.loads(stored('metadata.json'))
result = dict(implementation_commit='c9055f51e28d15290aeafc4dcf61d691d1d0bac0',
              checkpoint_id='01M56WJEYZETEBYWDQBM56MREX', checkpoint_ref=REF,
              checkpoint_object=git('rev-parse', REF).decode().strip(),
              root_capture_bytes=len(root), root_capture_sha256=sha256(root).hexdigest(),
              actual_user_request_and_successful_test_output_present=True,
              previously_missing_child_payloads_recovered=4, current_child_payloads_attached=3,
              children=checks, transcript_recovery_verified=True,
              subagent_tokens_complete=metadata['token_usage'].get('subagent_tokens_complete'),
              remaining_limitation='Exact aggregate/window accounting stays false; three old task placeholders remain but their genuine child sessions are attached as sessions1-3 on the same checkpoint. Stale active-session metadata is not treated as proof that the verified payloads are absent.',
              storage_transformations='Supported Entire storage sanitizes session-bound encrypted history and redacts marked strings. Raw byte equality is not claimed. Original local files are untouched; all record positions and nonredacted fields were compared.',
              initial_checker_correction='A strict raw-record equality check first failed; pinned sanitizer inspection and actual REDACTED fields explained the transformations. Verification then checked documented portable records and nonredacted content, without modifying captures.',
              hook_approvals_settings_flags_or_historical_refs_manually_rewritten=False,
              user_capture_action_required=False)
(OUT / 'capture-recovery.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key:value for key,value in result.items() if key != 'children'}, indent=2))
