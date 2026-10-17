"""Build local fact-specific repair work from verified batch observations.

This module sends nothing and invents no replies. Its response records describe
source-bound verification, not conversations caused by generated drafts. Resolving
a factual queue item grants no approval, partial payment or financial closure.
"""

from collections import defaultdict
from datetime import date
from hashlib import sha256
import json

from .authority import ROLE_FIELDS, _refs
from .independence import visible_at


def _key(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return sha256(_key(value).encode("utf-8")).hexdigest()[:24]


def _sources(*groups):
    return sorted({value for group in groups for value in (group or []) if isinstance(value, str) and value})


def _line_sources(observation):
    return _sources([observation.get("source_ref")], *[
        _sources(line.get("source_refs"), line.get("calculation", {}).get("source_refs"))
        for line in observation.get("lines", [])])


def _financial_sources(observation):
    return _sources([observation.get("source_ref")], *[
        request.get("source_refs", []) for request in observation.get("original_requests", {}).values()])


def _proof(item, observation, review_rows, processes):
    """A missing issue alone is insufficient; require the relevant positive fact."""
    if observation.get("revision") != item["revision"]:
        return None
    code, cost_id = item["code"], item.get("cost_id")
    lines = [line for line in observation.get("lines", []) if cost_id is None or line.get("cost_id") == cost_id]
    line_codes = {"paid_evidence", "missing_rate", "ambiguous_rate", "invalid_rate", "missing_cap",
                  "ambiguous_cap", "invalid_cap", "unknown_category", "invalid_input", "late_filing"}
    if code in line_codes and cost_id is None and len(lines) > 1:
        proved = all(line.get("evidence_supported") is True for line in lines)
        if code != "paid_evidence":
            proved = proved and all(line.get("calculation", {}).get("allowed_cents") is not None for line in lines)
        return _line_sources(observation) if proved else None
    if code in {"approval_reply", "review_return"}:
        valid = set(observation.get("authority", {}).get("valid_decision_ids", []))
        missing = set(observation.get("authority", {}).get("missing_roles", []))
        approved = set()
        refs = []
        for row in review_rows:
            if (row.get("Decision reference") in valid and row.get("Subject type") == "claim"
                    and row.get("Subject reference") == item["subject_id"]
                    and row.get("Revision") == item["revision"] and row.get("Outcome") == "approve"):
                approved.update(set(_refs(row.get("Review roles"))) - missing)
                refs.extend([row.get("_ref")])
        if set(item.get("roles", [])) <= approved:
            return _sources([observation.get("source_ref")], refs)
        return None
    if code == "approval_requirement":
        if (observation.get("calculated_entitlement_cents") is not None
                and "director_requirement_unknown" not in observation.get("authority", {}).get("missing_roles", [])):
            return _line_sources(observation)
        return None
    for line in lines:
        calculation = line.get("calculation", {})
        blocking = {finding.get("code") for finding in calculation.get("findings", []) if finding.get("blocking", True)}
        proved = False
        if code == "paid_evidence":
            proved = line.get("evidence_supported") is True
        elif code in {"missing_rate", "ambiguous_rate", "invalid_rate"}:
            proved = calculation.get("rate") is not None and not blocking & {"missing_rate", "ambiguous_rate", "invalid_rate"}
        elif code in {"missing_cap", "ambiguous_cap", "invalid_cap", "unknown_category", "invalid_input"}:
            proved = calculation.get("allowed_original") is not None and code not in blocking
        elif code == "late_filing":
            try:
                proved = (line.get("evidence_supported") is True
                          and date.fromisoformat(line["first_filed"]) <= date.fromisoformat(line["filing_deadline"])
                          and "eligibility" in observation.get("full_recheck_steps", []))
            except (KeyError, ValueError, TypeError):
                proved = False
        if proved:
            return _sources([observation.get("source_ref")], line.get("source_refs"), calculation.get("source_refs"))
    if code in line_codes:
        return None
    if code == "finance_resolution" and observation.get("current_resolution_event_ids"):
        return _financial_sources(observation)
    if code == "overpayment" and observation.get("calculated_balance_cents") is not None and observation["calculated_balance_cents"] >= 0:
        return _financial_sources(observation)
    if (code == "obligation_mismatch" and observation.get("calculated_entitlement_cents") is not None
            and observation.get("finance", {}).get("current_obligation_cents") == observation["calculated_entitlement_cents"]):
        return _financial_sources(observation)
    if code == "shared_budget" and observation.get("budget", {}).get("sufficient") is True:
        return _sources(observation["budget"].get("source_refs"), *[
            charge.get("source_refs", []) for charge in observation["budget"].get("charges", [])])
    if (code == "shared_cost_obligation" and observation.get("shared_cost_request_ids") == []
            and "budget and obligations" in observation.get("full_recheck_steps", [])):
        return _financial_sources(observation)
    if code == "cancellation_pending":
        for process in processes:
            if (process.get("status") == "confirmed" and process.get("confirmed_time")
                    and process.get("trip") == item.get("trip_id")
                    and process.get("trip_revision") == item.get("trip_revision")
                    and item.get("cancellation_id") == process.get("cancellation_id")):
                return process["source_refs"]
        return None
    if code in {"finance_resolution", "overpayment", "obligation_mismatch", "shared_budget", "shared_cost_obligation"}:
        return None
    if observation.get("current_recheck_supported") is True and observation.get("full_recheck_steps"):
        return _sources(_line_sources(observation), _financial_sources(observation),
                        observation.get("authority", {}).get("source_refs"))
    return None


def build_queue(run_id, batches, versions, reviews, people):
    """Return ``items``, status-separated ``owner_views`` and run/batch ``changes``.

    ``batches`` is the ordered cumulative recheck output. Line-specific issues
    should carry ``cost_id`` and may carry ``requested_facts``. Current approval
    gaps expand into exact directory roles; admitted returns retain their own
    reason, affected fields and reviewer. A new claim revision supersedes old
    work, never resolves it using a reply for another version.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("A nonempty run ID is required")
    batches = list(batches)
    ids = [batch["batch_id"] for batch in batches]
    if any(type(value) is not int or value < 1 for value in ids) or ids != sorted(set(ids)):
        raise ValueError("Queue batches must be distinct positive integers in arrival order")
    directory = people if isinstance(people, dict) else {row["Employee ID"]: row for row in people}
    version_map = {(version["id"], version["revision"]): version for version in versions}
    reviews = list(reviews)
    items, changes = {}, []

    def transition(item, batch_id, status, reason, refs, *, superseded_by=None):
        old = item.get("status")
        event = dict(run_id=run_id, batch_id=batch_id, item_id=item["item_id"],
                     from_status=old, to_status=status, reason=reason, source_refs=_sources(refs))
        item.update(status=status, updated_in=dict(run_id=run_id, batch_id=batch_id))
        if superseded_by is not None:
            item["superseded_by"] = superseded_by
        item["history"].append(event)
        changes.append(event)

    def request(item, batch_id):
        item["requests"].append(dict(request_id=item["item_id"] + "-draft-" + str(len(item["requests"]) + 1),
            kind="local_draft", run_id=run_id, batch_id=batch_id, recipient=item["owner"], sent=False,
            subject_type=item["subject_type"], subject_id=item["subject_id"], revision=item["revision"],
            requested_facts=list(item["requested_facts"]), source_refs=list(item["source_refs"]),
            text=(f"Local draft for {item['owner']}. Subject: {item['subject_type']} {item['subject_id']} revision {item['revision']}. "
                  f"Missing fact or return reason: {item['missing_fact']}. Next action: {item['next_action']}. "
                  "Provide evidence bound to this subject and revision. This draft has not been sent and grants no approval, payment or closure authority.")))

    def observe(spec, batch_id, *, resolved_by=None):
        fact = {"code": spec["code"], "cost_id": spec.get("cost_id"), "roles": spec.get("roles", [])}
        if not fact["cost_id"] and not fact["roles"]:
            fact["detail"] = spec["missing_fact"]
        if spec["code"] == "review_return":
            fact["return_reason"] = spec["missing_fact"]
        identity = (spec["subject_type"], spec["subject_id"], spec["revision"], fact)
        item_id = "RQ-" + _hash(identity)
        is_new = item_id not in items
        if is_new:
            items[item_id] = dict(item_id=item_id, fact_key=_key(fact), **spec,
                status=None, created_in=dict(run_id=run_id, batch_id=batch_id), updated_in=None,
                requests=[], responses=[], history=[], superseded_by=None,
                resolution_scope="This factual repair only; no approval, partial payment or financial closure")
        item = items[item_id]
        item["source_refs"] = _sources(item["source_refs"], spec["source_refs"])
        for key in ("owner", "next_action", "requested_facts", "missing_fact"):
            item[key] = spec[key]
        if resolved_by:
            proof_refs = _sources(spec["source_refs"], _refs(resolved_by))
            if item["status"] != "resolved":
                item["responses"].append(dict(kind="evidence_verification", run_id=run_id, batch_id=batch_id,
                    subject_type=item["subject_type"], subject_id=item["subject_id"], revision=item["revision"],
                    proven_facts=list(item["requested_facts"]), source_refs=proof_refs,
                    basis="Explicit source-bound resolution; not a reply caused by this draft"))
                transition(item, batch_id, "resolved", "Explicit verified resolution for this fact/version", proof_refs)
        elif item["status"] != "open":
            transition(item, batch_id, "open", "New or reopened missing fact/return", spec["source_refs"])
            request(item, batch_id)
        return item_id

    for batch in batches:
        batch_id = batch["batch_id"]
        current = batch.get("claims", {})
        visible_reviews = visible_at(reviews, batch_id)
        review_by_id = {row["Decision reference"]: row for row in visible_reviews}
        cancellation = batch.get("cancellation_processes", {})
        processes = cancellation.get("processes", [])
        active, observations = set(), {}
        for subject_id, observation in current.items():
            revision = observation["revision"]
            version = version_map.get((subject_id, revision), {})
            person = directory.get(observation.get("employee") or version.get("employee"), {})
            observations[(subject_id, revision)] = observation
            for item in items.values():
                if item["subject_type"] == "claim" and item["subject_id"] == subject_id and item["revision"] < revision and item["status"] != "superseded":
                    transition(item, batch_id, "superseded", "A corrected revision needs its own evidence and reviews", [observation.get("source_ref")],
                               superseded_by=dict(revision=revision, source_ref=observation.get("source_ref")))
            returned_roles = set()
            for rejected in observation.get("authority", {}).get("rejected_decisions", []):
                row = review_by_id.get(rejected.get("decision_id"))
                if (not row or rejected.get("reason") != "Current reviewer outcome is return"
                        or row.get("Subject type") != "claim" or row.get("Subject reference") != subject_id
                        or row.get("Revision") != revision or not row.get("Repair requested")):
                    continue
                roles = sorted(set(_refs(row.get("Review roles"))))
                if not roles or any(role not in ROLE_FIELDS or person.get(ROLE_FIELDS[role]) != row.get("Reviewer") for role in roles):
                    continue
                returned_roles.update(roles)
                spec = dict(subject_type="claim", subject_id=subject_id, revision=revision, code="review_return", cost_id=None,
                    roles=roles, owner=row["Reviewer"], missing_fact=row["Reason"],
                    requested_facts=[row["Repair requested"]], affected_fields=list(_refs(row.get("Affected fields"))),
                    next_action=row["Repair requested"], source_refs=_sources(rejected.get("source_refs"), [row.get("_ref"), observation.get("source_ref")]),
                    origin_decision_ids=[row["Decision reference"]])
                active.add(observe(spec, batch_id))
            for issue in observation.get("issues", []):
                if issue["code"] == "current_approvals":
                    for role in observation.get("authority", {}).get("missing_roles", []):
                        if role in returned_roles:
                            continue
                        unknown = role == "director_requirement_unknown"
                        owner = person.get("Administration reviewer") if unknown else person.get(ROLE_FIELDS.get(role, ""))
                        spec = dict(subject_type="claim", subject_id=subject_id, revision=revision,
                            code="approval_requirement" if unknown else "approval_reply", cost_id=None, roles=[role],
                            owner=owner or issue["owner"], missing_fact="Establish reviewed entitlement and applicable director requirement" if unknown else "Missing current authorized " + role + " reply",
                            requested_facts=["Known reviewed entitlement and strict director threshold applicability" if unknown else "Exact-subject/revision reply from the directory's " + role],
                            next_action="Validate prerequisites, then obtain only the applicable current authorized reply", source_refs=_sources(issue.get("source_refs"), [observation.get("source_ref")]))
                        spec["rejected_decisions"] = [dict(rejected) for rejected in observation.get("authority", {}).get("rejected_decisions", [])
                            if rejected.get("decision_id") in review_by_id
                            and review_by_id[rejected["decision_id"]].get("Revision") == revision
                            and role in _refs(review_by_id[rejected["decision_id"]].get("Review roles"))]
                        active.add(observe(spec, batch_id))
                    continue
                cost_id = issue.get("cost_id")
                if cost_id is None:
                    matches = [line["cost_id"] for line in observation.get("lines", []) if line["cost_id"] in issue["detail"]]
                    if len(matches) == 1:
                        cost_id = matches[0]
                    elif len(observation.get("lines", [])) == 1:
                        cost_id = observation["lines"][0]["cost_id"]
                spec = dict(subject_type="claim", subject_id=subject_id, revision=revision, code=issue["code"],
                    cost_id=cost_id, roles=[], owner=issue["owner"], missing_fact=issue["detail"],
                    requested_facts=list(_refs(issue.get("requested_facts"))) or [issue["detail"]],
                    next_action=issue.get("next_action") or "Supply source-bound evidence for this specific fact and version",
                    source_refs=_sources(issue.get("source_refs"), [observation.get("source_ref")]),
                    trip_id=observation.get("trip") or version.get("trip"), trip_revision=version.get("trip_revision"))
                if issue["code"] == "cancellation_pending":
                    matches = [process for process in processes if process.get("trip") == spec["trip_id"]
                               and process.get("trip_revision") == spec["trip_revision"]
                               and set(issue.get("source_refs", [])) & {ref for ref in process.get("source_refs", []) if "CANCELLATION" in ref.upper()}]
                    spec["cancellation_id"] = issue.get("cancellation_id") or (matches[0]["cancellation_id"] if len(matches) == 1 else None)
                if issue.get("blocking", True) or issue.get("resolved_by"):
                    active.add(observe(spec, batch_id, resolved_by=issue.get("resolved_by")))
        for process in processes:
            if process.get("status") != "requested":
                continue
            owners = [person["Supervisor"] for person in directory.values() if person.get("_ref") in process.get("source_refs", [])]
            owner = owners[0] if len(set(owners)) == 1 else "Travel operations"
            spec = dict(subject_type="cancellation", subject_id=process["cancellation_id"],
                revision=process["permit_revision"] if process["target_type"] == "permit" else process["trip_revision"],
                code="supervisor_confirmation", cost_id=None, roles=["supervisor"], owner=owner,
                missing_fact="Exact supervisor confirmation of the initiated business cancellation",
                requested_facts=["Supervisor confirmation bound to the original request, process, target, revisions and business time"],
                next_action="Await the applicable supervisor's exact confirmation; keep affected arrangements paused",
                source_refs=_sources(process.get("source_refs")), trip_id=process["trip"],
                target_type=process["target_type"], permit_id=process.get("permit"))
            active.add(observe(spec, batch_id))
        for hold in cancellation.get("holds", []):
            delivery = hold.get("delivery", {})
            subject = hold.get("cancellation_id") or hold.get("event_id") or "unmatched-delivery-" + _hash(hold.get("source_refs", []))
            spec = dict(subject_type="cancellation", subject_id=subject,
                revision=delivery.get("Permit revision") if delivery.get("Cancelled subject") == "permit" else delivery.get("Trip revision"),
                code="cancellation_import:" + hold["code"], cost_id=None, roles=[], owner=hold.get("owner") or "Travel operations",
                missing_fact=hold["reason"], requested_facts=[hold["reason"]], next_action=hold.get("next_action") or "Obtain exact authorized cancellation evidence",
                source_refs=_sources(hold.get("source_refs")), event_id=hold.get("event_id"), imported_delivery=dict(delivery))
            active.add(observe(spec, batch_id))
        for item_id, item in items.items():
            if item_id in active or item["status"] != "open":
                continue
            proof = None
            if item["subject_type"] == "claim":
                observation = observations.get((item["subject_id"], item["revision"]))
                if observation is not None:
                    proof = _proof(item, observation, visible_reviews, processes)
            elif item["code"] == "supervisor_confirmation":
                process = next((process for process in processes if process["cancellation_id"] == item["subject_id"]
                                and process["status"] == "confirmed" and process.get("confirmed_time")
                                and process.get("target_type") == item.get("target_type")
                                and process.get("trip") == item.get("trip_id")
                                and process.get("permit") == item.get("permit_id")
                                and (process.get("permit_revision") if process["target_type"] == "permit" else process.get("trip_revision")) == item["revision"]), None)
                if process:
                    proof = process["source_refs"]
            elif item["code"].startswith("cancellation_import:"):
                process = next((process for process in processes if item.get("event_id") in process.get("admitted_cancellation_event_ids", [])), None)
                if process:
                    proof = process["source_refs"]
            if proof:
                item["responses"].append(dict(kind="evidence_verification", run_id=run_id, batch_id=batch_id,
                    subject_type=item["subject_type"], subject_id=item["subject_id"], revision=item["revision"],
                    proven_facts=list(item["requested_facts"]), source_refs=_sources(proof),
                    basis="Fresh applicable-version observation proves this fact; not a fabricated human reply"))
                item["source_refs"] = _sources(item["source_refs"], proof)
                transition(item, batch_id, "resolved", "Only this requested fact is now demonstrated by current evidence", proof)
    views = defaultdict(lambda: {"open": [], "resolved": [], "superseded": []})
    for item_id in sorted(items):
        item = items[item_id]
        views[item["owner"]][item["status"]].append(item_id)
    return dict(items=[items[item_id] for item_id in sorted(items)],
                owner_views={owner: views[owner] for owner in sorted(views)}, changes=changes)
