"""Observe visible Travel cancellation deliveries without inventing money or claims.

The caller filters by arrival batch.  Rebuilding from that cumulative visible set
also rechecks confirmations whose initiation arrived in a later delivery batch.
Only employee initiation and the matching directory supervisor confirmation can
establish a process.  Business cancellation never changes a Finance obligation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .verify_independence import before_clock


def _positive_integer(value):
    if value is None or isinstance(value, bool):
        raise ValueError("A positive integer is required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("A positive integer is required") from None
    if not number.is_finite() or number < 1 or number != number.to_integral_value():
        raise ValueError("A positive integer is required")
    return int(number)


def _identity(value):
    return isinstance(value, str) and bool(value.strip())


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("A complete UTC timestamp is required")
    text = value.removesuffix(" UTC").replace("Z", "+00:00")
    if "T" not in text and " " not in text:
        raise ValueError("A complete UTC timestamp is required")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("Invalid UTC timestamp") from None
    # The source column explicitly declares UTC even in an unsuffixed export.
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("Cancellation timestamps must be UTC")
    return stamp.astimezone(timezone.utc)


def _payload(row):
    def freeze(value):
        if isinstance(value, dict):
            return tuple(sorted((key, freeze(item)) for key, item in value.items()))
        if isinstance(value, (tuple, list)):
            return tuple(freeze(item) for item in value)
        if isinstance(value, bool):
            return ("boolean", value)
        if isinstance(value, (int, float, Decimal)):
            return ("number", str(Decimal(str(value)).normalize()))
        return value
    return freeze({key: value for key, value in row.items() if key not in {"Arrival batch", "_ref"}})


def reduce_cancellations(rows, people, trips, sources):
    """Return ``processes``, owned ``holds`` and exact ``replayed_event_ids``.

    Inputs use native ``Sources.table`` column names.  ``people`` may be its
    employee-ID mapping or its row list; ``trips`` is the complete trip row list.
    Times returned on a process preserve the validated native UTC spelling.
    Invalid deliveries remain in holds with their original payload and sources.
    A later conflicting delivery never replaces an earlier admitted payload.
    This function establishes no entitlement, request or financial completion.
    """
    directory = list(people.values()) if isinstance(people, dict) else list(people)
    trip_rows = list(trips.values()) if isinstance(trips, dict) else list(trips)
    holds, replayed, groups = [], [], {}

    def hold(code, reason, row, refs, person=None):
        if person is None:
            targets = [trip for trip in trip_rows if trip.get("Trip reference") == row.get("Trip reference") and trip.get("Trip revision") == row.get("Trip revision")]
            persons = [entry for entry in directory if len(targets) == 1 and entry.get("Employee ID") == targets[0].get("Employee ID")]
            if len(persons) == 1:
                person = persons[0]
        supervisor = person.get("Supervisor") if person else None
        holds.append({
            "code": code, "reason": reason,
            "event_id": row.get("Cancellation activity reference"),
            "cancellation_id": row.get("Cancellation reference"),
            "trip": row.get("Trip reference"),
            "owner": supervisor or "Travel operations",
            "next_action": "Resolve the stated cancellation fact with Travel operations and the applicable employee/supervisor; preserve admitted history",
            "source_refs": sorted(set(refs)), "delivery": dict(row),
        })

    for index, row in enumerate(rows, 1):
        ref = row.get("_ref") or f"Travel cancellations:delivery{index}"
        event_id = row.get("Cancellation activity reference")
        if not _identity(event_id):
            hold("missing_event_id", "An immutable cancellation activity ID is required", row, [ref])
            continue
        try:
            arrival = _positive_integer(row.get("Arrival batch"))
        except ValueError:
            hold("invalid_arrival", "A delivery needs a positive integer arrival batch", row, [ref])
            continue
        groups.setdefault(event_id, []).append((arrival, row, ref))

    candidates = []
    for event_id, deliveries in groups.items():
        earliest_batch = min(item[0] for item in deliveries)
        earliest = [item for item in deliveries if item[0] == earliest_batch]
        if len({_payload(item[1]) for item in earliest}) != 1:
            refs = [item[2] for item in deliveries]
            for _, row, _ in earliest:
                hold("event_conflict", "Conflicting first-batch payloads have no established immutable event", row, refs)
            continue
        row = earliest[0][1]
        payload = _payload(row)
        identical = [item for item in deliveries if _payload(item[1]) == payload]
        refs = sorted({item[2] for item in identical})
        if len(identical) > 1:
            replayed.append(event_id)
        for _, other, ref in deliveries:
            if _payload(other) != payload:
                hold("event_conflict", "A conflicting immutable redelivery cannot replace admitted history", other, [*refs, ref])
        if not _identity(row.get("Cancellation reference")) or not _identity(row.get("Business reason")):
            hold("invalid_binding", "A cancellation process ID and explicit business reason are required", row, refs)
            continue
        if row.get("Action") not in {"requested", "confirmed"} or row.get("Cancelled subject") not in {"trip", "permit"}:
            hold("invalid_action", "Only requested/confirmed actions on a trip or permit are defined", row, refs)
            continue
        try:
            stamp = _utc(row.get("Activity time (UTC)"))
            if not before_clock(stamp.strftime("%Y-%m-%d %H:%M:%S UTC"), sources):
                raise ValueError("Cancellation activity occurs after the fixed case clock")
        except ValueError as error:
            hold("invalid_time", str(error), row, refs)
            continue
        try:
            revision = _positive_integer(row.get("Trip revision"))
        except ValueError:
            hold("invalid_target", "The cancellation needs an exact positive trip revision", row, refs)
            continue
        matched = [trip for trip in trip_rows if trip.get("Trip reference") == row.get("Trip reference") and trip.get("Trip revision") == revision]
        if not _identity(row.get("Trip reference")) or len(matched) != 1:
            hold("invalid_target", "The exact trip revision is missing or ambiguous", row, refs)
            continue
        trip = matched[0]
        try:
            _positive_integer(trip.get("Trip revision"))
        except ValueError:
            hold("invalid_target", "The source trip revision is not a positive integer", row, refs)
            continue
        persons = [person for person in directory if person.get("Employee ID") == trip.get("Employee ID")]
        refs = sorted(set([*refs, *([trip["_ref"]] if trip.get("_ref") else [])]))
        if len(persons) != 1 or not _identity(trip.get("Employee ID")):
            hold("invalid_authority", "The trip employee must have one directory record", row, refs)
            continue
        person = persons[0]
        if person.get("_ref"):
            refs = sorted(set([*refs, person["_ref"]]))
        permit, permit_revision = row.get("Permit reference"), row.get("Permit revision")
        international = trip.get("International")
        try:
            if international is True:
                permit_revision = _positive_integer(permit_revision)
                source_permit_revision = _positive_integer(trip.get("Permit revision"))
                if not _identity(permit) or (permit, permit_revision) != (trip.get("Permit reference"), source_permit_revision):
                    raise ValueError
            elif international is False:
                if any(value is not None for value in (permit, permit_revision, trip.get("Permit reference"), trip.get("Permit revision"))) or row["Cancelled subject"] != "trip":
                    raise ValueError
            else:
                raise ValueError
        except ValueError:
            hold("invalid_target", "Trip/permit target and their independent revisions must exactly match the source", row, refs, person)
            continue
        actor = row.get("Acting employee or supervisor")
        if row["Action"] == "requested":
            if actor != person.get("Employee ID") or row.get("Initiation activity reference") is not None or row.get("Effective time (UTC)") is not None:
                hold("invalid_initiation", "Only the trip employee may initiate, with no initiation reference or effective time", row, refs, person)
                continue
        else:
            if not _identity(person.get("Supervisor")) or actor != person["Supervisor"]:
                hold("invalid_authority", "Only the trip employee's directory supervisor may confirm", row, refs, person)
                continue
            try:
                effective = _utc(row.get("Effective time (UTC)"))
                if effective != stamp or not _identity(row.get("Initiation activity reference")):
                    raise ValueError("Confirmation must reference initiation and take effect at its own UTC occurrence")
            except ValueError as error:
                hold("invalid_confirmation", str(error), row, refs, person)
                continue
        candidates.append((earliest_batch, stamp, event_id, row, refs, person))

    processes, requests = {}, {}
    for _, stamp, event_id, row, refs, person in sorted(candidates, key=lambda item: item[:3]):
        if row["Action"] != "requested":
            continue
        cancellation_id = row["Cancellation reference"]
        if cancellation_id in processes:
            hold("repeated_action", "One cancellation process has only one initiation; a different event cannot overwrite it", row, [*processes[cancellation_id]["source_refs"], *refs], person)
            continue
        process = {
            "cancellation_id": cancellation_id, "target_type": row["Cancelled subject"],
            "trip": row["Trip reference"], "trip_revision": int(row["Trip revision"]),
            "permit": row.get("Permit reference"),
            "permit_revision": int(row["Permit revision"]) if row.get("Permit revision") is not None else None,
            "requested_time": row["Activity time (UTC)"], "confirmed_time": None,
            "status": "requested", "source_refs": refs,
            "admitted_cancellation_event_ids": [event_id],
        }
        processes[cancellation_id] = process
        requests[event_id] = (process, stamp)

    # Resolve by explicit request identity, not by worksheet or delivery ordering.
    for _, stamp, event_id, row, refs, person in sorted(candidates, key=lambda item: item[:3]):
        if row["Action"] != "confirmed":
            continue
        initiation = requests.get(row.get("Initiation activity reference"))
        if not initiation:
            hold("orphan_confirmation", "The exact valid initiation has not arrived; recheck when it becomes visible", row, refs, person)
            continue
        process, requested_at = initiation
        expected = (process["cancellation_id"], process["target_type"], process["trip"], process["trip_revision"], process["permit"], process["permit_revision"])
        actual = (row["Cancellation reference"], row["Cancelled subject"], row["Trip reference"], row["Trip revision"], row.get("Permit reference"), row.get("Permit revision"))
        if actual != expected or stamp <= requested_at:
            hold("invalid_confirmation", "Confirmation must bind the exact request/process/target and occur strictly after initiation", row, [*process["source_refs"], *refs], person)
            continue
        if process["status"] == "confirmed":
            hold("repeated_action", "One cancellation process has only one confirmation; a different event cannot overwrite it", row, [*process["source_refs"], *refs], person)
            continue
        process.update(status="confirmed", confirmed_time=row["Activity time (UTC)"],
                       source_refs=sorted(set([*process["source_refs"], *refs])),
                       admitted_cancellation_event_ids=[*process["admitted_cancellation_event_ids"], event_id])

    return {"processes": [processes[key] for key in sorted(processes)],
            "holds": holds, "replayed_event_ids": sorted(replayed)}
