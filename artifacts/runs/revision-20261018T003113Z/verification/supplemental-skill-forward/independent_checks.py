"""Supplemental offline checks using retained native values, no implementation imports."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import json

base = Path(__file__).parent
context = json.loads((base / 'test-context.json').read_text())
run = Path(context['run'])

def table(name):
    rows = json.loads((run / 'retained' / name).read_text())['sheets'][0]['data'][0]['rowData']
    def value(cell):
        return next(iter(cell.get('effectiveValue', {}).values()), None)
    headers = [value(cell) for cell in rows[4]['values']]
    result = []
    for number, row in enumerate(rows[5:], 6):
        cells = [value(cell) for cell in row.get('values', [])]
        record = dict(zip(headers, cells + [None] * (len(headers) - len(cells))))
        record['_row'] = number
        result.append(record)
    return result

def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))

finance = table('native-tab-finance-activity.json')
people = {row['Employee ID']: row for row in table('native-tab-people.json')}
review = table('native-tab-review-ledger.json')
summaries = json.loads((run / 'summary.json').read_text())
observations = []
for batch in (1, 2):
    snapshot = json.loads((run / f'batches/{batch}.json').read_text())
    claims = snapshot['claims']
    source_events = {row['Activity reference']: row for row in finance if row['Arrival batch'] <= batch}
    gross = sum(cents(row['Amount (EUR)']) for row in source_events.values() if row['Activity type'] == 'settled')
    refunds = sum(cents(row['Amount (EUR)']) for row in source_events.values() if row['Activity type'] == 'refund')
    accepted = sum(cents(row['Obligation (EUR)']) for row in source_events.values() if row['Activity type'] == 'accepted')
    assert len(claims) == 120 and len({claim['claim_id'] for claim in claims}) == 120
    assert 'C24' not in {claim['claim_id'] for claim in claims}
    assert set(source_events) == {event['event_id'] for event in snapshot['finance_events']}
    assert all(event['arrival_batch'] <= batch for event in snapshot['finance_events'])
    assert all(history['arrival_batch'] <= batch for claim in claims for history in claim['history'])
    assert sum(claim['gross_paid_cents'] for claim in claims) == gross
    assert sum(claim['refunded_cents'] for claim in claims) == refunds
    assert sum(claim['paid_cents'] for claim in claims) == gross - refunds
    assert sum(request['amount_cents'] for request in snapshot['requests']) == accepted
    assert len({request['request_id'] for request in snapshot['requests']}) == 100
    assert summaries[batch - 1]['net_paid_cents'] == gross - refunds
    assert summaries[batch - 1]['accepted_obligation_cents'] == accepted
    for claim in claims:
        assert claim['paid_cents'] == claim['gross_paid_cents'] - claim['refunded_cents']
        if claim['authorized_obligation_cents'] is not None:
            assert claim['balance_cents'] == claim['authorized_obligation_cents'] - claim['paid_cents']
        else:
            assert claim['balance_cents'] is None
        if claim['status'] == 'closed-reimbursed':
            assert claim['current_review']['current']
            assert claim['financial_completion_accepted']
            assert claim['allowed_cents'] == claim['authorized_obligation_cents'] == claim['paid_cents']
            assert not any(issue['blocking'] and issue['resolved_by'] is None and issue['subject_id'] == claim['claim_id'] for issue in snapshot['issues'])
    queue = json.loads((run / f'stages/{batch}/repair-queue.json').read_text())
    for owner, view in queue['owner_views'].items():
        for status, identifiers in view.items():
            assert set(identifiers) == {item['item_id'] for item in queue['items'] if item['owner'] == owner and item['status'] == status}
    assert all(not request['sent'] for item in queue['items'] for request in item['requests'])
    handoff = (run / f'stages/{batch}/report.md').read_text()
    assert all(item['item_id'] in handoff for item in queue['items'])
    with (run / f'stages/{batch}/claims.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 120 and len(rows[0]) == 9
    by_id = {row['claim_id']: row for row in rows}
    assert set(by_id) == {claim['claim_id'] for claim in claims}
    assert all(by_id[claim['claim_id']]['allowed_cents'] == '' for claim in claims if claim['allowed_cents'] is None)
    for claim_id, owner in [('C09', 'EMP-01'), ('C21', people['EMP-01']['Budget owner'])]:
        item = next(item for item in queue['items'] if item['subject_id'] == claim_id and item['code'] == 'review_return')
        returning = next(row for row in review if row['Subject reference'] == claim_id and row['Outcome'] == 'return')
        assert item['owner'] == owner
        assert item['returning_reviews'][0]['reviewer'] == returning['Reviewer']
    process = next(item for item in snapshot['travel_cancellations'] if item['cancellation_id'] == 'TC122')
    assert process['affected_claim_ids'] == [] and process['original_request_ids'] == []
    assert process['financial_status'] == 'no-financial-effect'
    assert process['status'] == ('requested' if batch == 1 else 'confirmed')
    observations.append({'batch': batch, 'retained_finance_events': len(source_events), 'retained_accepted_cents': accepted, 'retained_gross_cents': gross, 'retained_refund_cents': refunds, 'open_repair_items': sum(item['status'] == 'open' for item in queue['items']), 'closed_reimbursed': sum(claim['status'] == 'closed-reimbursed' for claim in claims)})

second = json.loads((run / 'batches/2.json').read_text())
assert second['predecessor']['sha256'] == hashlib.sha256((run / 'batches/1.json').read_bytes()).hexdigest()
assert second['source_binding']['sha256'] == hashlib.sha256((run / 'sources.json').read_bytes()).hexdigest()
c20 = next(claim for claim in second['claims'] if claim['claim_id'] == 'C20')
assert c20['paid_cents'] == 11000 and c20['balance_cents'] == -1000 and c20['status'] == 'held'
c08 = next(claim for claim in second['claims'] if claim['claim_id'] == 'C08')
assert c08['allowed_cents'] is None and c08['next_owner'] == 'EMP-01'
assert set(path.name for path in (run / 'batches').iterdir()) == {'1.json', '2.json'}
result = {'scope': 'Supplemental offline checks; retained source values parsed independently of implementation. Does not certify all business rules or fresh native source access.', 'passed': True, 'observations': observations}
(base / 'independent-check-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
