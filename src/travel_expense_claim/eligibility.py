"""Assess permission from visible source facts without granting eligibility waivers.

Historical permission and present permission are distinct. A later cancellation
cannot turn a timely, valid paid arrangement into permit_unapproved. A Finance
exception is deliberately not interpreted here, and cannot authorize travel.
"""

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .authority import _utc, recheck_authority
from .independence import cents


def assess_permission(claim, trip, person, reviews, packets, cancellations, sources):
    """Return findings, historical permission and current arrangement permission.

    The caller filters arrivals before invoking this function. With a date-only
    first commitment, an approval or cancellation on that same local day leaves
    ordering unknown. For a trip explicitly having no commitment, historical
    permission describes its evidenced authority before any later cancellation.
    ``claim`` can be a real claim or a permit pseudo-subject for a no-claim trip.
    This assessment does not establish budget affordability or approve a booking.
    """
    reviews = list(reviews)
    processes = cancellations.get("processes", []) if isinstance(cancellations, Mapping) else list(cancellations)
    relevant = [process for process in processes
                if process.get("trip") == trip.get("Trip reference")
                and process.get("trip_revision") == trip.get("Trip revision")
                and process.get("status") in {"requested", "confirmed"}
                and (process.get("target_type") == "trip" or
                     (process.get("target_type") == "permit"
                      and (process.get("permit"), process.get("permit_revision")) ==
                      (trip.get("Permit reference"), trip.get("Permit revision"))))]
    references = {ref for ref in (claim.get("source_ref"), trip.get("_ref"), person.get("_ref"), "POLICY:paragraph4", "POLICY:paragraph15") if ref}
    for process in relevant:
        references.update(process.get("source_refs", []))
    findings = []

    def finding(code, detail):
        findings.append(dict(code=code, detail=detail, source_refs=sorted(references)))

    result = dict(findings=findings, historical_permission=False, arrangements_authorized=False,
                  current_permit_authority=None, source_refs=[])

    def finish():
        result["source_refs"] = sorted(references)
        # Complete provenance may become available after the finding was made.
        for item in findings:
            item["source_refs"] = sorted(references)
        return result

    if trip.get("International") is False:
        result.update(historical_permission=True, arrangements_authorized=not relevant)
        return finish()
    if trip.get("International") is not True:
        finding("permission_definition_unknown", "Trip does not explicitly establish domestic or international permission requirements")
        return finish()
    permit_id, permit_revision = trip.get("Permit reference"), trip.get("Permit revision")
    if not permit_id or permit_revision is None or isinstance(permit_revision, bool):
        finding("permit_unapproved", "International travel lacks an exact permit ID and revision")
        return finish()
    try:
        estimate_cents = cents(trip.get("Estimate (EUR)"))
        if estimate_cents < 0:
            raise ValueError("Negative permit estimate")
    except (ValueError, TypeError, ArithmeticError):
        estimate_cents = None
        finding("permit_estimate_unknown", "Permit estimate must be known nonnegative integer EUR cents")
    permit = dict(subject_type="permit", id=permit_id, revision=permit_revision,
                  employee=claim.get("employee"), trip=trip.get("Trip reference"),
                  trip_revision=trip.get("Trip revision"), lines=[], source_ref=trip.get("_ref"))
    current = recheck_authority(permit, trip, person, estimate_cents, reviews, packets, relevant, sources)
    result["current_permit_authority"] = current
    references.update(current["source_refs"])

    def before(instant):
        selected = []
        for row in reviews:
            if row.get("Subject reference") != permit_id:
                continue
            try:
                if _utc(row.get("Decision time (UTC)")) < instant:
                    selected.append(row)
            except ValueError:
                # The current authority result retains malformed replies. They
                # cannot demonstrate a historical approval either.
                continue
        return selected

    def check_at(instant):
        context = []
        for process in relevant:
            if _utc(process["requested_time"]) < instant:
                prior = dict(process)
                if process["status"] == "confirmed" and _utc(process["confirmed_time"]) >= instant:
                    prior.update(status="requested", confirmed_time=None)
                context.append(prior)
        authority = recheck_authority(permit, trip, person, estimate_cents, before(instant), packets, context, sources)
        references.update(authority["source_refs"])
        return authority, context

    try:
        requested_times = [_utc(process["requested_time"]) for process in relevant]
        first_request = min(requested_times, default=None)
        if first_request is None:
            uncancelled_authority = recheck_authority(permit, trip, person, estimate_cents, reviews, packets, [], sources)
        else:
            uncancelled_authority = recheck_authority(permit, trip, person, estimate_cents, before(first_request), packets, [], sources)
        references.update(uncancelled_authority["source_refs"])
        commitment = trip.get("First commitment date")
        if commitment is None:
            result["historical_permission"] = uncancelled_authority["current"]
            result["arrangements_authorized"] = current["current"] and not relevant
            if not uncancelled_authority["current"]:
                finding("permit_unapproved", "International permit has no complete applicable approval route")
            return finish()
        committed_on = date.fromisoformat(commitment)
        zone = ZoneInfo(sources.data["case_timezone"])
        start = datetime.combine(committed_on, time(), zone)
        end = datetime.combine(committed_on + timedelta(days=1), time(), zone)
        early, early_context = check_at(start)
        same_day_cancellation = any(start <= stamp < end for stamp in requested_times)
        historical = early["current"] and not early_context and not same_day_cancellation
        result["historical_permission"] = historical
        result["arrangements_authorized"] = historical and current["current"] and not relevant
        if historical:
            return finish()
        within_day, day_context = check_at(end)
        if uncancelled_authority["current"] and (same_day_cancellation or (within_day["current"] and not day_context)):
            finding("permit_ordering_uncertain", "Date-only first commitment and same-local-day permit/cancellation facts do not establish ordering")
        elif uncancelled_authority["current"] and not early_context:
            finding("late_permit", "The complete applicable permit route was approved only after the first commitment day")
        else:
            finding("permit_unapproved", "No complete active applicable permit route is established before the first commitment")
    except (ValueError, TypeError, KeyError) as error:
        finding("permission_timing_unknown", "Cannot establish permission chronology: " + str(error))
    return finish()
