"""Build source-bound full-process results; completion adoption is explicit.

All human replies and financial events come from retained native records. Preview
evaluates the actual supplied inputs without asserting learner acceptance. Seal
writes the same ordered observations as immutable schema snapshots after adoption.
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from .eligibility import assess_permission
from .independence import visible_at
from .recheck import claim_versions, inspect, _stamp
from .repair_queue import build_queue
from .snapshots import claims_csv, validate_snapshot, write_snapshot
from .verify_independence import Sources, SourceError


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False, default=str) + "\n").encode("utf-8")


def immutable(path, content):
    path = Path(path)
    data = content.encode("utf-8") if isinstance(content, str) else content
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise SourceError("Distinct sealed output preserved; use a new run: " + str(path))
    else:
        with path.open("xb") as stream:
            stream.write(data)


def _record_id(subject, revision, code, fact):
    payload = json.dumps([subject, revision, code, fact], ensure_ascii=False)
    return "ISS-" + sha256(payload.encode()).hexdigest()[:24]


def _claim_row(identity, observation, claim, accepted, person):
    paid = observation["finance"]["net_paid_cents"]
    allowed = observation["calculated_entitlement_cents"]
    disposition = observation["source_disposition"]
    clean_nonpayment = observation["clean_nonpayment"]
    issues = [item for item in observation["issues"] if item["blocking"]]
    obligation = observation["finance"]["current_obligation_cents"]
    if clean_nonpayment and disposition in {"withdrawn", "rejected"}:
        obligation = 0
    elif obligation is None:
        obligation = allowed
    balance = None if obligation is None else obligation - paid
    financial_agreement = (observation["current_recheck_supported"] and not issues
                           and allowed is not None and obligation == allowed and balance == 0
                           and (allowed == 0 or bool(observation["finance"]["request_ids"])))
    nonpayment_agreement = clean_nonpayment and not issues
    if disposition in {"withdrawn", "rejected"} and clean_nonpayment:
        status, owner = disposition, None
        reason = observation["disposition_reason"]
    elif issues:
        only_waiting = all(item["code"] == "current_approvals" for item in issues)
        has_return = any("return" in item["reason"] for item in observation["authority"]["rejected_decisions"])
        status = "pending" if only_waiting and not has_return else "held"
        owner, reason = issues[0]["owner"], "; ".join(dict.fromkeys(item["detail"] for item in issues))
        if any(item["code"] in {"finance_resolution", "settlement_after_cancellation", "overpayment", "obligation_mismatch"} for item in issues):
            owner = person["Finance officer"]
        elif issues[0]["code"] == "current_approvals":
            role_fields = {"administration":"Administration reviewer", "budget_owner":"Budget owner", "supervisor":"Supervisor", "director":"Director"}
            role = next((role for role in observation["authority"]["missing_roles"] if role in role_fields), "administration")
            owner = person[role_fields[role]]
    elif accepted and (financial_agreement or nonpayment_agreement):
        status, owner = ("closed-no-payment" if allowed == 0 else "closed-reimbursed"), None
        reason = "Known zero entitlement with no financial effect" if allowed == 0 else "Current approvals, entitlement, original obligation, net confirmed payment and required resolutions agree"
    elif financial_agreement or nonpayment_agreement:
        status, owner = "pending", "Learner"
        reason = "Source prerequisites observed; financial-completion conditions and delivery acceptance await learner choice 3"
    elif observation["finance"]["request_ids"]:
        status, owner = "pending", next(iter(observation["original_requests"].values()))["finance_officer"]
        reason = "Accepted obligation awaits " + ("authorized retry/settlement" if any(r["retry_needed"] for r in observation["original_requests"].values()) else "remaining confirmed settlement")
    else:
        status, owner = "ready", "Finance"
        reason = "Current review supported; local readiness only, no Finance acceptance or transfer invented"
    lines = []
    for line in observation["lines"]:
        amount = line["calculation"]["allowed_cents"]
        refs = list(dict.fromkeys([claim["source_ref"], *line["source_refs"], *line["calculation"]["source_refs"]]))
        lines.append(dict(cost_id=line["cost_id"], source_ids=refs,
            status="unresolved" if amount is None else "excluded" if amount == 0 else "supported",
            allowed_cents=amount, previously_paid_cents=line.get("previously_paid_cents", 0),
            reviewed_cents=line.get("reviewed_cents", amount),
            reason="Unknown evidence or monetary definition" if amount is None else "Previously settled linked cost excluded from the new obligation" if line.get("previously_paid_cents") else "Personal purchase excluded" if amount == 0 else "Receipt, settled employee proof and exact arithmetic retained",
            findings=line["calculation"]["findings"], exception=line["exception"],
            first_filed=line["first_filed"], filing_deadline=line["filing_deadline"]))
    return dict(claim_id=identity, revision=observation["revision"], trip_id=claim["trip"], trip_revision=claim["trip_revision"],
        employee_id=claim["employee"], status=status, lines=lines, allowed_cents=allowed, paid_cents=paid,
        authorized_obligation_cents=obligation, balance_cents=balance,
        decision_ids=observation["authority"]["valid_decision_ids"], next_owner=owner, reason=reason,
        source_disposition=disposition, source_ref=claim["source_ref"],
        source_financial_prerequisites_observed=financial_agreement or nonpayment_agreement,
        financial_completion_accepted=accepted and (financial_agreement or nonpayment_agreement),
        history=observation["revision_history"], prior_costs=observation["prior_costs"],
        permission=observation["permission"], current_review=observation["authority"],
        finance_resolution_required=observation["finance_resolution_required"],
        current_resolution_event_ids=observation["current_resolution_event_ids"],
        gross_paid_cents=observation["finance"]["paid_cents"], refunded_cents=observation["finance"]["refunded_cents"],
        material_changes=observation["material_changes"], trip_retired_for_future_arrangements=observation["trip_retired_for_future_arrangements"])


def build_run(manifest, completion_accepted=False):
    sources = Sources(manifest)
    versions = claim_versions(sources)
    identities = sorted({version["id"] for version in versions})
    observed_batches = [version["batch"] for version in versions]
    for name in ("Review ledger", "Finance activity", "Travel cancellations"):
        rows = sources.table(name)
        visible_at(rows, 1)  # Validate delivery metadata before selecting its maximum.
        observed_batches.extend(row["Arrival batch"] for row in rows)
    observations = inspect(manifest, identities, through_batch=int(max(observed_batches)))
    people = {row["Employee ID"]: row for row in sources.table("People")}
    trips = sources.table("Trips")
    all_reviews, all_packets = sources.table("Review ledger"), sources.table("Review packets")
    queue = build_queue(sources.data["run_id"], observations["batches"], versions, all_reviews, people)
    snapshots, summaries = [], []
    for batch in observations["batches"]:
        number = batch["batch_id"]
        visible = [version for version in versions if version["batch"] <= number]
        current = {identity: max((v for v in visible if v["id"] == identity), key=lambda v: v["revision"])
                   for identity in batch["claims"]}
        claims = [_claim_row(identity, batch["claims"][identity], current[identity], completion_accepted, people[current[identity]["employee"]]) for identity in sorted(current)]
        by_id = {claim["claim_id"]: claim for claim in claims}
        issues = []
        for identity, observed in batch["claims"].items():
            for item in observed["issues"]:
                issues.append(dict(record_id=_record_id(identity, observed["revision"], item["code"], item.get("cost_id", "") + item["detail"]),
                    subject_type="claim", subject_id=identity, revision=observed["revision"], code=item["code"],
                    cost_id=item.get("cost_id"), reason=item["detail"], owner=item["owner"], resolution_needed=item["next_action"],
                    blocking=item["blocking"], resolved_by=item["resolved_by"], source_ids=item["source_refs"]))
        requests = []
        finance = batch["finance_state"]
        for identity, request in sorted(finance["requests"].items()):
            basis = max((v for v in visible if v["id"] == request["claim_id"] and v["batch"] <= request["accepted_arrival_batch"]), key=lambda v: v["revision"])
            basis_observation = observations["batches"][request["accepted_arrival_batch"] - 1]["claims"][request["claim_id"]]
            status = ("held" if request["holds"] or request["retry_needed"] else "cancelled" if request["cancelled"]
                      else "cancel-pending" if request["cancellation_requested"] else "settled" if request["net_paid_cents"] == request["current_obligation_cents"]
                      else "accepted")
            requests.append(dict(request_id=identity, claim_id=request["claim_id"], revision=basis["revision"],
                amount_cents=request["current_obligation_cents"], payee=request["payee_id"], currency=request["currency"], status=status,
                decision_ids=basis_observation["authority"]["valid_decision_ids"], original_amount_cents=request["initial_obligation_cents"],
                paid_cents=request["paid_cents"], refunded_cents=request["refunded_cents"], net_paid_cents=request["net_paid_cents"],
                accepted_at=request["accepted_time"], accepted_arrival_batch=request["accepted_arrival_batch"],
                source_ids=request["source_refs"], admitted_event_ids=request["admitted_event_ids"],
                resolution_event_ids=request["resolution_event_ids"], retry_authorized=request["retry_authorized"], retry_needed=request["retry_needed"]))
        cancellations = []
        for process in batch["cancellation_processes"]["processes"]:
            target_versions = [v for v in visible if v["trip"] == process["trip"] and v["trip_revision"] == process["trip_revision"]]
            affected = sorted({v["id"] for v in target_versions})
            originals = []
            for request in requests:
                if any(v["id"] == request["claim_id"] and v["revision"] == request["revision"] for v in target_versions):
                    originals.append(request["request_id"])
            trip = next(row for row in trips if row["Trip reference"] == process["trip"] and row["Trip revision"] == process["trip_revision"])
            person = people[trip["Employee ID"]]
            no_costs = not target_versions and not originals and trip["First commitment date"] is None and not any(row["Trip reference"] == process["trip"] for row in sources.table("Merchant payments"))
            candidate_resolved = bool(affected) and all(by_id[identity]["source_financial_prerequisites_observed"] for identity in affected)
            resolved = bool(affected) and all(by_id[identity]["financial_completion_accepted"] for identity in affected)
            financial = "no-financial-effect" if no_costs else "resolved" if resolved else "unresolved"
            linked_issues = [item["record_id"] for item in issues if item["subject_id"] in affected and item["blocking"]]
            owner = person["Supervisor"] if process["status"] == "requested" else None if financial != "unresolved" else "Learner" if candidate_resolved else person["Finance officer"]
            if process["status"] == "requested":
                record_id = _record_id(process["cancellation_id"], process["trip_revision"], "confirmation", "")
                issues.append(dict(record_id=record_id, subject_type="travel_cancellation", subject_id=process["cancellation_id"],
                    revision=process["trip_revision"], code="cancellation_confirmation", reason="Valid employee request awaits exact supervisor confirmation; affected arrangements remain paused",
                    owner=person["Supervisor"], resolution_needed="Await supplied supervisor confirmation of this exact request and target", blocking=True, resolved_by=None, source_ids=process["source_refs"]))
                linked_issues.append(record_id)
            cancellations.append(dict(cancellation_id=process["cancellation_id"], target_type=process["target_type"], trip_id=process["trip"],
                trip_revision=process["trip_revision"], permit_id=process["permit"], permit_revision=process["permit_revision"], status=process["status"],
                admitted_cancellation_event_ids=process["admitted_cancellation_event_ids"], requested_at=_stamp(process["requested_time"]).isoformat().replace("+00:00", "Z"),
                confirmed_at=_stamp(process["confirmed_time"]).isoformat().replace("+00:00", "Z") if process["confirmed_time"] else None,
                effective_at=_stamp(process["confirmed_time"]).isoformat().replace("+00:00", "Z") if process["confirmed_time"] else None,
                affected_claim_ids=affected, original_request_ids=originals, financial_status=financial, next_owner=owner,
                reason="Complete sources show no commitment, employee-paid cost or reimbursement obligation" if no_costs else "Current cost disposition, claim review, net payment and required Finance resolution agree" if resolved else "Source financial prerequisites observed; learner financial-completion acceptance remains pending" if candidate_resolved else "Retain original request and money; current disposition/review/reconciliation requires the stated source evidence",
                issue_record_ids=sorted(set(linked_issues)), source_ids=process["source_refs"], arrangements_paused=True,
                trip_retired=process["target_type"] == "trip" and process["status"] == "confirmed",
                permit_retired=process["status"] == "confirmed" and process["permit"] is not None,
                source_financial_prerequisites_observed=candidate_resolved))
        for hold in batch["cancellation_processes"]["holds"]:
            issues.append(dict(record_id=_record_id(hold.get("event_id"), 1, hold["code"], str(hold["delivery"])),
                subject_type="travel_cancellation", subject_id=hold.get("cancellation_id"), revision=hold["delivery"].get("Trip revision"),
                code=hold["code"], reason=hold["reason"], owner=hold["owner"], resolution_needed=hold["next_action"], blocking=True, source_ids=hold["source_refs"]))
        reviews = visible_at(all_reviews, number)
        review_ids = {row["Decision reference"] for row in reviews}
        packets = [packet for packet in all_packets if packet["Decision reference"] in review_ids]
        permits = []
        for trip in trips:
            if not trip["Permit reference"]:
                continue
            person = people[trip["Employee ID"]]
            subject = dict(id=trip["Permit reference"], revision=trip["Permit revision"], employee=trip["Employee ID"], source_ref=trip["_ref"])
            permits.append(dict(permit_id=trip["Permit reference"], permit_revision=trip["Permit revision"], trip_id=trip["Trip reference"],
                trip_revision=trip["Trip revision"], assessment=assess_permission(subject, trip, person, reviews, packets, batch["cancellation_processes"], sources)))
        snapshot = dict(schema_version="travel-claim-snapshot/2", run_id=sources.data["run_id"], batch_id=str(number),
            predecessor=None if not snapshots else dict(path=f"{number-1}.json", sha256=sha256(encoded(snapshots[-1])).hexdigest()),
            source_binding=dict(path="../sources.json", sha256=sha256(sources.path.read_bytes()).hexdigest()),
            claims=claims, requests=requests, travel_cancellations=cancellations, admitted_event_ids=finance["admitted_event_ids"], issues=issues,
            finance_events=finance["admitted_events"], rejected_finance_events=finance["rejected_events"],
            replayed_finance_event_ids=finance["replayed_event_ids"], replayed_cancellation_event_ids=batch["cancellation_processes"]["replayed_event_ids"],
            decisions=reviews, review_packets=packets, permits=permits,
            budget_groups=list({tuple(obs["budget"]["group"]):obs["budget"] for obs in batch["claims"].values()}.values()),
            completion_choice_adopted=completion_accepted, case_clock=sources.data["case_clock"], case_timezone=sources.data["case_timezone"])
        snapshot = json.loads(encoded(snapshot))
        snapshots.append(snapshot)
        summaries.append(dict(batch_id=number, claims=len(claims), statuses=dict(Counter(claim["status"] for claim in claims)),
            known_allowed_cents=sum(claim["allowed_cents"] for claim in claims if claim["allowed_cents"] is not None), unknown_claims=sum(claim["allowed_cents"] is None for claim in claims),
            gross_paid_cents=sum(claim["gross_paid_cents"] for claim in claims), refunded_cents=sum(claim["refunded_cents"] for claim in claims), net_paid_cents=sum(claim["paid_cents"] for claim in claims),
            accepted_obligation_cents=sum(request["amount_cents"] for request in requests), request_count=len(requests), finance_event_count=len(finance["admitted_event_ids"]),
            budget_remaining_cents=snapshot["budget_groups"][0]["remaining_cents"]))
    return dict(snapshots=snapshots, queue=queue, summaries=summaries, observations=observations)


def render_report(result, manifest, *, preview=False):
    sources = Sources(manifest)
    latest = result["snapshots"][-1]
    rows = ["# Travel expense operations handoff", "", f"Run: `{sources.data['run_id']}`. Case clock: `{sources.data['case_clock']} {sources.data['case_timezone']}`.", "",
        "PREVIEW: real complete-source result for learner inspection; completion choice 3 is pending. No sealed operational snapshots or financial completion is claimed." if preview else "All supplied records and four arrival batches were processed. Business approvals, exceptions, bookings and money remain human-owned; all replies/outcomes are fixed supplied exercise facts.", "",
        "Inputs are bound in `sources.json`; native content, full searchable PDF extractions and all ten workbook CellData tabs are retained. Earlier source-review and choice-verification artifacts remain unchanged.", "",
        "| Batch | Claims | Net paid cents | Accepted obligation cents | Budget remaining cents | Status counts |", "|---|---:|---:|---:|---:|---|"]
    for item in result["summaries"]:
        rows.append(f"| {item['batch_id']} | {item['claims']} | {item['net_paid_cents']} | {item['accepted_obligation_cents']} | {item['budget_remaining_cents']} | {item['statuses']} |")
    rows += ["", "## Current claims and owned next work", "", "Unknown money remains null/blank; known zero is explicit. Balance uses the current authorized obligation, preserving overpayments and explicit non-payment dispositions. Prepaid costs are linked and excluded from a new obligation without erasing the original transfer.", "", "| Claim / revision | Trip | Status | Allowed / net paid / balance cents | Next owner | Reason |", "|---|---|---|---|---|---|"]
    for claim in latest["claims"]:
        values=" / ".join("unknown" if claim[key] is None else str(claim[key]) for key in ("allowed_cents","paid_cents","balance_cents"))
        rows.append(f"| {claim['claim_id']} / {claim['revision']} | {claim['trip_id']} | {claim['status']} | {values} | {claim['next_owner'] or '—'} | {claim['reason'].replace('|','/')} |")
    rows += ["", "## Independent cancellation processes", "", "| Process | Exact target | Business state | Financial consequence | Affected claims / original requests | Owner / next action |", "|---|---|---|---|---|---|"]
    for process in latest["travel_cancellations"]:
        target_id = process['trip_id'] if process['target_type'] == 'trip' else process['permit_id']
        target_revision = process['trip_revision'] if process['target_type'] == 'trip' else process['permit_revision']
        rows.append(f"| {process['cancellation_id']} | {process['target_type']} {target_id} / {target_revision} | {process['status']} | {process['financial_status']} | {process['affected_claim_ids']} / {process['original_request_ids']} | {process['next_owner'] or '—'} / {process['reason']} |")
    rows += ["", "## Repair queue and significant updates", "", "`repair-queue.json` preserves one item per subject/revision/missing fact or return reason and owner-based views. Local drafts have not been sent. Verification records cite supplied evidence; later source batches were fixed inputs, not responses caused by the drafts. A partial repair proves only its fact; queue resolution grants no approval or payment authority.", "", "| Batch | Subject / revision | Item | Change | Evidence / reason |", "|---|---|---|---|---|"]
    queue_items = {item['item_id']:item for item in result['queue']['items']}
    for change in result["queue"]["changes"]:
        item = queue_items[change['item_id']]
        rows.append(f"| {change.get('batch_id',change.get('batch'))} | {item['subject_id']} / {item['revision']} | {change.get('item_id','')} | {change.get('from',change.get('from_status',''))} → {change.get('to',change.get('to_status',''))} | {str(change.get('reason','')).replace('|','/')} |")
    rows += ["", "## Scope and verification boundaries", "", "The original interview is retained byte-for-byte under `interviews/`. Policy paragraphs 2–11 and 13–16 govern the arithmetic, evidence, decision bindings, original requests and cancellation consequences. Each line, issue, decision and financial event retains its exact source identity/locator in the batch result. The learner's captured choices and code/test evidence are mapped in `docs/coverage.md`.", "",
        "A complete business handoff may include legitimate owned unresolved cases: missing settled proof, applicable rates/caps, unknown categories, eligibility exceptions, returned work, missing discretionary replies or unresolved Finance effects. Implementation/verification gaps are separately recorded in the coverage map; they are not business holds. See README for validation, unchanged replay and safe resume commands. Sealed outputs change only in a new explicitly linked run.", ""]
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preview", "seal", "verify"))
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("snapshot.schema.json"))
    parser.add_argument("--output-dir", type=Path, help="Optional distinct preview directory; sealed outputs always remain under their source run")
    parser.add_argument("--completion-accepted", action="store_true", help="Use only after the learner's captured source-grounded choice 3")
    args = parser.parse_args()
    if args.mode == "seal" and not args.completion_accepted:
        parser.error("Sealing the final workflow requires the learner's actual completion choice; preview remains available")
    if args.output_dir is not None and args.mode != "preview":
        parser.error("--output-dir applies only to preview; sealed paths are bound to the source run")
    root = args.sources.resolve().parent
    result = build_run(args.sources, args.completion_accepted)
    if args.mode == "preview":
        preview_dir = args.output_dir or root / "preview"
        immutable(preview_dir / "summary.json", encoded(result["summaries"]))
        immutable(preview_dir / "repair-queue.json", encoded(result["queue"]))
        immutable(preview_dir / "report.md", render_report(result, args.sources, preview=True))
    else:
        previous = None
        for snapshot in result["snapshots"]:
            path = root / "batches" / (snapshot["batch_id"] + ".json")
            if args.mode == "verify":
                if not path.exists() or path.read_bytes() != encoded(snapshot):
                    raise SourceError("Missing or distinct sealed replay: " + str(path))
                validate_snapshot(snapshot, args.schema, args.sources, previous, snapshot_path=path)
            else:
                write_snapshot(path, snapshot, args.schema, args.sources, previous)
            previous = path
        for name, content in (("claims.csv", claims_csv(result["snapshots"][-1])), ("repair-queue.json", encoded(result["queue"])), ("report.md", render_report(result, args.sources)), ("summary.json", encoded(result["summaries"]))):
            if args.mode == "verify":
                if (root / name).read_bytes() != (content.encode() if isinstance(content,str) else content):
                    raise SourceError("Run output differs on unchanged replay: " + name)
            else:
                immutable(root / name, content)
    print(json.dumps(dict(mode=args.mode, run_id=root.name, batches=result["summaries"]), indent=2))


if __name__ == "__main__":
    main()
