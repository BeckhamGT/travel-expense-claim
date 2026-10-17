"""Pure per-line arithmetic; evidence, exception authority and eligibility are external.

Amounts use Decimal throughout and each converted line is rounded half-up once.
An unresolved calculation returns ``allowed_cents=None``, never an invented zero.
Informational findings have ``blocking=False``; original cap findings survive a
caller-validated replacement. A replacement does not resolve an undefined cap
in this component: that would need an explicit additional source rule.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


KNOWN_CATEGORIES = frozenset({"transport", "conference", "lodging", "meals", "personal"})


def _decimal(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Expected a finite decimal number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Expected a finite decimal number") from error
    if not number.is_finite():
        raise ValueError("Expected a finite decimal number")
    return number


def _day(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected a local YYYY-MM-DD date")
    return date.fromisoformat(value)


def _text(value):
    text = format(value, "f")
    return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"


def _precision(*values):
    return max(50, sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values) + 10)


def calculate_line(*, gross, currency, category, units, destination, payment_date,
                   fx_rows, caps_rows, replacement_allowed=None):
    """Calculate one supported line using native table headings and ``_ref``.

    The caller must establish paid evidence and validate any Finance replacement's
    actor, claim/revision, cost and scope. This function grants no eligibility
    waiver, approval, request authority or closure. ``allowed_original`` remains
    available when only FX is unresolved; ``rate=None`` on a foreign personal
    purchase means conversion is unnecessary because its known entitlement is 0.
    """
    result = dict(allowed_cents=None, allowed_original=None, rate=None,
                  findings=[], source_refs=[])

    def finding(code, detail, *, blocking=True, **facts):
        result["findings"].append(dict(code=code, detail=detail, blocking=blocking, **facts))

    def refs(rows, complete=None):
        for row in rows:
            reference = row.get("_ref")
            if reference and reference not in result["source_refs"]:
                result["source_refs"].append(reference)
        if complete and complete not in result["source_refs"]:
            result["source_refs"].append(complete)

    try:
        gross_amount, unit_count = _decimal(gross), _decimal(units)
        paid_on = _day(payment_date)
        if gross_amount < 0 or unit_count <= 0 or unit_count != unit_count.to_integral_value():
            raise ValueError("Gross must be nonnegative and units a positive integer")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Currency must be an explicit three-letter code")
        replacement = None if replacement_allowed is None else _decimal(replacement_allowed)
        if replacement is not None and replacement < 0:
            raise ValueError("Replacement allowed amount must be nonnegative")
    except ValueError as error:
        finding("invalid_input", str(error))
        return result

    if category not in KNOWN_CATEGORIES:
        finding("unknown_category", "No supplied arithmetic rule for category: " + str(category))
        return result
    if category == "personal":
        result.update(allowed_cents=0, allowed_original="0", rate="1" if currency == "EUR" else None)
        finding("personal_excluded", "Personal purchases have known zero entitlement", blocking=False)
        return result

    ordinary_allowed = gross_amount
    if category in {"lodging", "meals"}:
        candidates = [row for row in caps_rows if row.get("Destination") == destination
                      and row.get("Category") == category and row.get("Currency") == currency]
        matching = []
        for row in candidates:
            try:
                start, end = _day(row.get("Effective from")), _day(row.get("Effective to"))
                if end < start:
                    raise ValueError("Cap effective period ends before it starts")
            except ValueError as error:
                refs([row])
                finding("invalid_cap", str(error))
                return result
            if start <= paid_on <= end:
                matching.append(row)
        refs(matching)
        if len(matching) != 1:
            refs(candidates, "REGISTERS-CAPS:complete-tab")
            finding("missing_cap" if not matching else "ambiguous_cap",
                    "Need exactly one applicable destination/category/currency/payment-date cap")
            return result
        try:
            cap = _decimal(matching[0].get("Amount per unit"))
            if cap < 0:
                raise ValueError("Cap cannot be negative")
        except ValueError as error:
            finding("invalid_cap", str(error))
            return result
        with localcontext() as context:
            context.prec = _precision(gross_amount, cap, unit_count)
            limit = cap * unit_count
            ordinary_allowed = min(gross_amount, limit)
        if ordinary_allowed < gross_amount:
            finding("cap_applied", "Ordinary allowed amount is limited by the applicable cap and units",
                    blocking=False, gross_original=_text(gross_amount), cap_total_original=_text(limit),
                    ordinary_allowed_original=_text(ordinary_allowed))

    allowed = ordinary_allowed if replacement is None else replacement
    if replacement is not None:
        finding("replacement_applied", "Caller-validated replacement controls the allowed original amount",
                blocking=False, ordinary_allowed_original=_text(ordinary_allowed),
                replacement_allowed_original=_text(replacement))
    result["allowed_original"] = _text(allowed)

    if currency == "EUR":
        rate = Decimal(1)
    else:
        candidates = [row for row in fx_rows if row.get("Currency") == currency]
        matching = []
        for row in candidates:
            try:
                rate_day = _day(row.get("Rate date"))
            except ValueError as error:
                refs([row])
                finding("invalid_rate", str(error))
                return result
            if rate_day == paid_on:
                matching.append(row)
        refs(matching)
        if len(matching) != 1:
            refs(candidates, "REGISTERS-FX:complete-tab")
            finding("missing_rate" if not matching else "ambiguous_rate",
                    "Need exactly one exact payment-date rate for the expense currency")
            return result
        try:
            rate = _decimal(matching[0].get("EUR per currency unit"))
            if rate <= 0:
                raise ValueError("Exchange rate must be positive")
        except ValueError as error:
            finding("invalid_rate", str(error))
            return result
    with localcontext() as context:
        context.prec = _precision(allowed, rate)
        converted = (allowed * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result["allowed_cents"] = int(converted * 100)
    result["rate"] = _text(rate)
    return result
