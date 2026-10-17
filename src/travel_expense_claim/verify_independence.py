"""Offline source-bound verification of the adopted independence constraint.

This component observes initial-batch evidence, authorizations and commitments.
It does not calculate final entitlement, dispatch requests, close claims, choose
correction scope, or organize the operational repair queue.
"""

import argparse
from datetime import datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .independence import Check, Work, budget_remaining, cents, evaluate, visible_at


class SourceError(ValueError):
    pass


class Sources:
    def __init__(self, manifest):
        self.path = Path(manifest).resolve()
        self.base = self.path.parent
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        entries = self.data["files"]
        self.files = {e["source_id"]: e for e in entries}
        if len(self.files) != len(entries) or len({e["url"] for e in entries}) != 5:
            raise SourceError("Need unique source IDs and coverage of all five native URLs")
        for entry in entries:
            if entry["status"] != "read":
                raise SourceError("This verification requires complete retained sources")
            path = (self.base / entry["path"]).resolve()
            if not path.is_relative_to(self.base) or sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise SourceError("Missing, unsafe or hash-mismatched retained source: " + entry["source_id"])

    def read(self, source_id):
        entry = self.files[source_id]
        return json.loads((self.base / entry["path"]).read_text(encoding="utf-8"), parse_float=Decimal)

    def table(self, name):
        source_id = "REGISTERS-" + name.upper().replace(" ", "-")
        sheet = self.read(source_id)["sheets"][0]
        rows = sheet["data"][0]["rowData"]
        headers = [v["formattedValue"] for v in rows[4]["values"]]
        result = []
        for index, data in enumerate(rows[5:], 6):
            values = data.get("values", [])
            row = {}
            for column, header in enumerate(headers):
                cell = values[column] if column < len(values) else {}
                value = cell.get("effectiveValue", {})
                if "date" in header.lower() or "time" in header.lower():
                    row[header] = cell.get("formattedValue")
                else:
                    row[header] = next(iter(value.values()), None)
            if any(v is not None for v in row.values()):
                row["_ref"] = f"{source_id}:row{index}"
                result.append(row)
        return result


def field(text, label):
    match = re.search(r"^\s*" + re.escape(label) + r":\s*([^\n]+)", text, re.M)
    if not match:
        raise SourceError("Missing binder field: " + label)
    return match.group(1).strip()


def initial_claims(sources):
    claims = {}
    for page in sources.read("INITIAL-PAGES"):
        text = page["text"]
        lines = [dict(cost_id=m[0], receipt_id=m[1], first_submitted=m[2], gross=Decimal(m[3]), currency=m[4]) for m in re.findall(r"^\s*\d+\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d+\.\d+)\s+([A-Z]{3})\s*$", text, re.M)]
        if not lines:
            raise SourceError("No expense lines in initial claim page")
        item = dict(id=field(text, "Claim reference"), revision=int(field(text, "Revision")), batch=int(field(text, "Arrival batch")), employee=field(text, "Employee"), trip=field(text, "Trip reference"), trip_revision=int(field(text, "Trip revision")), lines=lines, source_ref=f"INITIAL:page{page['page']}")
        if item["id"] in claims:
            raise SourceError("Ambiguous initial claim identity")
        claims[item["id"]] = item
    return claims


def receipt_records(sources):
    receipts = {}
    for page in sources.read("RECEIPTS-PAGES"):
        for block in re.split(r"(?=Receipt reference:)", page["text"])[1:]:
            key = field(block, "Receipt reference")
            if key in receipts:
                raise SourceError("Duplicate receipt identity")
            employee_label = "Employee ID" if re.search(r"^\s*Employee ID:", block, re.M) else "Employee"
            receipts[key] = dict(cost_id=field(block, "Expense reference"), employee=field(block, employee_label), trip=field(block, "Trip reference"), currency=field(block, "Currency"), gross=Decimal(field(block, "Gross amount")), source_ref=f"RECEIPTS:page{page['page']}")
    return receipts


def split(value):
    return tuple(str(value).splitlines()) if value else ()


def single(rows, label):
    if len(rows) != 1:
        raise SourceError("Missing or ambiguous " + label)
    return rows[0]


def before_clock(value, sources):
    if not value:
        return False
    event = datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=ZoneInfo("UTC"))
    day = datetime.strptime(sources.data["case_clock"], "%Y-%m-%d").date()
    end = datetime.combine(day + timedelta(days=1), time(), ZoneInfo(sources.data["case_timezone"]))
    return event < end


def payment_check(claim, line, receipt, payments, case_clock):
    """A matching cost ID alone is insufficient; all evidence identities must bind."""
    expected = (line["cost_id"], claim["employee"], claim["trip"], line["currency"], line["gross"])
    receipt_matches = receipt is not None and tuple(receipt[k] for k in ("cost_id", "employee", "trip", "currency", "gross")) == expected
    matching = [r for r in payments if (r["Expense reference"], r["Employee ID"], r["Trip reference"], r["Currency"], r["Gross amount"]) == expected and r["Receipt reference"] == line["receipt_id"] and r["Payment status"] == "settled" and r["Paid date"] and datetime.strptime(r["Paid date"], "%Y-%m-%d").date() <= datetime.strptime(case_clock, "%Y-%m-%d").date()]
    ok = receipt_matches and len(matching) == 1
    refs = (claim["source_ref"], receipt["source_ref"] if receipt else "RECEIPTS:all-pages", *(r["_ref"] for r in matching))
    if not matching:
        refs += ("REGISTERS-MERCHANT-PAYMENTS:complete-tab",)
    action = f"Supply matching settled merchant proof for {line['receipt_id']}; retain the existing matched receipt" if receipt_matches else f"Supply original receipt and separate settled proof bound to employee, trip, cost, currency, gross and {line['receipt_id']}"
    return Check("evidence", ok, f"{claim['id']} revision {claim['revision']} / {line['cost_id']}: receipt and matching settled merchant proof " + ("verified" if ok else "missing, ambiguous or incompatible"), claim["employee"], action, refs)


def inspect(manifest, subjects, batch=1):
    if batch != 1:
        raise SourceError("This initial-batch component does not apply correction policy; later-batch implementation awaits learner choice 2")
    sources = Sources(manifest)
    claims = initial_claims(sources)
    receipts = receipt_records(sources)
    people = {r["Employee ID"]: r for r in sources.table("People")}
    trips, payments, ledger = sources.table("Trips"), sources.table("Merchant payments"), sources.table("Budget")
    reviews = visible_at(sources.table("Review ledger"), batch)
    packets = {r["Decision reference"]: r for r in sources.table("Review packets")}
    finance = visible_at(sources.table("Finance activity"), batch)
    cancellations = visible_at(sources.table("Travel cancellations"), batch)
    # Check observed Finance acceptance bindings before using them as shared commitments.
    accepted = []
    event_payloads, request_payloads = {}, {}
    for row in finance:
        if row["Activity type"] != "accepted":
            raise SourceError("Initial-budget observer needs a full Finance reducer for non-acceptance outcomes")
        claim = claims.get(row["Claim reference"])
        person = people.get(claim["employee"]) if claim else None
        if not person or row["Finance officer"] != person["Finance officer"] or row["Payee ID"] != person["Payee ID"] or row["Currency"] != "EUR" or not before_clock(row["Activity time (UTC)"], sources):
            raise SourceError("Cannot establish shared budget from incompatible Finance acceptance")
        event_id, request_id = row["Activity reference"], row["Request reference"]
        payload = {k: v for k, v in row.items() if k not in {"_ref", "Arrival batch"}}
        request_payload = (claim["id"], row["Finance officer"], row["Payee ID"], row["Currency"], row["Obligation (EUR)"])
        if not event_id or (event_id in event_payloads and event_payloads[event_id] != payload) or (request_id in request_payloads and request_payloads[request_id] != request_payload):
            raise SourceError("Conflicting immutable Finance event/request prevents proving shared budget")
        event_payloads[event_id], request_payloads[request_id] = payload, request_payload
        if any(e["request_id"] == request_id for e in accepted):
            continue
        accepted.append(dict(request_id=row["Request reference"], amount_cents=cents(row["Obligation (EUR)"]), claim=claim, group=tuple(person[k] for k in ("Department", "Project", "Budget period")), source_ref=row["_ref"], event_id=row["Activity reference"]))
    work, observations = [], {}
    for selector in subjects:
        kind, identity, revision_text = selector.split(":")
        revision = int(revision_text)
        if kind == "claim":
            claim = claims.get(identity)
            if not claim or claim["revision"] != revision or claim["batch"] > batch:
                raise SourceError("Claim version is not available in selected batch")
            trip = single([r for r in trips if r["Trip reference"] == claim["trip"] and r["Trip revision"] == claim["trip_revision"]], "claim trip revision")
            person = people[claim["employee"]]
            costs = tuple(line["cost_id"] for line in claim["lines"])
            own = [r for r in accepted if r["claim"]["id"] == identity]
            amount = own[0]["amount_cents"] if len(own) == 1 else None
            checks = [payment_check(claim, line, receipts.get(line["receipt_id"]), payments, sources.data["case_clock"]) for line in claim["lines"]]
            observations[selector] = dict(subject_type=kind, subject_id=identity, revision=revision, progress_scope="Continue independent review and observation of existing request; no dispatch or closure authority", trip_id=claim["trip"], trip_revision=claim["trip_revision"], entitlement_cents=None, entitlement_assessment="pending full monetary implementation; never inferred from accepted request", recorded_request_status="accepted" if own else "not_observed", recorded_request_ids=[r["request_id"] for r in own], recorded_obligation_cents=amount, visible_settlement_event_ids=[], confirmed_paid_cents=0, financially_closed=False)
        elif kind == "permit":
            trip = single([r for r in trips if r["Permit reference"] == identity and r["Permit revision"] == revision], "permit revision")
            person = people[trip["Employee ID"]]
            costs = ()
            amount = cents(trip["Estimate (EUR)"])
            own = []
            checks = [Check("evidence", trip["First commitment date"] is None and not any(r["Trip reference"] == trip["Trip reference"] for r in payments), "Separate permit process with no committed or merchant-paid cost observed", "Administration", "Retain trip/permit evidence without inventing a claim", (trip["_ref"], "REGISTERS-MERCHANT-PAYMENTS:complete-tab"))]
            observations[selector] = dict(subject_type=kind, subject_id=identity, revision=revision, progress_scope="Independent administrative/cancellation tracking only; estimate affordability and funded arrangements are not established", trip_id=trip["Trip reference"], trip_revision=int(trip["Trip revision"]), claim_id=None, recorded_estimate_cents=amount, arrangements_paused=False, cancellation_status="not_observed", financially_closed=False)
        else:
            raise SourceError("Subject must be claim or permit")
        if trip["Employee ID"] != person["Employee ID"]:
            raise SourceError("Employee/trip identity conflict")
        group = tuple(person[k] for k in ("Department", "Project", "Budget period"))
        grouped_ledger = [r for r in ledger if tuple(r[k] for k in ("Department", "Project", "Budget period")) == group]
        group_acceptances = [r for r in accepted if r["group"] == group]
        available = budget_remaining(grouped_ledger, group_acceptances)
        checks.append(Check("budget", available >= 0 and (kind == "permit" or amount is not None), f"Shared budget {group}: remaining {available} cents after {len(group_acceptances)} observed accepted obligations; own amount " + ("known" if amount is not None else "not yet established"), person["Budget owner"], "Resolve actual funding deficit/unknown commitment before dependent financial readiness", tuple(r["_ref"] for r in grouped_ledger) + ("REGISTERS-FINANCE-ACTIVITY:all-visible-batch1-accepted-requests",)))
        obligations = [r for r in accepted if r["claim"]["id"] != identity and set(costs) & {line["cost_id"] for line in r["claim"]["lines"]}]
        checks.append(Check("obligations", not obligations, "Prior/shared cost obligations " + ("conflict: " + ", ".join(r["request_id"] for r in obligations) if obligations else "checked; no competing accepted request for this cost"), person["Finance officer"], "Resolve duplicate cost/request basis with Finance; preserve existing transfers", ("INITIAL-PAGES:all-claims", "REGISTERS-FINANCE-ACTIVITY:visible-batch1")))
        required = {"administration": person["Administration reviewer"], "budget_owner": person["Budget owner"], "supervisor": person["Supervisor"]}
        if amount is not None and amount > 100000:
            required["director"] = person["Director"]
        observations[selector]["director_requirement"] = "unknown_pending_entitlement" if amount is None else "required" if amount > 100000 else "not_required_for_observed_amount"
        current_roles = {}
        for row in reviews:
            packet = packets.get(row["Decision reference"])
            if row["Subject type"] != kind or row["Subject reference"] != identity or row["Revision"] != revision or row["Outcome"] not in {"approve", "return", "reject"} or not packet or not row["Reason"] or not before_clock(row["Decision time (UTC)"], sources):
                continue
            roles = split(row["Review roles"])
            expected = (person["Employee ID"], trip["Trip reference"], trip["Trip revision"], trip["Permit reference"], trip["Permit revision"], costs)
            actual = (packet["Employee ID"], packet["Trip reference"], packet["Trip revision"], packet["Permit reference"], packet["Permit revision"], split(packet["Expense references"]))
            versions = set(split(row["Source revisions"]))
            context_matches = all(packet[name] == trip[name] for name in ("Business purpose", "Client", "Schedule coverage", "Alternatives considered"))
            estimate_matches = kind != "permit" or packet["Reviewed estimate (EUR)"] == trip["Estimate (EUR)"]
            if actual != expected or not context_matches or not estimate_matches or packet["Policy revision"] != sources.files["POLICY"]["source_version"] or not {sources.files["INITIAL"]["source_version"], packet["Policy revision"]} <= versions or set(split(packet["Budget record references"])) != {r["Ledger reference"] for r in grouped_ledger}:
                continue
            if not roles or any(role not in required or required[role] != row["Reviewer"] for role in roles) or (len(roles) > 1 and set(roles) != {"budget_owner", "supervisor"}):
                continue
            stamp = row["Decision time (UTC)"]
            for role in roles:
                previous = current_roles.get(role)
                if previous is None or stamp > previous[0]:
                    current_roles[role] = (stamp, row["Outcome"], row["_ref"])
                elif stamp == previous[0] and row["Outcome"] != previous[1]:
                    current_roles[role] = (stamp, "conflict", row["_ref"])
        found = {role for role, (_, outcome, _) in current_roles.items() if outcome == "approve"}
        decision_refs = sorted({ref for _, outcome, ref in current_roles.values() if outcome == "approve"})
        observations[selector]["current_decision_refs"] = decision_refs
        checks.append(Check("authority", set(required) <= found, "Exact subject/revision/current packet roles: " + ", ".join(sorted(found)) + "; required: " + ", ".join(sorted(required)), person["Administration reviewer"], "Obtain only applicable actor/role replies; another subject's approval cannot substitute", tuple(decision_refs) or ("REGISTERS-REVIEW-LEDGER:visible-batch1",)))
        for row in cancellations:
            if row["Trip reference"] != trip["Trip reference"] or row["Trip revision"] != trip["Trip revision"]:
                continue
            valid_request = row["Action"] == "requested" and row["Cancelled subject"] in {"trip", "permit"} and bool(row["Cancellation activity reference"]) and bool(row["Cancellation reference"]) and bool(row["Business reason"]) and row["Acting employee or supervisor"] == person["Employee ID"] and row["Permit reference"] == trip["Permit reference"] and row["Permit revision"] == trip["Permit revision"] and row["Initiation activity reference"] is None and row["Effective time (UTC)"] is None and before_clock(row["Activity time (UTC)"], sources)
            if not valid_request:
                raise SourceError("Cancellation requires the later full reducer; cannot infer authority")
            observations[selector].update(cancellation_id=row["Cancellation reference"], cancellation_status="requested", arrangements_paused=True, payment_readiness_paused=True, cancellation_owner=person["Supervisor"], cancellation_next_action="Await source-bound supervisor confirmation; keep affected arrangements paused", cancellation_source_ref=row["_ref"])
        observations[selector]["budget_remaining_cents"] = available
        observations[selector]["current_decision_refs"] = decision_refs
        work.append(Work(selector, tuple(checks)))
    decisions = evaluate(work)
    return dict(mode="offline retained-source verification", source_run_id=sources.data["run_id"], source_binding={"path": str(sources.path.relative_to(sources.path.parents[3])) if sources.path.is_relative_to(sources.path.parents[3]) else sources.path.name, "sha256": sha256(sources.path.read_bytes()).hexdigest()}, batch_id=1, case_clock=sources.data["case_clock"], scope="Independence gate and observed initial facts only; not a financial-readiness verdict or schema snapshot", subjects={key: {**observations[key], **decisions[key]} for key in decisions})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--subject", action="append", required=True, help="Exact subject type:ID:revision; repeat for independent work")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.sources, args.subject)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        if args.output.read_text() != text:
            raise SourceError("Distinct existing verification preserved; use a new output path")
    else:
        with args.output.open("x") as stream:
            stream.write(text)
    print(args.output)


if __name__ == "__main__":
    main()
