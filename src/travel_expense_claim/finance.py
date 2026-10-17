"""Observe supplied Finance history without creating requests or declaring closure.

The caller filters arrival batches before calling.  A source acceptance establishes
the request binding; later claim revisions never replace its admitted transfers.
All amounts returned here are exact integer EUR cents, not reviewed entitlement.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


TYPES = frozenset({
    "accepted", "settled", "failed", "retry_authorized",
    "cancellation_requested", "cancelled", "adjustment", "refund", "resolution",
})
_ORDER = {name: i for i, name in enumerate((
    "accepted", "failed", "retry_authorized", "settled", "cancellation_requested",
    "cancelled", "adjustment", "refund", "resolution",
))}


def _cents(value, *, positive=False):
    if value is None or isinstance(value, bool):
        raise ValueError("A monetary value is missing or is not numeric")
    try:
        amount = Decimal(str(value)) * 100
    except (InvalidOperation, ValueError):
        raise ValueError("A monetary value is not numeric") from None
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError("A monetary value must be exact integer EUR cents")
    result = int(amount)
    if result < 0 or (positive and result == 0):
        raise ValueError("A monetary value must be positive" if positive else "An obligation cannot be negative")
    return result


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("An event needs a UTC timestamp including its time")
    text = value.removesuffix(" UTC").replace("Z", "+00:00")
    if not ("T" in text or " " in text):
        raise ValueError("An event needs a UTC timestamp including its time")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("Invalid UTC event timestamp") from None
    # The native column explicitly names UTC, including exports without a suffix.
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("Finance event timestamps must be UTC")
    return stamp.astimezone(timezone.utc)


def _payload(row):
    """Compare immutable native values, excluding delivery/provenance only."""
    def freeze(value):
        if isinstance(value, dict):
            return tuple(sorted((key, freeze(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(freeze(item) for item in value)
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return Decimal(str(value))
        return value
    return freeze({key: value for key, value in row.items() if key not in {"Arrival batch", "_ref"}})


def summarize_finance(rows, people, claims_by_id, case_clock, case_timezone):
    """Reduce visible native Finance rows into requests, paid history and holds.

    ``people`` maps employee IDs to native People rows.  Each claim supplies its
    ``employee`` and may supply ``employee_by_batch`` for revision-bound employee
    identity.  Its latest entry available at the first acceptance's arrival is
    authoritative; the original accepted binding governs subsequent transfers.
    Invalid deliveries remain owned holds; they cannot erase admitted money.
    No eligibility, approval, dispatch, or financially-closed verdict is produced.
    """
    day = date.fromisoformat(case_clock) if isinstance(case_clock, str) else case_clock
    cutoff = datetime.combine(day + timedelta(days=1), time(), ZoneInfo(case_timezone))
    requests, admitted, holds, rejected, replayed = {}, {}, [], [], []
    claims = {key: {
        "request_ids": [], "admitted_event_ids": [], "paid_cents": 0,
        "refunded_cents": 0, "net_paid_cents": 0,
        "current_obligation_cents": None, "resolution_event_ids": [], "holds": [],
    } for key in claims_by_id}

    def hold(code, reason, row, refs, *, affected=()):
        claim_id, request_id = row.get("Claim reference"), row.get("Request reference")
        req = requests.get(request_id)
        claim = claims_by_id.get(claim_id, {})
        person = people.get(claim.get("employee"), {})
        item = {
            "code": code, "reason": reason, "event_id": row.get("Activity reference"),
            "claim_id": claim_id, "request_id": request_id,
            "owner": req["finance_officer"] if req else person.get("Finance officer") or "Finance",
            "next_action": "Obtain an explicit Finance resolution of this delivery; preserve admitted history",
            "source_refs": sorted(set(refs)),
        }
        holds.append(item)
        for key in set((claim_id, *affected, req["claim_id"] if req else None)):
            if key in claims:
                claims[key]["holds"].append(item)
        return item

    def reject(code, reason, row, refs):
        item = hold(code, reason, row, refs)
        rejected.append({key: item[key] for key in (
            "code", "reason", "event_id", "claim_id", "request_id", "source_refs",
        )})

    # Source row order is not an authorization.  Exact redelivery has one effect;
    # conflicting later payloads do not overwrite the earliest established one.
    groups = {}
    for index, row in enumerate(rows, 1):
        refs = [row.get("_ref") or f"Finance activity:delivery{index}"]
        event_id = row.get("Activity reference")
        if not isinstance(event_id, str) or not event_id.strip():
            reject("missing_event_id", "An immutable Finance event ID is required", row, refs)
            continue
        try:
            arrival_value = row.get("Arrival batch")
            arrival = int(arrival_value)
            if isinstance(arrival_value, bool) or Decimal(str(arrival_value)) != arrival or arrival < 1:
                raise ValueError
        except (TypeError, ValueError, InvalidOperation):
            reject("invalid_arrival", "A delivery needs a positive integer arrival batch", row, refs)
            continue
        groups.setdefault(event_id, []).append((arrival, row, refs[0]))

    pending = []
    for event_id, deliveries in groups.items():
        first_batch = min(entry[0] for entry in deliveries)
        earliest = [entry for entry in deliveries if entry[0] == first_batch]
        payloads = {_payload(entry[1]) for entry in earliest}
        if len(payloads) != 1:
            affected = tuple(entry[1].get("Claim reference") for entry in deliveries)
            for _, row, ref in earliest:
                hold("event_conflict", "Conflicting immutable payloads in the first observed batch have no established order", row, [entry[2] for entry in deliveries], affected=affected)
            continue
        row = earliest[0][1]
        original_payload = _payload(row)
        identical = [entry for entry in deliveries if _payload(entry[1]) == original_payload]
        refs = sorted({entry[2] for entry in identical})
        if len(identical) > 1:
            replayed.append(event_id)
        for _, other, ref in deliveries:
            if _payload(other) != original_payload:
                hold("event_conflict", "A conflicting immutable event redelivery cannot replace admitted history", other, [*refs, ref], affected=(row.get("Claim reference"),))
        try:
            stamp = _utc(row.get("Activity time (UTC)"))
            if stamp >= cutoff:
                raise ValueError("The Finance event occurs after the fixed case clock")
        except ValueError as error:
            reject("invalid_time", str(error), row, refs)
            continue
        pending.append((first_batch, stamp, _ORDER.get(row.get("Activity type"), 99), event_id, row, refs))

    # Arrival establishes visibility and immutable identity, not business order.
    # Replaying the visible facts in UTC order also rechecks references resolved
    # by late imports, without allowing older facts to overwrite newer state.
    for arrival, stamp, _, event_id, row, refs in sorted(pending, key=lambda item: (item[1], item[2], item[3])):
        kind = row.get("Activity type")
        claim_id, request_id = row.get("Claim reference"), row.get("Request reference")
        if kind not in TYPES:
            reject("unknown_activity_type", "Undefined Finance activity type", row, refs)
            continue
        if claim_id not in claims_by_id or not isinstance(request_id, str) or not request_id.strip() or not isinstance(row.get("Reason"), str) or not row["Reason"].strip():
            reject("invalid_binding", "A Finance event needs a known claim, explicit request ID and reason", row, refs)
            continue
        if row.get("Currency") != "EUR":
            reject("invalid_binding", "Finance events must bind the EUR reimbursement currency", row, refs)
            continue
        try:
            amount = _cents(row.get("Amount (EUR)"), positive=True) if kind in {"settled", "refund"} else None
            obligation = _cents(row.get("Obligation (EUR)"), positive=kind == "accepted") if kind in {"accepted", "adjustment", "resolution"} else None
            if kind not in {"settled", "refund"} and row.get("Amount (EUR)") is not None:
                raise ValueError("This activity type cannot supply a transfer amount")
            if kind not in {"accepted", "adjustment", "resolution"} and row.get("Obligation (EUR)") is not None:
                raise ValueError("This activity type cannot replace the accepted obligation")
            if kind != "refund" and row.get("Original activity reference") is not None:
                raise ValueError("Only a refund can bind an original settled transfer")
        except ValueError as error:
            reject("invalid_amount", str(error), row, refs)
            continue

        request = requests.get(request_id)
        if request is not None:
            expected = (request["claim_id"], request["finance_officer"], request["payee_id"], request["currency"])
            actual = (claim_id, row.get("Finance officer"), row.get("Payee ID"), row.get("Currency"))
            if actual != expected:
                reject("request_conflict", "The event conflicts with the original request's claim, Finance actor, payee or currency", row, refs)
                continue
            if stamp < _utc(request["accepted_time"]):
                reject("invalid_time", "An activity cannot precede its accepted request", row, refs)
                continue
        elif kind != "accepted":
            after_event = any(other[4].get("Activity type") == "accepted" and
                              other[4].get("Request reference") == request_id and
                              other[4].get("Claim reference") == claim_id and other[1] > stamp
                              for other in pending)
            reject("invalid_time" if after_event else "unmatched_request",
                   "An activity cannot precede its accepted request" if after_event else
                   "No admitted Finance acceptance establishes this request binding", row, refs)
            continue

        if kind == "accepted":
            if request is None:
                claim = claims_by_id[claim_id]
                if "employee_by_batch" in claim:
                    try:
                        versions = {int(batch): employee for batch, employee in claim["employee_by_batch"].items()
                                    if not isinstance(batch, bool) and Decimal(str(batch)) == int(batch) and int(batch) > 0}
                        if len(versions) != len(claim["employee_by_batch"]):
                            raise ValueError
                        available = [batch for batch in versions if batch <= arrival]
                        employee_ids = {versions[max(available)]} if available else set()
                    except (TypeError, ValueError, InvalidOperation, AttributeError):
                        reject("invalid_binding", "Claim employee history needs unambiguous positive arrival batches", row, refs)
                        continue
                else:
                    # Compatibility for callers supplying a fixed original basis.
                    employee_ids = set(claim.get("employee_history", ())) | {claim.get("employee")}
                candidates = [people[employee] for employee in employee_ids if employee in people and
                              people[employee].get("Finance officer") == row.get("Finance officer") and
                              people[employee].get("Payee ID") == row.get("Payee ID")]
                if len(candidates) != 1:
                    reject("invalid_binding", "Finance actor and payee do not match an evidenced claim employee", row, refs)
                    continue
                if claims[claim_id]["request_ids"]:
                    existing = claims[claim_id]["request_ids"][0]
                    reject("competing_request", f"Claim already has request {existing}; a replacement needs explicit Finance binding", row, refs)
                    continue
                request = requests[request_id] = {
                    "claim_id": claim_id, "employee_id": candidates[0]["Employee ID"],
                    "finance_officer": row["Finance officer"], "payee_id": row["Payee ID"], "currency": "EUR",
                    "accepted_time": stamp.isoformat().replace("+00:00", "Z"),
                    "initial_obligation_cents": obligation, "current_obligation_cents": obligation,
                    "paid_cents": 0, "refunded_cents": 0, "net_paid_cents": 0,
                    "status": "accepted", "retry_authorized": False, "retry_needed": False,
                    "cancellation_requested": False, "cancelled": False,
                    "admitted_event_ids": [], "resolution_event_ids": [], "source_refs": [],
                }
                claims[claim_id]["request_ids"].append(request_id)
            elif obligation != request["current_obligation_cents"] or request["cancelled"]:
                reject("conflicting_acceptance", "A new acceptance cannot replace an existing accepted/adjusted/cancelled obligation", row, refs)
                continue
        elif kind == "settled":
            if request["retry_needed"] and not request["retry_authorized"]:
                reject("retry_authorization_missing", "A failed request needs supplied Finance retry authorization before another attempt", row, refs)
                continue
            request["paid_cents"] += amount
            request["retry_needed"] = request["retry_authorized"] = False
            if request["cancelled"] or request["cancellation_requested"]:
                hold("settlement_after_cancellation", "A transfer arrived after Finance cancellation activity; retain the money and reconcile the original request", row, refs)
            request["status"] = "settled"
        elif kind == "refund":
            original_id = row.get("Original activity reference")
            original = admitted.get(original_id)
            if not original or original["type"] != "settled" or original["request_id"] != request_id or original["claim_id"] != claim_id or _utc(original["time"]) > stamp:
                reject("invalid_refund_link", "A refund must bind a previously admitted settled transfer on this exact request", row, refs)
                continue
            recovered = sum(event["amount_cents"] for event in admitted.values() if event["type"] == "refund" and event["original_event_id"] == original_id)
            if amount > original["amount_cents"] - recovered:
                reject("refund_exceeds_transfer", "Confirmed refunds cannot exceed the named transfer's unrecovered amount", row, refs)
                continue
            request["refunded_cents"] += amount
            request["status"] = "refund"
        elif kind == "adjustment":
            request["current_obligation_cents"] = obligation
            request["cancelled"] = request["cancellation_requested"] = False
            request["status"] = "adjustment"
        elif kind == "failed":
            request["retry_needed"], request["retry_authorized"] = True, False
            request["status"] = "failed"
        elif kind == "retry_authorized":
            if not request["retry_needed"] or request["cancelled"] or request["cancellation_requested"]:
                reject("invalid_retry", "Retry authorization needs a failed, uncancelled request", row, refs)
                continue
            request["retry_authorized"] = True
            request["status"] = "retry_authorized"
        elif kind == "cancellation_requested":
            request["cancellation_requested"] = True
            request["status"] = kind
        elif kind == "cancelled":
            request["current_obligation_cents"] = 0
            request["cancelled"], request["cancellation_requested"] = True, False
            request["status"] = kind
        elif kind == "resolution":
            if obligation != request["current_obligation_cents"]:
                reject("resolution_mismatch", "A resolution must agree with the current accepted obligation; it cannot silently adjust it", row, refs)
                continue
            request["resolution_event_ids"].append(event_id)
            request["status"] = kind

        request["net_paid_cents"] = request["paid_cents"] - request["refunded_cents"]
        request["admitted_event_ids"].append(event_id)
        request["source_refs"] = sorted(set(request["source_refs"]) | set(refs))
        admitted[event_id] = {
            "event_id": event_id, "type": kind, "claim_id": claim_id, "request_id": request_id,
            "time": stamp.isoformat().replace("+00:00", "Z"), "amount_cents": amount,
            "obligation_cents": obligation, "original_event_id": row.get("Original activity reference"),
            "source_refs": refs,
        }
        claims[claim_id]["admitted_event_ids"].append(event_id)

    for request_id, request in requests.items():
        item = claims[request["claim_id"]]
        for key in ("paid_cents", "refunded_cents", "net_paid_cents"):
            item[key] += request[key]
        item["current_obligation_cents"] = (item["current_obligation_cents"] or 0) + request["current_obligation_cents"]
        item["resolution_event_ids"].extend(request["resolution_event_ids"])
        request["balance_cents"] = request["current_obligation_cents"] - request["net_paid_cents"]
        if request["balance_cents"] < 0:
            row = {"Claim reference": request["claim_id"], "Request reference": request_id, "Activity reference": None}
            hold("overpayment", "Net confirmed reimbursement exceeds the current accepted obligation", row, request["source_refs"])
        request["holds"] = [item for item in holds if item["request_id"] == request_id]
    return {
        "claims": claims, "requests": requests, "admitted_events": list(admitted.values()),
        "admitted_event_ids": list(admitted), "holds": holds,
        "rejected_events": rejected, "replayed_event_ids": sorted(replayed),
    }
