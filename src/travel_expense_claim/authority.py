"""Recheck supplied claim reviews against current facts without creating replies.

The caller has already established evidence/entitlement and filtered review and
cancellation arrivals. This component checks current authority only. It grants
no dispatch, travel-arrangement, payment or closure authority.
"""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


ROLE_FIELDS = {"administration": "Administration reviewer", "budget_owner": "Budget owner",
               "supervisor": "Supervisor", "director": "Director"}
CONTEXT_FIELDS = ("Business purpose", "Client", "Schedule coverage", "Alternatives considered")


def _refs(value):
    if not value:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value).splitlines() if item.strip())


def _utc(value):
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str) and ("T" in value or " " in value):
        try:
            stamp = datetime.fromisoformat(value.removesuffix(" UTC").replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid UTC review/context timestamp") from None
    else:
        raise ValueError("A review/context timestamp needs a UTC date and time")
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("Review/context timestamp must be UTC")
    return stamp.astimezone(timezone.utc)


def _payload(row):
    return {key: value for key, value in row.items() if key not in {"_ref", "Arrival batch"}}


def recheck_authority(claim, trip, person, entitlement_cents, reviews, packets, cancellations, sources):
    """Return current claim approvals and reasons other replies cannot authorize it.

    ``packets`` is either native rows or a decision-ID mapping. ``cancellations``
    contains admitted processes from the cancellation reducer. The source reader
    supplies ``table('Budget')`` plus manifest ``data`` and ``files``. The full
    department/project/period ledger reference set is checked here; affordability
    and accepted-request reconciliation remain separate checks.
    """
    if entitlement_cents is not None and (type(entitlement_cents) is not int or entitlement_cents < 0):
        raise ValueError("Entitlement must be nonnegative integer cents or unknown")
    required = {role: person.get(field) for role, field in ROLE_FIELDS.items() if role != "director"}
    if entitlement_cents is not None and entitlement_cents > 100000:
        required["director"] = person.get(ROLE_FIELDS["director"])
    day = date.fromisoformat(sources.data["case_clock"])
    cutoff = datetime.combine(day + timedelta(days=1), time(), ZoneInfo(sources.data["case_timezone"]))
    group_fields = ("Department", "Project", "Budget period")
    budget = [row for row in sources.table("Budget")
              if tuple(row.get(field) for field in group_fields) == tuple(person.get(field) for field in group_fields)]
    budget_ids = [row.get("Ledger reference") for row in budget]
    budget_valid = bool(budget_ids) and all(budget_ids) and len(budget_ids) == len(set(budget_ids))
    identity_valid = (claim.get("employee") == person.get("Employee ID") == trip.get("Employee ID")
                      and claim.get("trip") == trip.get("Trip reference")
                      and claim.get("trip_revision") == trip.get("Trip revision"))
    costs = tuple(line["cost_id"] for line in claim["lines"])
    policy_version = sources.files["POLICY"]["source_version"]
    claim_source = str(claim.get("source_ref", "INITIAL")).split(":", 1)[0]
    version_ids = (claim_source, "RECEIPTS", "REGISTERS-PEOPLE", "REGISTERS-TRIPS", "REGISTERS-BUDGET")
    expected_versions = {policy_version}
    expected_versions.update(sources.files[key]["source_version"] for key in version_ids if key in sources.files)
    source_refs = {reference for reference in (claim.get("source_ref"), trip.get("_ref"), person.get("_ref"), "POLICY") if reference}
    source_refs.update(row["_ref"] for row in budget if row.get("_ref"))
    rejected = []

    def reject(row, reason, extra_refs=()):
        references = {ref for ref in (row.get("_ref"), *extra_refs) if ref}
        source_refs.update(references)
        rejected.append(dict(decision_id=row.get("Decision reference"), reason=reason,
                             source_refs=sorted(references)))

    packet_groups = defaultdict(list)
    for packet in packets.values() if isinstance(packets, Mapping) else packets:
        packet_groups[packet.get("Decision reference")].append(packet)

    relevant = []
    context_valid = True
    context_times = []
    for process in cancellations:
        if process.get("trip") != trip.get("Trip reference") or process.get("trip_revision") != trip.get("Trip revision"):
            continue
        if process.get("target_type") == "permit" and (process.get("permit"), process.get("permit_revision")) != (trip.get("Permit reference"), trip.get("Permit revision")):
            continue
        if process.get("status") not in {"requested", "confirmed"}:
            continue
        relevant.append(process)
        source_refs.update(process.get("source_refs", []))
        try:
            if not process.get("cancellation_id") or process.get("target_type") not in {"trip", "permit"}:
                raise ValueError("Undefined cancellation context")
            request_time = _utc(process.get("requested_time"))
            context_times.append(request_time)
            if process["status"] == "confirmed":
                context_times.append(_utc(process.get("confirmed_time")))
            if any(stamp >= cutoff for stamp in context_times):
                raise ValueError("Future cancellation context")
        except ValueError:
            context_valid = False
    cancellation_ids = {process["cancellation_id"] for process in relevant if process.get("cancellation_id")}
    latest_context = max(context_times, default=None)

    candidate_groups = defaultdict(list)
    for row in reviews:
        # Other subjects are not invalid imports merely because this claim is
        # being checked. Prior revisions of this same claim remain visible.
        if row.get("Subject reference") == claim["id"]:
            candidate_groups[row.get("Decision reference")].append(row)
    admitted = []
    for decision_id, deliveries in candidate_groups.items():
        row = deliveries[0]
        delivery_refs = [item.get("_ref") for item in deliveries if item.get("_ref")]
        source_refs.update(delivery_refs)
        if not decision_id or any(_payload(other) != _payload(row) for other in deliveries[1:]):
            reject(row, "Missing decision ID or conflicting payloads for one decision reference", delivery_refs)
            continue
        if row.get("Subject type") != "claim" or row.get("Revision") != claim["revision"] or isinstance(row.get("Revision"), bool):
            reject(row, "Wrong subject type or prior/stale claim revision", delivery_refs)
            continue
        options = packet_groups.get(decision_id, [])
        if not options or any(_payload(other) != _payload(options[0]) for other in options[1:]):
            reject(row, "Missing or ambiguous current review packet", delivery_refs)
            continue
        packet = options[0]
        packet_refs = [item.get("_ref") for item in options if item.get("_ref")]
        references = [*delivery_refs, *packet_refs]
        source_refs.update(packet_refs)
        if not identity_valid:
            reject(row, "Current claim/trip/directory identity conflict", references)
            continue
        expected = (person.get("Employee ID"), trip.get("Trip reference"), trip.get("Trip revision"),
                    trip.get("Permit reference"), trip.get("Permit revision"), costs)
        actual = (packet.get("Employee ID"), packet.get("Trip reference"), packet.get("Trip revision"),
                  packet.get("Permit reference"), packet.get("Permit revision"), _refs(packet.get("Expense references")))
        if actual != expected or isinstance(packet.get("Trip revision"), bool) or isinstance(packet.get("Permit revision"), bool):
            reject(row, "Packet employee/trip/permit/revision/expense identities do not match current evidence", references)
            continue
        if any(packet.get(field) != trip.get(field) for field in CONTEXT_FIELDS):
            reject(row, "Packet business purpose/client/coverage/alternatives are not current", references)
            continue
        versions = set(_refs(row.get("Source revisions")))
        stale_versions = {version for version in versions if version.startswith(("POL-", "SRC-")) and version not in expected_versions}
        if packet.get("Policy revision") != policy_version or not expected_versions <= versions or stale_versions:
            reject(row, "Missing, stale or conflicting policy/evidence source versions", references)
            continue
        if not budget_valid or set(_refs(packet.get("Budget record references"))) != set(budget_ids):
            reject(row, "Packet does not contain the complete current department/project/period budget ledger", references)
            continue
        if not context_valid or set(_refs(packet.get("Travel cancellation references"))) != cancellation_ids:
            reject(row, "Packet cancellation context is missing, stale, extra or unresolved", references)
            continue
        roles = _refs(row.get("Review roles"))
        valid_roles = roles and len(roles) == len(set(roles)) and all(role in required and required[role] and required[role] == row.get("Reviewer") for role in roles)
        if not valid_roles or (len(roles) > 1 and set(roles) != {"budget_owner", "supervisor"}):
            reject(row, "Wrong stable actor/role or prohibited role combination", references)
            continue
        outcome = row.get("Outcome")
        if outcome not in {"approve", "return", "reject"} or not row.get("Reason") or (outcome == "return" and not row.get("Repair requested")):
            reject(row, "Undefined outcome, missing reason or missing concrete return repair", references)
            continue
        try:
            stamp = _utc(row.get("Decision time (UTC)"))
            if stamp >= cutoff:
                raise ValueError("Future review reply")
            if latest_context is not None and stamp < latest_context:
                raise ValueError("Review predates the relevant cancellation request/confirmation")
        except ValueError as error:
            reject(row, str(error), references)
            continue
        admitted.append((stamp, outcome, roles, row, references))

    approved_roles = set()
    valid_ids = set()
    for role in required:
        candidates = [entry for entry in admitted if role in entry[2]]
        if not candidates:
            continue
        latest = max(entry[0] for entry in candidates)
        current = [entry for entry in candidates if entry[0] == latest]
        outcomes = {entry[1] for entry in current}
        if outcomes == {"approve"}:
            approved_roles.add(role)
            valid_ids.update(entry[3]["Decision reference"] for entry in current)
        else:
            for _, outcome, _, row, references in current:
                reject(row, "Conflicting current role outcomes" if len(outcomes) > 1 else "Current reviewer outcome is " + outcome, references)
    missing = sorted(set(required) - approved_roles)
    if entitlement_cents is None:
        missing.append("director_requirement_unknown")
    return dict(current=not missing and identity_valid and context_valid and budget_valid,
                valid_decision_ids=sorted(valid_ids), rejected_decisions=rejected,
                missing_roles=missing, source_refs=sorted(source_refs))
