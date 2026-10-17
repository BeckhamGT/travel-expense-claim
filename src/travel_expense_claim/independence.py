"""Allow work only after its own prerequisites and real dependencies are checked.

Shared file names, reviewer identities and departments are context, not edges.
Callers supply source-grounded checks for each required dependency domain.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Iterable


DOMAINS = frozenset({"evidence", "budget", "authority", "obligations"})


@dataclass(frozen=True)
class Check:
    domain: str
    satisfied: bool
    fact: str
    owner: str
    next_action: str
    source_refs: tuple[str, ...]

    def __post_init__(self):
        if self.domain not in DOMAINS:
            raise ValueError(f"Unknown dependency domain: {self.domain}")
        if not self.fact or not self.owner or not self.next_action or not self.source_refs:
            raise ValueError("A dependency check needs a fact, owner, action and source references")


@dataclass(frozen=True)
class Dependency:
    prerequisite: str
    reason: str
    source_ref: str


@dataclass(frozen=True)
class Work:
    key: str
    checks: tuple[Check, ...]
    dependencies: tuple[Dependency, ...] = ()


def evaluate(work: Iterable[Work]) -> dict[str, dict]:
    """Propagate only explicit, evidenced prerequisites, including unresolved cycles."""
    items = list(work)
    by_key = {item.key: item for item in items}
    if len(by_key) != len(items):
        raise ValueError("Duplicate subject/revision work key")
    results = {}

    def visit(key, path):
        if key in path:
            return {"may_continue": False, "holds": [{"domain": "dependency", "fact": "Cyclic prerequisite: " + " -> ".join((*path, key))}]}
        if key in results:
            return results[key]
        item = by_key[key]
        holds = [asdict(check) for check in item.checks if not check.satisfied]
        missing = DOMAINS - {check.domain for check in item.checks}
        for domain in sorted(missing):
            holds.append({"domain": domain, "fact": "Independence has not been demonstrated", "owner": "Administration", "next_action": "Supply a source-grounded dependency check", "source_refs": []})
        for dep in item.dependencies:
            if not dep.reason or not dep.source_ref:
                raise ValueError("A prerequisite needs a reason and a source reference")
            other = by_key.get(dep.prerequisite)
            if other is None or not visit(dep.prerequisite, (*path, key))["may_continue"]:
                holds.append({"domain": "dependency", "fact": dep.reason, "prerequisite": dep.prerequisite, "source_refs": [dep.source_ref], "owner": "Administration", "next_action": "Resolve or substantiate the prerequisite before continuing dependent work"})
        results[key] = {"may_continue": not holds, "holds": holds, "dependency_checks": [asdict(check) for check in item.checks]}
        return results[key]

    for key in by_key:
        visit(key, ())
    return results


def visible_at(rows: Iterable[dict], batch: int) -> list[dict]:
    """Filter arrival before joining; worksheet order and business time are irrelevant."""
    if type(batch) is not int or batch < 1:
        raise ValueError("Batch must be a positive integer")
    visible = []
    for row in rows:
        arrival = row.get("Arrival batch")
        if isinstance(arrival, bool) or arrival is None or Decimal(str(arrival)) != int(arrival) or int(arrival) < 1:
            raise ValueError("Missing or invalid arrival batch")
        if int(arrival) <= batch:
            visible.append(row)
    return visible


def cents(value) -> int:
    amount = Decimal(str(value)) * 100
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError("Expected exact integer EUR cents")
    return int(amount)


def budget_remaining(ledger: Iterable[dict], accepted: Iterable[dict]) -> int:
    """Opening allocation minus net settled and remaining prior/new commitments.

    Accepted entries use request_id/amount_cents. Exact redelivery has no extra
    effect; conflicting payloads or missing references cannot prove availability.
    """
    allocation = spent = remaining = 0
    allocation_found = False
    prior = {}
    references = set()
    for row in ledger:
        reference = row["Ledger reference"]
        if not reference or reference in references:
            raise ValueError("Missing or duplicate budget ledger reference")
        references.add(reference)
        value = cents(row["Allocation or commitment (EUR)"])
        if row["Entry type"] == "allocation":
            if value < 0:
                raise ValueError("Negative allocation")
            allocation_found = True
            allocation += value
        elif row["Entry type"] == "obligation":
            obligation = row["Obligation reference"]
            if not obligation or obligation in prior:
                raise ValueError("Missing or duplicate prior obligation")
            settled, refunded = cents(row["Settled (EUR)"]), cents(row["Refunded (EUR)"])
            if min(value, settled, refunded) < 0 or settled > value or refunded > settled:
                raise ValueError("Inconsistent prior budget obligation")
            prior[obligation] = value
            spent += settled - refunded
            remaining += value - settled
        else:
            raise ValueError("Undefined budget entry type")
    if not allocation_found:
        raise ValueError("Missing allocation; availability is unknown")
    requests = {}
    for event in accepted:
        request, amount = event["request_id"], event["amount_cents"]
        if not request or type(amount) is not int or amount <= 0:
            raise ValueError("Invalid accepted commitment")
        if request in requests and requests[request] != amount:
            raise ValueError("Conflicting accepted commitment")
        requests[request] = amount
    for request, amount in requests.items():
        if request in prior:
            if prior[request] != amount:
                raise ValueError("Accepted request conflicts with prior obligation")
        else:
            remaining += amount
    return allocation - spent - remaining
