"""Offline full recheck of supplied domestic claim revisions.

This observer preserves source versions and Finance history. It creates no
requests, transfers, final acceptance or operational batch snapshots. The caller
selects claims; all visible Finance obligations still inform their shared budget.
"""

import argparse
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from .authority import recheck_authority
from .cancellations import reduce_cancellations
from .finance import summarize_finance
from .independence import budget_remaining, visible_at
from .monetary import calculate_line
from .verify_independence import Sources, SourceError, field, payment_check, receipt_records, single


POLICY_REFS = ["POLICY:paragraph" + str(n) for n in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16)]
ISSUE_NAMES = {"late filing": "late_filing", "late permit": "late_permit",
               "permit unapproved": "permit_unapproved", "travel cancellation": "travel_cancellation"}


def claim_versions(sources, through_batch=4):
    """Keep every supplied revision, including its original exception wording."""
    result, seen = [], set()
    for source_id, reference in (("INITIAL-PAGES", "INITIAL"), ("UPDATES-PAGES", "UPDATES")):
        for page in sources.read(source_id):
            text = page["text"]
            arrival = int(field(text, "Arrival batch"))
            if arrival > through_batch:
                continue
            lines = [dict(cost_id=m[0], receipt_id=m[1], first_submitted=m[2],
                          gross=Decimal(m[3]), currency=m[4]) for m in re.findall(
                r"^\s*\d+\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d+\.\d+)\s+([A-Z]{3})\s*$", text, re.M)]
            raw_line_count = len(re.findall(r"^\s*\d+\s+\S+\s+\S+\s+\d{4}-\d{2}-\d{2}\s+", text, re.M))
            parse_error = ("Missing, invalid or repeated expense line" if not lines or len(lines) != raw_line_count
                           or len({line["cost_id"] for line in lines}) != len(lines) else None)
            item = dict(id=field(text, "Claim reference"), revision=int(field(text, "Revision")),
                        batch=int(field(text, "Arrival batch")), employee=field(text, "Employee"),
                        trip=field(text, "Trip reference"), trip_revision=int(field(text, "Trip revision")),
                        submitted=field(text, "Submitted date"), status=field(text, "Status"),
                        reason=field(text, "Claim reason"), lines=lines, exception=None,
                        source_ref=f"{reference}:page{page['page']}", parse_error=parse_error)
            if "Authorizing Finance officer:" in text:
                try:
                    reason = re.search(r"Exception reason:\s*(.*?)(?=\n\s*\n|\Z)", text, re.S)
                    if not reason:
                        raise SourceError("Finance exception needs a reason")
                    raw_issues = field(text, "Covered issues")
                    words = [value.strip().lower().replace("_", " ") for value in re.split(r"[,;]", raw_issues)]
                    item["exception"] = dict(actor=field(text, "Authorizing Finance officer"),
                        claim_id=field(text, "Applies to claim"), revision=int(field(text, "Applies to revision")),
                        cost_id=field(text, "Expense reference"), allowed=Decimal(field(text, "Allowed original amount")),
                        covered_issues=[] if words == ["none"] else [ISSUE_NAMES.get(value, value) for value in words],
                        cancellation_id=field(text, "Travel cancellation reference") if "Travel cancellation reference:" in text else None,
                        reason=" ".join(reason.group(1).split()), source_ref=item["source_ref"])
                except (InvalidOperation, ValueError) as error:
                    item["parse_error"] = "Invalid Finance exception: " + str(error)
            key = (item["id"], item["revision"])
            if key in seen or item["batch"] < 1 or item["revision"] < 1:
                raise SourceError("Invalid or ambiguous claim version")
            seen.add(key)
            result.append(item)
    return result


def receipts_with_metadata(sources):
    result = receipt_records(sources)
    for page in sources.read("RECEIPTS-PAGES"):
        for block in re.split(r"(?=Receipt reference:)", page["text"])[1:]:
            result[field(block, "Receipt reference")].update(
                category=field(block, "Category"), units=field(block, "Documented units"),
                issued=field(block, "Issued date"))
    return result


def filing_deadline(end):
    original = date.fromisoformat(end)
    year, month = divmod(original.year * 12 + original.month - 1 + 2, 12)
    month += 1
    return date(year, month, min(original.day, monthrange(year, month)[1]))


def validate_exception(claim, line, person):
    exception = claim.get("exception")
    if not exception:
        return None, None
    valid = (exception["actor"] == person["Finance officer"]
             and exception["claim_id"] == claim["id"] and exception["revision"] == claim["revision"]
             and exception["cost_id"] in {cost["cost_id"] for cost in claim["lines"]} and bool(exception["reason"])
             and exception["allowed"].is_finite() and exception["allowed"] >= 0
             and set(exception["covered_issues"]) <= set(ISSUE_NAMES.values()))
    if not valid:
        return None, "Exception actor, revision, cost, amount, reason or covered issues do not bind this line"
    if exception["cost_id"] != line["cost_id"]:
        return None, None
    return exception, None


def material_changes(previous, current):
    if previous is None:
        return []
    fields = ("employee", "trip", "trip_revision", "submitted", "status", "lines")
    changes = [key for key in fields if previous[key] != current[key]]
    def exception_basis(claim):
        exception = claim.get("exception")
        return None if exception is None else {key: value for key, value in exception.items()
                                               if key not in {"revision", "source_ref"}}
    if exception_basis(previous) != exception_basis(current):
        changes.append("Finance exception basis")
    return changes


def budget_context(person, ledger, finance, people, claims, finance_rows):
    group = tuple(person[key] for key in ("Department", "Project", "Budget period"))
    rows = [row for row in ledger if tuple(row[key] for key in ("Department", "Project", "Budget period")) == group]
    available = budget_remaining(rows, [])
    charges, uncertainty = [], []
    prior_ids = {row["Obligation reference"] for row in rows if row["Entry type"] == "obligation"}
    for request_id, request in finance["requests"].items():
        owner = people[request["employee_id"]]
        if tuple(owner[key] for key in ("Department", "Project", "Budget period")) != group:
            continue
        if request_id in prior_ids:
            uncertainty.append("Accepted request also occurs in prior ledger: " + request_id)
            continue
        # Paid money remains expenditure even when a corrected obligation is lower.
        charge = max(request["current_obligation_cents"], request["net_paid_cents"])
        charges.append(dict(request_id=request_id, charged_cents=charge,
                            obligation_cents=request["current_obligation_cents"],
                            net_paid_cents=request["net_paid_cents"], source_refs=request["source_refs"]))
        if available is not None:
            available -= charge
    for issue in finance["holds"]:
        matching = [row for row in finance_rows if row["Activity reference"] == issue["event_id"]]
        if not any(row["Activity type"] in {"accepted", "adjustment", "cancelled", "settled", "refund"} for row in matching):
            continue
        # Known overpayments and late transfers are already charged above. Only
        # unadmitted or conflicting monetary facts introduce funding uncertainty.
        if issue["code"] in {"overpayment", "settlement_after_cancellation"}:
            continue
        request = finance["requests"].get(issue["request_id"])
        employee = request["employee_id"] if request else claims.get(issue["claim_id"], {}).get("employee")
        owner = people.get(employee)
        if owner is None or tuple(owner[key] for key in ("Department", "Project", "Budget period")) == group:
            uncertainty.append(dict(reason=issue["reason"], source_refs=issue["source_refs"]))
    return dict(group=list(group), remaining_cents=available,
                sufficient=available is not None and available >= 0 and not uncertainty,
                uncertainty=uncertainty, charges=charges,
                source_refs=[row["_ref"] for row in rows])


def _stamp(value):
    return datetime.fromisoformat(value.removesuffix(" UTC").replace("Z", "+00:00")).replace(tzinfo=timezone.utc)


def _recheck(claim, history, sources, tables, receipts, reviews, packets, cancellations, finance):
    person = tables["people"][claim["employee"]]
    trip = single([row for row in tables["Trips"] if row["Trip reference"] == claim["trip"]
                   and row["Trip revision"] == claim["trip_revision"]], "current trip revision")
    issues, lines = [], []
    def issue(code, detail, owner, refs, *, resolved_by=None, next_action=None):
        item = dict(code=code, detail=detail, owner=owner, source_refs=sorted(set(refs)),
                    resolved_by=resolved_by, blocking=resolved_by is None,
                    next_action=next_action or "Obtain source-bound current evidence or applicable human response")
        issues.append(item)
        return item
    if trip["Employee ID"] != claim["employee"]:
        issue("trip_identity", "Trip employee does not match current claim", claim["employee"], [trip["_ref"], claim["source_ref"]])
    if trip["International"]:
        issue("permit_review_pending", "This scoped recheck has not implemented international permit eligibility", person["Administration reviewer"], [trip["_ref"], "POLICY:paragraph4"])
    if claim.get("parse_error"):
        issue("claim_payload", claim["parse_error"], claim["employee"], [claim["source_ref"]])
    relevant = [process for process in cancellations["processes"] if process["trip"] == claim["trip"]
                and process["trip_revision"] == claim["trip_revision"]]
    confirmed = [process for process in relevant if process["status"] == "confirmed"]
    for process in relevant:
        if process["status"] == "requested":
            issue("cancellation_pending", "A valid business cancellation request pauses affected payment readiness", person["Supervisor"], process["source_refs"])
    for hold in cancellations["holds"]:
        admitted_process_ids = {process["cancellation_id"] for process in relevant}
        admitted_event_ids = {event for process in relevant for event in process["admitted_cancellation_event_ids"]}
        delivery = hold.get("delivery", {})
        exact_target = (delivery.get("Trip reference"), delivery.get("Trip revision")) == (claim["trip"], claim["trip_revision"])
        if exact_target or hold.get("cancellation_id") in admitted_process_ids or hold.get("event_id") in admitted_event_ids:
            issue("cancellation_import", hold.get("reason", str(hold)), person["Supervisor"], hold["source_refs"])
    previous_costs = {}
    for old in history:
        if old["revision"] < claim["revision"]:
            for line in old["lines"]:
                previous_costs.setdefault(line["cost_id"], line["first_submitted"])
    for line in claim["lines"]:
        receipt = receipts.get(line["receipt_id"])
        check = payment_check(claim, line, receipt, tables["Merchant payments"], sources.data["case_clock"])
        exception, exception_error = validate_exception(claim, line, person)
        if exception_error:
            issue("invalid_exception", exception_error, person["Finance officer"], [claim["source_ref"]])
        calculation = dict(allowed_cents=None, findings=[], source_refs=[])
        settled = [row for row in tables["Merchant payments"] if row["_ref"] in check.source_refs]
        if not check.satisfied:
            issue("paid_evidence", check.fact, claim["employee"], check.source_refs, next_action=check.next_action)
        else:
            paid = single(settled, "matching paid proof")
            first = previous_costs.get(line["cost_id"], line["first_submitted"])
            if first != line["first_submitted"]:
                issue("changed_first_filing", "Unchanged cost cannot reset its initial filing date", person["Administration reviewer"], [claim["source_ref"], *[v["source_ref"] for v in history]])
            if date.fromisoformat(first) > date.fromisoformat(sources.data["case_clock"]):
                issue("future_filing", "Cost filing is after the fixed case clock", claim["employee"], [claim["source_ref"]])
            if date.fromisoformat(first) < date.fromisoformat(paid["Paid date"]) or date.fromisoformat(first) < date.fromisoformat(receipt["issued"]):
                issue("filing_before_evidence", "Initial filing predates payment or receipt", claim["employee"], check.source_refs)
            if date.fromisoformat(first) > filing_deadline(trip["End date"]):
                resolved = exception["source_ref"] if exception and "late_filing" in exception["covered_issues"] else None
                issue("late_filing", "First filing is after the original planned trip deadline", person["Finance officer"], [claim["source_ref"], trip["_ref"]], resolved_by=resolved)
            calculation = calculate_line(gross=line["gross"], currency=line["currency"], category=receipt["category"],
                units=receipt["units"], destination=trip["Destination"], payment_date=paid["Paid date"],
                fx_rows=tables["FX"], caps_rows=tables["Caps"], replacement_allowed=exception["allowed"] if exception else None)
            for finding in calculation["findings"]:
                if finding["blocking"]:
                    issue(finding["code"], finding["detail"], person["Finance officer"], [*check.source_refs, *calculation["source_refs"]])
        for process in confirmed:
            resolved = (exception["source_ref"] if exception and "travel_cancellation" in exception["covered_issues"]
                        and exception["cancellation_id"] == process["cancellation_id"] else None)
            issue("travel_cancellation", f"{line['cost_id']} needs explicit cost disposition for {process['cancellation_id']}",
                  person["Finance officer"], [claim["source_ref"], *process["source_refs"]], resolved_by=resolved)
            if settled and settled[0]["Paid date"] == process["confirmed_time"][:10]:
                issue("cancellation_payment_order", "Date-only payment and same-day cancellation have unresolved ordering", person["Finance officer"], [*check.source_refs, *process["source_refs"]])
        lines.append(dict(cost_id=line["cost_id"], receipt_id=line["receipt_id"], evidence_supported=check.satisfied,
                          first_filed=previous_costs.get(line["cost_id"], line["first_submitted"]),
                          filing_deadline=filing_deadline(trip["End date"]).isoformat(),
                          calculation=calculation, exception=exception, source_refs=list(check.source_refs)))
    entitlement = None if claim.get("parse_error") or any(line["calculation"]["allowed_cents"] is None for line in lines) else sum(line["calculation"]["allowed_cents"] for line in lines)
    authority = recheck_authority(claim, trip, person, entitlement, reviews, packets, relevant, sources)
    if not authority["current"]:
        issue("current_approvals", "Current revision lacks applicable approval roles: " + ", ".join(authority["missing_roles"]), person["Administration reviewer"], authority["source_refs"] or [claim["source_ref"]])
    current_finance = finance["claims"][claim["id"]]
    requests = [finance["requests"][key] for key in current_finance["request_ids"]]
    changes = material_changes(history[-2] if len(history) > 1 else None, claim)
    # Finance has no claim-revision field. Arrival context establishes whether its
    # first acceptance existed before the material correction became available.
    accepted_events = [event for event in finance["admitted_events"] if event["claim_id"] == claim["id"] and event["type"] == "accepted"]
    accepted_before_revision = any(next(row["Arrival batch"] for row in tables["visible_finance"]
        if row["Activity reference"] == event["event_id"]) < claim["batch"] for event in accepted_events)
    cancelled_after_acceptance = any(_stamp(event["time"]) < _stamp(process["confirmed_time"]) for event in accepted_events for process in confirmed)
    resolution_required = bool((changes and accepted_before_revision) or cancelled_after_acceptance
                               or any(event["claim_id"] == claim["id"] and event["type"] == "adjustment" for event in finance["admitted_events"]))
    # Finance rows do not carry a revision number. Require corroborating current
    # reviews and business chronology as well as arrival and amount; arrival alone
    # cannot turn a late-imported old resolution into current resolution proof.
    resolutions = []
    current_review_times = [_stamp(row["Decision time (UTC)"]) for row in reviews
                            if row["Decision reference"] in authority["valid_decision_ids"]]
    for event in finance["admitted_events"]:
        if event["claim_id"] != claim["id"] or event["type"] != "resolution" or event["obligation_cents"] != entitlement:
            continue
        arrival = min(row["Arrival batch"] for row in tables["visible_finance"] if row["Activity reference"] == event["event_id"])
        if (authority["current"] and arrival >= claim["batch"]
                and all(_stamp(event["time"]) >= stamp for stamp in current_review_times)
                and all(_stamp(event["time"]) >= _stamp(process["confirmed_time"]) for process in confirmed)):
            resolutions.append(event["event_id"])
    if resolution_required and not resolutions:
        issue("finance_resolution", "Post-acceptance material correction/cancellation needs current explicit Finance resolution", person["Finance officer"], [claim["source_ref"], *[ref for req in requests for ref in req["source_refs"]]])
    for hold in current_finance["holds"]:
        issue(hold["code"], hold["reason"], hold["owner"], hold["source_refs"])
    if requests and entitlement is not None and current_finance["current_obligation_cents"] != entitlement:
        issue("obligation_mismatch", "Recorded Finance obligation differs from rechecked amount", person["Finance officer"], [claim["source_ref"], *[ref for req in requests for ref in req["source_refs"]]])
    balance = None if entitlement is None else entitlement - current_finance["net_paid_cents"]
    if balance is not None and balance < 0 and not any(item["code"] == "overpayment" for item in issues):
        issue("overpayment", "Confirmed net paid exceeds current calculated amount; retain transfers until a linked refund", person["Finance officer"], [ref for req in requests for ref in req["source_refs"]])
    own_costs = {line["cost_id"] for line in claim["lines"]}
    shared = []
    for request_id, request in finance["requests"].items():
        if request["claim_id"] == claim["id"]:
            continue
        acceptance_batch = min(row["Arrival batch"] for row in tables["visible_finance"]
                               if row["Request reference"] == request_id and row["Activity type"] == "accepted")
        accepted_version = max((version for version in tables["visible_versions"]
                                if version["id"] == request["claim_id"] and version["batch"] <= acceptance_batch),
                               key=lambda version: version["revision"])
        other_costs = {line["cost_id"] for line in accepted_version["lines"]}
        if own_costs & other_costs:
            shared.append(request_id)
            issue("shared_cost_obligation", "Cost is already bound to another accepted request: " + request_id,
                  person["Finance officer"], [claim["source_ref"], *request["source_refs"]])
    budget = budget_context(person, tables["Budget"], finance, tables["people"], tables["latest"], tables["visible_finance"])
    if not budget["sufficient"]:
        issue("shared_budget", "Actual shared funding is deficient or unresolved", person["Budget owner"], budget["source_refs"])
    blocking = [item for item in issues if item["blocking"]]
    return dict(revision=claim["revision"], source_ref=claim["source_ref"], employee=claim["employee"], trip=claim["trip"],
        material_changes=changes, full_recheck_steps=["evidence", "calculations", "eligibility", "current approvals", "budget and obligations", "Finance history"],
        revision_history=[dict(revision=v["revision"], arrival_batch=v["batch"], source_ref=v["source_ref"], trip=v["trip"], employee=v["employee"]) for v in history],
        lines=lines, calculated_entitlement_cents=entitlement, issues=issues, authority=authority,
        finance=current_finance, original_requests={key: finance["requests"][key] for key in current_finance["request_ids"]},
        calculated_balance_cents=balance, finance_resolution_required=resolution_required, current_resolution_event_ids=resolutions,
        budget=budget, shared_cost_request_ids=shared, arrangements_paused=bool(relevant),
        trip_retired_for_future_arrangements=any(p["target_type"] == "trip" for p in confirmed),
        current_recheck_supported=not blocking, competing_replacement_requests_held=bool(accepted_before_revision and not resolutions),
        financial_completion_accepted=False, completion_choice="Learner choice 3 pending; no closure verdict",
        policy_refs=POLICY_REFS)


def inspect(manifest, claim_ids, through_batch=4):
    if not 1 <= through_batch <= 4 or not claim_ids or len(set(claim_ids)) != len(claim_ids):
        raise SourceError("Select distinct claim IDs and a batch from 1 through 4")
    sources = Sources(manifest)
    versions = claim_versions(sources, through_batch)
    if not set(claim_ids) <= {claim["id"] for claim in versions}:
        raise SourceError("Requested claim not found in supplied versions")
    tables = {name: sources.table(name) for name in ("People", "Trips", "Merchant payments", "Budget", "FX", "Caps")}
    tables["people"] = {person["Employee ID"]: person for person in tables["People"]}
    # Effective cap dates are Excel calendar serials, not timestamps. Sources.table
    # exposes effectiveValue for these two headings; normalize from the native
    # serial without a timezone conversion.
    for cap in tables["Caps"]:
        for key in ("Effective from", "Effective to"):
            if isinstance(cap[key], (int, Decimal)):
                cap[key] = (date(1899, 12, 30) + timedelta(days=int(cap[key]))).isoformat()
    receipts = receipts_with_metadata(sources)
    all_reviews, all_packets = sources.table("Review ledger"), sources.table("Review packets")
    all_finance, all_cancellations = sources.table("Finance activity"), sources.table("Travel cancellations")
    batches = []
    for batch in range(1, through_batch + 1):
        visible = [claim for claim in versions if claim["batch"] <= batch]
        latest = {identity: max([v for v in visible if v["id"] == identity], key=lambda v: v["revision"])
                  for identity in {v["id"] for v in visible}}
        finance_claims = {identity: {**claim, "employee_by_batch": {version["batch"]: version["employee"]
                           for version in visible if version["id"] == identity}} for identity, claim in latest.items()}
        reviews = visible_at(all_reviews, batch)
        decision_ids = {row["Decision reference"] for row in reviews}
        packets = [packet for packet in all_packets if packet["Decision reference"] in decision_ids]
        tables["visible_versions"] = visible
        tables["latest"] = latest
        tables["visible_finance"] = visible_at(all_finance, batch)
        finance = summarize_finance(tables["visible_finance"], tables["people"], finance_claims,
                                    sources.data["case_clock"], sources.data["case_timezone"])
        cancellation = reduce_cancellations(visible_at(all_cancellations, batch), tables["people"], tables["Trips"], sources)
        subjects = {}
        for identity in claim_ids:
            if identity not in latest:
                continue
            history = sorted([v for v in visible if v["id"] == identity], key=lambda v: v["revision"])
            subjects[identity] = _recheck(latest[identity], history, sources, tables, receipts, reviews, packets, cancellation, finance)
        batches.append(dict(batch_id=batch, claims=subjects, cancellation_processes=cancellation,
                            finance_replayed_event_ids=finance["replayed_event_ids"]))
    return dict(mode="offline retained-source full-recheck verification", scope="Current domestic claim rechecks; no dispatch, operational snapshot or completion acceptance",
        source_run_id=sources.data["run_id"], source_manifest_sha256=sha256(sources.path.read_bytes()).hexdigest(),
        case_clock=sources.data["case_clock"], case_timezone=sources.data["case_timezone"], batches=batches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--claim", action="append", required=True)
    parser.add_argument("--through-batch", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.sources, args.claim, args.through_batch)
    content = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        if args.output.read_text() != content:
            raise SourceError("Distinct existing verification preserved; use a new output path")
    else:
        with args.output.open("x") as stream:
            stream.write(content)
    print(args.output)


if __name__ == "__main__":
    main()
