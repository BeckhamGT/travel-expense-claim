"""Read-only independent audit of this linked run's retained native corpus.

This audit performs no fresh native access; collection attempts are recorded separately.

No production parser, arithmetic, event reducer, or coverage assertions are used.
This script creates only diagnostic JSON beside itself.
"""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from calendar import monthrange
from collections import Counter
from zoneinfo import ZoneInfo
import hashlib, json, re, csv, subprocess

REPO=Path(__file__).resolve().parents[4]
RUN=Path(__file__).resolve().parent.parent
OUT=Path(__file__).parent
errors=[]
checks=Counter()
def check(ok, label, detail=None):
    checks[label]+=1
    if not ok: errors.append({'check':label,'detail':detail})
def load(p): return json.loads(p.read_text(),parse_float=Decimal)
def money(v):
    n=Decimal(str(v))*100
    assert n==n.to_integral_value()
    return int(n)
def field(t,k):
    m=re.search(r'^\s*'+re.escape(k)+r':[^\S\n]*([^\n]*)',t,re.M)
    assert m,k
    return m.group(1).strip()
def rows(slug):
    raw=load(RUN/'retained'/('native-tab-'+slug+'.json'))['sheets'][0]['data'][0]['rowData']
    heads=[c['formattedValue'] for c in raw[4]['values']]
    result=[]
    for i,r in enumerate(raw[5:],6):
        values=r.get('values',[])
        if not any(c.get('effectiveValue') for c in values):continue
        parsed={}
        for j,k in enumerate(heads):
            c=values[j] if j<len(values) else {}
            if any(word in k.lower() for word in ['date','time','effective from','effective to']):
                v=c.get('formattedValue')
            else:v=next(iter(c.get('effectiveValue',{}).values()),None)
            parsed[k]=v
        parsed['_row']=i
        result.append(parsed)
    return result
tables={s:rows(s) for s in ['people','trips','merchant-payments','fx','caps','budget','review-ledger','review-packets','finance-activity','travel-cancellations']}
people={r['Employee ID']:r for r in tables['people']}
trips={(r['Trip reference'],int(r['Trip revision'])):r for r in tables['trips']}
packets={r['Decision reference']:r for r in tables['review-packets']}
decisions={r['Decision reference']:r for r in tables['review-ledger']}
receipts={}
for p in load(RUN/'retained/receipts.pages.json'):
    for t in re.split(r'(?=Receipt reference:)',p['text'])[1:]:
        k=field(t,'Receipt reference')
        receipts[k]={key:field(t,key) for key in ['Expense reference','Employee','Trip reference','Category','Currency','Gross amount','Documented units','Issued date']}
versions=[]
for stem in ['claims-initial','claims-updates']:
    for p in load(RUN/'retained'/(stem+'.pages.json')):
        t=p['text']
        v={k:field(t,k) for k in ['Claim reference','Revision','Arrival batch','Employee','Trip reference','Trip revision','Status','Claim reason','Related earlier claims']}
        v['lines']=[{'cost':m[0],'receipt':m[1],'filed':m[2],'gross':Decimal(m[3]),'currency':m[4]} for m in re.findall(r'^\s*\d+\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d+\.\d+)\s+([A-Z]{3})\s*$',t,re.M)]
        v['exception']=None
        if 'Authorizing Finance officer:' in t:
            v['exception']={k:field(t,k) for k in ['Authorizing Finance officer','Applies to claim','Applies to revision','Expense reference','Allowed original amount','Covered issues']}
            v['exception']['cancellation']=field(t,'Travel cancellation reference') if 'Travel cancellation reference:' in t else None
        v['page']=p['page'];versions.append(v)
manifest=load(RUN/'sources.json')
for f in manifest['files']:
    check(f['status']=='read' and hashlib.sha256((RUN/f['path']).read_bytes()).hexdigest()==f['sha256'],'retained_hash',f['source_id'])
rolefields={'administration':'Administration reviewer','budget_owner':'Budget owner','supervisor':'Supervisor','director':'Director'}
batch_results=[]
for b in range(1,5):
    snapshot=load(RUN/'batches'/f'{b}.json')
    current={}
    for v in versions:
        if int(v['Arrival batch'])<=b and (v['Claim reference'] not in current or int(v['Revision'])>int(current[v['Claim reference']]['Revision'])):current[v['Claim reference']]=v
    actual={c['claim_id']:c for c in snapshot['claims']}
    check(set(actual)==set(current),'visible_claim_ids',b)
    finance={}
    for r in tables['finance-activity']:
        if int(r['Arrival batch'])>b:continue
        k=r['Activity reference']
        payload={key:v for key,v in r.items() if key not in {'_row','Arrival batch'}}
        if k in finance:check(finance[k]['payload']==payload,'immutable_finance_redelivery',k)
        else:finance[k]={'row':r,'payload':payload}
    check(set(finance)==set(snapshot['admitted_event_ids']),'finance_event_ids',b)
    reqs={}; transfers={}
    for entry in sorted(finance.values(),key=lambda e:(e['row']['Activity time (UTC)'],e['row']['_row'])):
        r=entry['row']; typ=r['Activity type']; key=r['Request reference']; claim=r['Claim reference']
        if typ=='accepted':
            reqs[key]={'claim':claim,'obligation':money(r['Obligation (EUR)']),'paid':0,'refund':0,'payee':r['Payee ID'],'actor':r['Finance officer']}
        q=reqs[key]
        check((r['Payee ID'],r['Finance officer'],r['Currency'],claim)==(q['payee'],q['actor'],'EUR',q['claim']),'finance_actor_payee_binding',r['Activity reference'])
        if typ=='settled':
            q['paid']+=money(r['Amount (EUR)']);transfers[r['Activity reference']]={'amount':money(r['Amount (EUR)']),'recovered':0,'request':key}
        if typ=='refund':
            orig=transfers[r['Original activity reference']]; amount=money(r['Amount (EUR)'])
            check(orig['request']==key and orig['recovered']+amount<=orig['amount'],'confirmed_refund_link',r['Activity reference'])
            orig['recovered']+=amount;q['refund']+=amount
        if typ=='adjustment':q['obligation']=money(r['Obligation (EUR)'])
        if typ=='cancelled':q['obligation']=0
    for q in snapshot['requests']:
        native=reqs[q['request_id']]
        check((q['amount_cents'],q['paid_cents'],q['refunded_cents'],q['payee'])==(native['obligation'],native['paid'],native['refund'],native['payee']),'request_money_and_identity',{'batch':b,'request':q['request_id']})
    visible_decisions={r['Decision reference'] for r in tables['review-ledger'] if int(r['Arrival batch'])<=b}
    check({r['Decision reference'] for r in snapshot['decisions']}==visible_decisions,'visible_decisions',b)
    for ident,v in current.items():
        c=actual[ident];person=people[v['Employee']];trip=trips[(v['Trip reference'],int(v['Trip revision']))]
        check((c['revision'],c['employee_id'],c['trip_id'],c['trip_revision'])==(int(v['Revision']),v['Employee'],v['Trip reference'],int(v['Trip revision'])),'claim_revision_and_identity',{'batch':b,'claim':ident})
        if trip['International']:
            permit_roles=set()
            for d in tables['review-ledger']:
                if int(d['Arrival batch'])>b or d['Subject type']!='permit' or d['Subject reference']!=trip['Permit reference'] or d['Revision']!=trip['Permit revision'] or d['Outcome']!='approve':continue
                decision_day=datetime.strptime(d['Decision time (UTC)'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Amsterdam')).date().isoformat()
                if trip['First commitment date'] and decision_day>=trip['First commitment date']:continue
                roles=d['Review roles'].splitlines()
                if all(person[rolefields[role]]==d['Reviewer'] for role in roles):permit_roles.update(roles)
            needed={'administration','budget_owner','supervisor'}|({'director'} if money(trip['Estimate (EUR)'])>100000 else set())
            check(c['permission']['historical_permission']==(needed<=permit_roles),'historical_permission_route_and_timing',{'batch':b,'claim':ident})
        amount_by_cost={}
        for line in v['lines']:
            rec=receipts[line['receipt']]
            matches=[m for m in tables['merchant-payments'] if (m['Employee ID'],m['Trip reference'],m['Expense reference'],m['Currency'],Decimal(str(m['Gross amount'])))==(v['Employee'],v['Trip reference'],line['cost'],line['currency'],line['gross']) and m['Payment status']=='settled']
            supported=(rec['Employee'],rec['Trip reference'],rec['Expense reference'],rec['Currency'],Decimal(rec['Gross amount']))==(v['Employee'],v['Trip reference'],line['cost'],line['currency'],line['gross']) and len(matches)==1
            result=None
            if supported:
                m=matches[0];category=rec['Category'];original_amount=line['gross']
                if category=='personal':result=0
                elif category in ['transport','conference','lodging','meals']:
                    caps=[cap for cap in tables['caps'] if cap['Destination']==trip['Destination'] and cap['Category']==category and cap['Currency']==line['currency'] and cap['Effective from']<=m['Paid date']<=cap['Effective to']]
                    cap_known=category not in ['lodging','meals'] or len(caps)==1
                    if cap_known:
                        if caps:original_amount=min(original_amount,Decimal(str(caps[0]['Amount per unit']))*Decimal(rec['Documented units']))
                        ex=v['exception']
                        if ex and ex['Expense reference']==line['cost']:
                            check((ex['Authorizing Finance officer'],ex['Applies to claim'],int(ex['Applies to revision']))==(person['Finance officer'],ident,int(v['Revision'])),'exception_binding',ident)
                            original_amount=Decimal(ex['Allowed original amount'])
                        rates=[fx for fx in tables['fx'] if fx['Currency']==line['currency'] and fx['Rate date']==m['Paid date']]
                        rate=Decimal(1) if line['currency']=='EUR' else Decimal(str(rates[0]['EUR per currency unit'])) if len(rates)==1 else None
                        if rate is not None:result=int((original_amount*rate*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            # Explicit earlier-claim linkage permits exclusion only of proved settled original cost.
            related=[s.strip() for s in v['Related earlier claims'].split(',') if s.strip()!='None']
            for prior in related:
                for q in reqs.values():
                    if q['claim']!=prior:continue
                    prior_versions=[old for old in versions if old['Claim reference']==prior and int(old['Arrival batch'])<=b]
                    prior_version=max(prior_versions,key=lambda x:int(x['Revision']))
                    if len(prior_version['lines'])==1 and prior_version['lines'][0]['cost']==line['cost'] and result is not None:
                        result-=q['paid']-q['refund']
            out_line=next(l for l in c['lines'] if l['cost_id']==line['cost'])
            check(out_line['allowed_cents']==result,'independent_line_cents',{'batch':b,'claim':ident,'cost':line['cost'],'expected':result,'actual':out_line['allowed_cents']})
            amount_by_cost[line['cost']]=result
            # The source retains first filing for unchanged costs and uses trip end +2 calendar months.
            end=date.fromisoformat(trip['End date']);month=end.month+2;year=end.year+(month-1)//12;month=(month-1)%12+1
            expected_deadline=date(year,month,min(end.day,monthrange(year,month)[1])).isoformat()
            check(out_line['filing_deadline']==expected_deadline,'filing_deadline',{'batch':b,'claim':ident})
        expected_allowed=None if any(v is None for v in amount_by_cost.values()) else sum(amount_by_cost.values())
        check(c['allowed_cents']==expected_allowed,'independent_claim_cents',{'batch':b,'claim':ident})
        native_requests=[q for q in reqs.values() if q['claim']==ident]
        paid=sum(q['paid']-q['refund'] for q in native_requests)
        check(c['paid_cents']==paid,'independent_claim_paid',{'batch':b,'claim':ident})
        obligation=sum(q['obligation'] for q in native_requests) if native_requests else 0 if c['status'] in ['withdrawn','rejected'] else expected_allowed
        check(c['authorized_obligation_cents']==obligation,'independent_obligation',{'batch':b,'claim':ident})
        check(c['balance_cents']==(None if obligation is None else obligation-paid),'independent_balance',{'batch':b,'claim':ident})
        approved=set()
        for k in c['decision_ids']:
            d=decisions[k];p=packets[k];roles=d['Review roles'].splitlines()
            check(k in visible_decisions and d['Outcome']=='approve' and d['Subject type']=='claim' and d['Subject reference']==ident and int(d['Revision'])==int(v['Revision']),'decision_subject_revision',k)
            check(all(person[rolefields[role]]==d['Reviewer'] for role in roles),'decision_role_actor',k)
            check((p['Employee ID'],p['Trip reference'],int(p['Trip revision']),p['Permit reference'],p['Permit revision'])==(v['Employee'],v['Trip reference'],int(v['Trip revision']),trip['Permit reference'],trip['Permit revision']),'packet_identity',k)
            check(p['Expense references'].splitlines()==[line['cost'] for line in v['lines']],'packet_expenses',k)
            check(set(p['Budget record references'].splitlines())=={r['Ledger reference'] for r in tables['budget']},'packet_budget_context',k)
            relevant=[r for r in tables['travel-cancellations'] if int(r['Arrival batch'])<=b and (r['Trip reference'],r['Trip revision'])==(v['Trip reference'],int(v['Trip revision']))]
            expected_context={r['Cancellation reference'] for r in relevant}
            check(set((p['Travel cancellation references'] or '').splitlines())==expected_context,'packet_cancellation_context',k)
            check(all(d['Decision time (UTC)']>=r['Activity time (UTC)'] for r in relevant),'fresh_cancellation_aware_review',k)
            approved.update(roles)
        if c['status']=='closed-reimbursed':
            required={'administration','budget_owner','supervisor'}|({'director'} if expected_allowed>100000 else set())
            check(required<=approved and expected_allowed==paid==obligation and c['balance_cents']==0 and c['next_owner'] is None,'closed_reimbursement_source_conditions',{'batch':b,'claim':ident})
            check(not any(i.get('blocking') and i['subject_id']==ident for i in snapshot['issues']),'closed_without_blocking_issue',ident)
            if c['finance_resolution_required']:
                check(bool(c['current_resolution_event_ids']) and all(finance[k]['row']['Activity type']=='resolution' for k in c['current_resolution_event_ids']),'required_source_resolution',ident)
        if c['status'] in ['held','pending']:
            check(c['next_owner'] in set(person.values()) and bool(c['reason']),'owned_open_claim',{'batch':b,'claim':ident})
    unique_canc={}
    for row in tables['travel-cancellations']:
        if int(row['Arrival batch'])<=b:unique_canc.setdefault(row['Cancellation activity reference'],row)
    observed_canc={e for p in snapshot['travel_cancellations'] for e in p['admitted_cancellation_event_ids']}
    check(observed_canc==set(unique_canc),'visible_cancellation_event_ids',b)
    source_processes={}
    for row in unique_canc.values():source_processes.setdefault(row['Cancellation reference'],{})[row['Action']]=row
    check({p['cancellation_id'] for p in snapshot['travel_cancellations']}==set(source_processes),'cancellation_processes',b)
    for process in snapshot['travel_cancellations']:
        native=source_processes[process['cancellation_id']];req=native['requested'];conf=native.get('confirmed')
        trip=trips[(req['Trip reference'],int(req['Trip revision']))];person=people[trip['Employee ID']]
        check(req['Acting employee or supervisor']==trip['Employee ID'],'cancellation_initiating_actor',req['Cancellation activity reference'])
        check((process['trip_id'],process['trip_revision'],process['permit_id'],process['permit_revision'],process['target_type'])==(req['Trip reference'],int(req['Trip revision']),req['Permit reference'],req['Permit revision'],req['Cancelled subject']),'cancellation_target_revisions',{'batch':b,'id':process['cancellation_id']})
        check(process['status']==('confirmed' if conf else 'requested'),'cancellation_business_state',{'batch':b,'id':process['cancellation_id']})
        if conf:
            check(conf['Acting employee or supervisor']==person['Supervisor'] and conf['Initiation activity reference']==req['Cancellation activity reference'],'cancellation_confirmation_authority',conf['Cancellation activity reference'])
            check(conf['Activity time (UTC)']>req['Activity time (UTC)'] and conf['Effective time (UTC)']==conf['Activity time (UTC)'],'cancellation_effective_time',conf['Cancellation activity reference'])
            check(process['trip_retired']==(req['Cancelled subject']=='trip') and process['permit_retired']==bool(req['Permit reference']),'cancellation_retirement_scope',process['cancellation_id'])
        check(set(process['issue_record_ids'])<={i['record_id'] for i in snapshot['issues']},'cancellation_issue_references',process['cancellation_id'])
        if process['financial_status']=='no-financial-effect':
            check(trip['First commitment date'] is None and not process['affected_claim_ids'] and not process['original_request_ids'] and not any(m['Trip reference']==process['trip_id'] for m in tables['merchant-payments']),'cancellation_no_financial_effect',process['cancellation_id'])
        affected={v['Claim reference'] for v in versions if int(v['Arrival batch'])<=b and v['Trip reference']==process['trip_id'] and int(v['Trip revision'])==process['trip_revision']}
        check(set(process['affected_claim_ids'])==affected,'cancellation_affected_claim_history',process['cancellation_id'])
    allocations=sum(money(r['Allocation or commitment (EUR)']) for r in tables['budget'] if r['Entry type']=='allocation')
    prior=sum(money(r['Allocation or commitment (EUR)']) for r in tables['budget'] if r['Entry type']=='obligation')
    budget=allocations-prior-sum(max(q['obligation'],q['paid']-q['refund']) for q in reqs.values())
    check(all(group['remaining_cents']==budget for group in snapshot['budget_groups']),'independent_budget',b)
    batch_results.append({'batch':b,'claims':len(current),'line_occurrences':sum(len(v['lines']) for v in current.values()),'finance_events':len(finance),'requests':len(reqs),'net_paid_cents':sum(q['paid']-q['refund'] for q in reqs.values()),'budget_remaining_cents':budget})
final=load(RUN/'batches/4.json')
csvrows=list(csv.DictReader((RUN/'claims.csv').open()))
expected_columns=['claim_id','revision','trip_id','status','allowed_cents','paid_cents','balance_cents','next_owner','reason']
check(list(csvrows[0])==expected_columns,'csv_exact_columns')
check(len(csvrows)==121 and len({r['claim_id'] for r in csvrows})==121,'csv_exact_cardinality')
claims={c['claim_id']:c for c in final['claims']}
report=(RUN/'report.md').read_text()
for row in csvrows:
    c=claims[row['claim_id']]
    for col in expected_columns:check(row[col]==('' if c[col] is None else str(c[col])),'csv_field_agreement',{'claim':c['claim_id'],'field':col})
    rendered=' / '.join('unknown' if c[k] is None else str(c[k]) for k in ['allowed_cents','paid_cents','balance_cents'])
    check(f"| {c['claim_id']} / {c['revision']} | {c['trip_id']} | {c['status']} | {rendered} | {c['next_owner'] or '—'} |" in report,'report_money_identity_owner',c['claim_id'])
result={'mode':'independent retained-native source audit of the current linked run; no fresh source access','HEAD_observed_at_execution_before_final_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),'checks':dict(checks),'errors':errors,'source_run_id':manifest['run_id'],'source_manifest_sha256':hashlib.sha256((RUN/'sources.json').read_bytes()).hexdigest(),'batches':batch_results,'unknown_final_claims':[c['claim_id'] for c in final['claims'] if c['allowed_cents'] is None]}
(OUT/'independent-source-results.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
print(json.dumps(result,indent=2,default=str))
raise SystemExit(bool(errors))
