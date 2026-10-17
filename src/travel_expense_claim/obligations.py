"""Bind retained prepaid costs to their actual original reimbursement request.

This observes source links and confirmed net transfers.  It neither creates a
request nor treats an accepted, failed or promised transfer as settled money.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def _related(claim):
    value = claim.get("related_claims", claim.get("related_earlier_claims", ()))
    if isinstance(value, str):
        return set() if value.strip().lower() in {"", "none"} else {part.strip() for part in value.replace(",", "\n").splitlines() if part.strip()}
    return set(value or ())


def _identity(claim, line):
    amount = Decimal(str(line["gross"]))
    if not amount.is_finite():
        raise ValueError("A cost needs finite original gross")
    return (line["cost_id"], claim["employee"], claim["trip"], claim["trip_revision"], line["currency"], amount)


def _accepted_basis(request, versions):
    choices = [version for version in versions if version["id"] == request["claim_id"]]
    batch = request.get("accepted_arrival_batch")
    if batch is not None:
        choices = [version for version in choices if version["batch"] <= batch]
    elif len(choices) != 1:
        return None
    if not choices:
        return None
    return max(choices, key=lambda version: version["revision"])


def _earlier(first, second):
    """Only a strictly established original request protects its origin claim."""
    try:
        first_time = datetime.fromisoformat(first["accepted_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        second_time = datetime.fromisoformat(second["accepted_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        return first_time < second_time
    except (KeyError, ValueError, TypeError):
        return first.get("accepted_arrival_batch", float("inf")) < second.get("accepted_arrival_batch", 0)


def reconcile_prior_costs(claim, visible_versions, finance, evaluated_claims=None):
    """Return proved per-cost EUR exclusions and owned holds for ambiguous links.

    ``claim.related_claims`` names explicit earlier claim IDs. ``finance`` is the
    Finance reducer result. A single-cost original request has an unambiguous
    cost allocation; a multi-cost request needs an evaluation of the accepted
    version, per-line allowed cents and complete settlement. Partial aggregate
    settlement cannot be assigned to selected lines by guesswork.

    Callers keep total reviewed entitlement separately and subtract these proved
    exclusions only when calculating the new obligation. Any blocking finding
    prevents using an unknown allocation as permission to pay the cost again.
    """
    versions = list(visible_versions)
    evaluated = evaluated_claims or {}
    related = _related(claim)
    own_lines = {line["cost_id"]: line for line in claim["lines"]}
    findings, links, exclusions, original_ids, all_refs = [], [], {}, set(), {claim["source_ref"]}
    own_requests = [request for request in finance["requests"].values() if request["claim_id"] == claim["id"]]

    def finding(code, detail, refs, request=None):
        references = sorted(set(ref for ref in refs if ref))
        all_refs.update(references)
        findings.append({"code": code, "detail": detail,
                         "owner": request.get("finance_officer", "Finance") if request else "Finance",
                         "source_refs": references, "blocking": True,
                         "next_action": "Obtain an exact source-bound prior-cost/request allocation and Finance disposition before new payment readiness"})

    known_ids = {version["id"] for version in versions}
    for identity in sorted(related):
        if identity == claim["id"] or identity not in known_ids:
            finding("invalid_prior_claim_link", "Related earlier claim is missing or refers to this claim: " + identity, [claim["source_ref"]])

    candidates = {}
    observed_related = set()
    for request_id, request in finance["requests"].items():
        if request["claim_id"] == claim["id"]:
            continue
        basis = _accepted_basis(request, versions)
        if basis is None or (request.get("employee_id") is not None and request["employee_id"] != basis["employee"]):
            if request["claim_id"] in related:
                observed_related.add(request["claim_id"])
                finding("prior_cost_basis_unknown", "Original accepted request cannot be bound to one supplied claim version", [claim["source_ref"], *request.get("source_refs", ())], request)
            continue
        # A later claim containing the old cost cannot block the valid origin.
        if any(_earlier(own, request) for own in own_requests):
            continue
        overlap = own_lines.keys() & {line["cost_id"] for line in basis["lines"]}
        if basis["id"] in related:
            observed_related.add(basis["id"])
        for cost in overlap:
            source_line = next(line for line in basis["lines"] if line["cost_id"] == cost)
            refs = [claim["source_ref"], basis["source_ref"], *request.get("source_refs", ())]
            original_ids.add(request_id)
            if basis["id"] not in related:
                finding("unlinked_shared_cost", f"{cost} is already in accepted request {request_id}; no explicit earlier-claim link establishes a safe exclusion", refs, request)
                continue
            try:
                compatible = _identity(claim, own_lines[cost]) == _identity(basis, source_line)
            except (KeyError, ValueError, InvalidOperation):
                compatible = False
            if not compatible:
                finding("prior_cost_identity_conflict", f"{cost} does not match its original employee/trip/revision/currency/gross identity", refs, request)
                continue
            candidates.setdefault(cost, []).append((request_id, request, basis, refs))

    for identity in sorted((related & known_ids) - observed_related - {claim["id"]}):
        earlier = [version for version in versions if version["id"] == identity]
        if any(own_lines.keys() & {line["cost_id"] for line in version["lines"]} for version in earlier):
            finding("prior_cost_unsettled", "Linked earlier claim has no admitted accepted/settled request: " + identity,
                    [claim["source_ref"], *[version["source_ref"] for version in earlier]])

    for cost, matches in candidates.items():
        if len(matches) != 1:
            finding("prior_cost_allocation_ambiguous", f"{cost} is bound to more than one original accepted request",
                    [ref for _, _, _, refs in matches for ref in refs])
            continue
        request_id, request, basis, refs = matches[0]
        net = request["net_paid_cents"]
        obligation = request["current_obligation_cents"]
        if request.get("holds") or net < 0 or net > obligation:
            finding("prior_cost_finance_unresolved", f"Original request {request_id} has unresolved Finance facts or an overpayment", refs, request)
            continue
        if request.get("initial_obligation_cents", obligation) != obligation:
            finding("prior_cost_basis_changed", f"Original request {request_id} changed its authorized obligation; an explicit current cost allocation is required", refs, request)
            continue
        allocated = None
        if len(basis["lines"]) == 1:
            allocated = net
        else:
            assessment = evaluated.get(basis["id"])
            if assessment and assessment.get("revision") == basis["revision"] and net == obligation:
                amounts = {line["cost_id"]: line.get("calculation", {}).get("allowed_cents", line.get("allowed_cents"))
                           for line in assessment.get("lines", ())}
                source_costs = {line["cost_id"] for line in basis["lines"]}
                if set(amounts) == source_costs and all(type(value) is int and value >= 0 for value in amounts.values()) and sum(amounts.values()) == obligation:
                    allocated = amounts[cost]
            if allocated is None:
                finding("prior_cost_allocation_unknown", f"Aggregate request {request_id} does not prove a settled EUR allocation for {cost}", refs, request)
                continue
        if allocated:
            exclusions[cost] = allocated
            links.append({"cost_id": cost, "original_claim_id": basis["id"], "original_revision": basis["revision"],
                          "original_request_id": request_id, "excluded_cents": allocated, "source_refs": sorted(set(refs))})
            all_refs.update(refs)
        if net < obligation:
            finding("prior_cost_unsettled", f"Original request {request_id} still has {obligation - net} accepted cents unsettled; its cost cannot be dispatched again", refs, request)

    return {"exclusion_by_cost_cents": exclusions, "original_request_ids": sorted(original_ids),
            "links": links, "findings": findings, "source_refs": sorted(all_refs)}
