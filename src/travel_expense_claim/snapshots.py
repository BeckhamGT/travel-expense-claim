"""Validate source-bound batch state and write immutable UTF-8 artifacts.

This module checks representation, references, arithmetic and retained history.
It does not choose review, repair-queue or financial-completion policy. Native
record admission and source-grounded business decisions belong to the runner.
"""

import csv
from datetime import date, datetime, timedelta
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile


CSV_COLUMNS = ("claim_id", "revision", "trip_id", "status", "allowed_cents",
               "paid_cents", "balance_cents", "next_owner", "reason")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$")


class SnapshotError(ValueError):
    """A retained source, snapshot, chain or immutable write is inconsistent."""


def _require(condition, message):
    if not condition:
        raise SnapshotError(message)


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, UnicodeError, ValueError) as error:
        raise SnapshotError(f"Cannot read retained UTF-8 JSON {path}: {error}") from error


def _digest(path):
    try:
        return sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise SnapshotError(f"Missing or unreadable retained file {path}: {error}") from error


def _relative(path, base, *, within=None):
    _require(_nonempty(path), "A retained binding needs a relative path")
    relative = Path(path)
    _require(not relative.is_absolute() and not PureWindowsPath(path).is_absolute(),
             "Retained paths must be relative")
    resolved = (Path(base) / relative).resolve()
    if within is not None:
        _require(resolved.is_relative_to(Path(within).resolve()), "Retained path escapes its run directory")
    return resolved


def _utc_observation(value, checker):
    _require(isinstance(value, str) and checker.conforms(value, "date-time"),
             "Source observed_at must be an RFC 3339 UTC date-time")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    _require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0),
             "Source observed_at must be UTC")


def _rfc3339(value):
    # jsonschema's optional format extras are not installed in every runtime.
    # Register this explicitly so format validation never silently disappears.
    if not isinstance(value, str):
        return True
    if not _DATE_TIME.fullmatch(value):
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return False
    return stamp.tzinfo is not None


def _manifest(path, checker):
    manifest = _read_json(path)
    _require(isinstance(manifest, dict), "Source manifest must be an object")
    for field in ("run_id", "source_version", "case_clock"):
        _require(_nonempty(manifest.get(field)), "Source manifest needs " + field)
    try:
        date.fromisoformat(manifest["case_clock"])
    except ValueError as error:
        raise SnapshotError("Source case_clock must be a calendar date") from error
    entries = manifest.get("files")
    _require(isinstance(entries, list) and entries, "Source manifest needs file observations")
    files, urls = {}, set()
    required = {"source_id", "path", "sha256", "status", "error", "url", "locator", "observed_at", "source_version"}
    for entry in entries:
        _require(isinstance(entry, dict) and required <= entry.keys(), "Incomplete source manifest file entry")
        identity = entry["source_id"]
        _require(_nonempty(identity) and identity not in files, "Source IDs must be nonempty and unique")
        _require(_nonempty(entry["url"]) and entry["url"].startswith("https://") and _nonempty(entry["locator"]),
                 "Every source observation needs its native HTTPS URL and locator")
        _utc_observation(entry["observed_at"], checker)
        _require(entry["status"] in {"read", "unavailable"}, "Undefined source read status")
        if entry["status"] == "read":
            _require(entry["error"] is None and _nonempty(entry["source_version"]),
                     "Read source needs an observed version and no read error")
            _require(isinstance(entry["sha256"], str) and _HASH.fullmatch(entry["sha256"]),
                     "Read source needs an observed SHA-256")
            retained = _relative(entry["path"], path.parent, within=path.parent)
            _require(retained != path, "A source manifest cannot hash itself")
            _require(_digest(retained) == entry["sha256"], "Retained source hash mismatch: " + identity)
        else:
            _require(_nonempty(entry["error"]), "Unavailable source needs its actual access error")
            _require(all(entry[field] is None for field in ("path", "sha256", "source_version")),
                     "Unobtainable source path/hash/version must be null; retain partial reads separately")
        urls.add(entry["url"])
        files[identity] = entry
    _require(len(urls) == 5, "Manifest must cover all five native source URLs")
    return manifest, files


def _unique(rows, key, label):
    result = {}
    for row in rows:
        identity = row[key]
        _require(_nonempty(identity) and identity not in result, f"Duplicate or empty {label} ID: {identity}")
        result[identity] = row
    return result


def _cents(value, label, *, nullable=False):
    _require((value is None and nullable) or type(value) is int,
             label + " must be exact integer EUR cents" + (" or null" if nullable else ""))


def _semantic(snapshot, files):
    claims = _unique(snapshot["claims"], "claim_id", "claim")
    requests = _unique(snapshot["requests"], "request_id", "request")
    cancellations = _unique(snapshot["travel_cancellations"], "cancellation_id", "cancellation")
    issues = _unique(snapshot["issues"], "record_id", "issue")
    finance_ids = set(snapshot["admitted_event_ids"])
    cancellation_ids = set()
    for claim in claims.values():
        _require(type(claim["revision"]) is int and type(claim["trip_revision"]) is int,
                 "Claim and trip revisions must be integers")
        _unique(claim["lines"], "cost_id", "cost within claim")
        _cents(claim["allowed_cents"], "Claim allowed_cents", nullable=True)
        _cents(claim["paid_cents"], "Claim paid_cents")
        _cents(claim["balance_cents"], "Claim balance_cents", nullable=True)
        amounts = []
        for line in claim["lines"]:
            _cents(line["allowed_cents"], "Line allowed_cents", nullable=True)
            _require(bool(line["source_ids"]), "Every line needs retained source provenance")
            for reference in line["source_ids"]:
                identity = reference if reference in files else reference.split(":", 1)[0]
                _require(identity in files, "Line source ID does not resolve in manifest: " + reference)
                if line["status"] == "supported":
                    _require(files[identity]["status"] == "read", "Supported line cannot rely on unavailable source bytes")
            amounts.append(line["allowed_cents"])
        total = None if None in amounts else sum(amounts)
        _require(claim["allowed_cents"] == total, "Claim allowed_cents disagrees with its line amounts")
        obligation = claim.get("authorized_obligation_cents", total)
        _cents(obligation, "Claim authorized_obligation_cents", nullable=True)
        _require(obligation is None or obligation >= 0, "Authorized obligation cannot be negative")
        balance = None if obligation is None else obligation - claim["paid_cents"]
        _require(claim["balance_cents"] == balance, "Claim balance_cents must equal authorized obligation minus net paid, preserving null")
    for request in requests.values():
        _require(request["claim_id"] in claims, "Request refers to a missing claim")
        _require(type(request["revision"]) is int and request["revision"] <= claims[request["claim_id"]]["revision"],
                 "Request basis revision must refer to an observed claim revision")
        _cents(request["amount_cents"], "Request amount_cents")
    for process in cancellations.values():
        _require(type(process["trip_revision"]) is int and (process["permit_revision"] is None or type(process["permit_revision"]) is int),
                 "Cancellation target revisions must be integers")
        event_ids = set(process["admitted_cancellation_event_ids"])
        _require(not cancellation_ids & event_ids, "Cancellation event is admitted to more than one process")
        cancellation_ids.update(event_ids)
        _require(set(process["affected_claim_ids"]) <= claims.keys(), "Cancellation affected claim does not resolve")
        _require(set(process["original_request_ids"]) <= requests.keys(), "Cancellation original request does not resolve")
        for identity in process["original_request_ids"]:
            _require(requests[identity]["claim_id"] in process["affected_claim_ids"],
                     "Cancellation request must belong to an affected claim")
        _require(set(process["issue_record_ids"]) <= issues.keys(), "Cancellation issue_record_ids do not resolve")
        requested = datetime.fromisoformat(process["requested_at"].replace("Z", "+00:00").replace("z", "+00:00"))
        _require(requested.utcoffset() == timedelta(0), "Cancellation snapshot timestamps must be UTC")
        if process["status"] == "confirmed":
            confirmed = datetime.fromisoformat(process["confirmed_at"].replace("Z", "+00:00").replace("z", "+00:00"))
            effective = datetime.fromisoformat(process["effective_at"].replace("Z", "+00:00").replace("z", "+00:00"))
            _require(confirmed.utcoffset() == effective.utcoffset() == timedelta(0), "Cancellation snapshot timestamps must be UTC")
            _require(confirmed > requested and effective == confirmed,
                     "Cancellation confirmation must be later than request and effective at confirmation")
        if process["financial_status"] == "unresolved":
            _require(_nonempty(process["next_owner"]), "Unresolved cancellation consequence needs an owner")
    _require(not finance_ids & cancellation_ids, "Finance and Travel cancellation admitted event IDs must stay separate")
    return claims, requests, cancellations


def _chain(current, previous):
    _require(current["run_id"] == previous["run_id"], "Predecessor must belong to this run")
    _require(int(previous["batch_id"]) + 1 == int(current["batch_id"]), "Predecessor must be the immediately preceding batch")
    _require(set(previous["admitted_event_ids"]) <= set(current["admitted_event_ids"]), "Later state cannot erase admitted Finance events")
    unchanged_finance = set(previous["admitted_event_ids"]) == set(current["admitted_event_ids"])
    for collection, identity in (("claims", "claim_id"), ("requests", "request_id"), ("travel_cancellations", "cancellation_id")):
        old, new = ({row[identity]: row for row in data[collection]} for data in (previous, current))
        _require(old.keys() <= new.keys(), "Later state cannot erase observed " + collection)
        for key, row in old.items():
            if collection == "claims":
                _require(new[key]["revision"] >= row["revision"], "Current claim revision cannot move backwards")
                if unchanged_finance:
                    _require(new[key]["paid_cents"] == row["paid_cents"], "Unchanged admitted Finance history cannot change net paid")
            elif collection == "requests":
                _require(new[key]["claim_id"] == row["claim_id"] and new[key]["currency"] == row["currency"],
                         "Stable request cannot be rebound to another claim/currency")
                if row["status"] != "proposed":
                    _require(all(new[key][field] == row[field] for field in ("revision", "payee")),
                             "Established request cannot be rebound to another basis/payee")
                if unchanged_finance and row["status"] != "proposed":
                    _require(new[key]["amount_cents"] == row["amount_cents"], "Unchanged admitted Finance history cannot change request obligation")
            else:
                _require(all(new[key][field] == row[field] for field in ("target_type", "trip_id", "trip_revision", "permit_id", "permit_revision", "requested_at")),
                         "Admitted cancellation process target/initiation cannot change")
                _require(set(row["admitted_cancellation_event_ids"]) <= set(new[key]["admitted_cancellation_event_ids"]),
                         "Later state cannot erase admitted cancellation events")
                if row["status"] == "confirmed":
                    _require(new[key]["status"] == "confirmed" and new[key]["confirmed_at"] == row["confirmed_at"] and new[key]["effective_at"] == row["effective_at"],
                             "Admitted cancellation confirmation cannot change")


def validate_snapshot(snapshot, schema_path, sources_path, predecessor_path=None, *, snapshot_path=None):
    """Validate state and its complete retained predecessor chain; return ``None``.

    Bindings are resolved relative to each snapshot. If ``snapshot_path`` is not
    supplied, the assignment's ``sources.parent/batches/<batch-id>.json`` path
    is used. Original request revisions may precede the current claim revision.
    This validates no discretionary reviewer outcome or learner acceptance.
    """
    _canonical(snapshot)
    _require(isinstance(snapshot, dict), "Snapshot must be an object")
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as error:
        raise SnapshotError("Snapshot validation requires the jsonschema Python package") from error
    schema = _read_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SnapshotError("Invalid supplied snapshot schema: " + str(error)) from error
    checker = FormatChecker()
    checker.checks("date-time")(_rfc3339)
    validator = Draft202012Validator(schema, format_checker=checker)
    sources_path = Path(sources_path).resolve()
    manifest, files = _manifest(sources_path, checker)
    location = Path(snapshot_path).resolve() if snapshot_path is not None else sources_path.parent / "batches" / f"{snapshot.get('batch_id', '')}.json"
    current, seen, expected_predecessor = snapshot, set(), Path(predecessor_path).resolve() if predecessor_path is not None else None
    while True:
        errors = sorted(validator.iter_errors(current), key=lambda error: tuple(str(value) for value in error.absolute_path))
        if errors:
            error = errors[0]
            where = "/".join(map(str, error.absolute_path)) or "snapshot"
            raise SnapshotError(f"Schema violation at {where}: {error.message}")
        _require(re.fullmatch(r"[1-4]", current["batch_id"]) is not None, "Batch ID must be one of 1, 2, 3, 4")
        _require(current["run_id"] == manifest["run_id"], "Snapshot and source manifest run IDs disagree")
        binding = current["source_binding"]
        bound_source = _relative(binding["path"], location.parent, within=sources_path.parent)
        _require(bound_source == sources_path and bound_source != location, "source_binding must resolve to this run's sources.json, never itself")
        _require(binding["sha256"] == _digest(sources_path), "Source manifest binding hash mismatch")
        _semantic(current, files)
        predecessor = current["predecessor"]
        if current["batch_id"] == "1":
            _require(predecessor is None and expected_predecessor is None, "First batch predecessor must be null")
            break
        _require(predecessor is not None, "Later batch requires the immediately preceding retained snapshot")
        prior_path = _relative(predecessor["path"], location.parent, within=sources_path.parent)
        _require(prior_path != location and prior_path not in seen and prior_path != sources_path,
                 "Snapshot predecessor cannot hash itself or form a cycle")
        _require(expected_predecessor is None or prior_path == expected_predecessor, "Predecessor path does not match supplied predecessor")
        _require(_digest(prior_path) == predecessor["sha256"], "Predecessor snapshot hash mismatch")
        previous = _read_json(prior_path)
        errors = list(validator.iter_errors(previous))
        _require(not errors, "Predecessor does not conform to supplied snapshot schema")
        _require(re.fullmatch(r"[1-4]", previous["batch_id"]) is not None, "Invalid predecessor batch ID")
        _chain(current, previous)
        seen.add(location)
        current, location, expected_predecessor = previous, prior_path, None


def _canonical(data):
    try:
        return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SnapshotError("Snapshot must contain JSON-native finite values: " + str(error)) from error


def write_snapshot(path, data, schema_path, sources_path, predecessor_path=None):
    """Atomically create a validated sealed file; exact replay leaves it intact."""
    path = Path(path)
    _require(not path.is_symlink(), "A sealed snapshot path must not be a symlink")
    content = _canonical(data)
    validate_snapshot(data, schema_path, sources_path, predecessor_path, snapshot_path=path)
    if path.exists():
        _require(path.is_file() and path.read_bytes() == content, "Distinct sealed snapshot preserved; create a new run")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".snapshot-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # An exclusive hard-link publication is atomic and cannot overwrite
            # a file created by another writer between validation and publish.
            os.link(temporary, path)
        except FileExistsError:
            _require(path.is_file() and not path.is_symlink() and path.read_bytes() == content,
                     "Distinct sealed snapshot preserved; create a new run")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def claims_csv(snapshot):
    """Return the required nine-column CSV; unknown money is blank, zero is 0."""
    claims = _unique(snapshot["claims"], "claim_id", "claim")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for identity in sorted(claims):
        claim = claims[identity]
        for field in ("allowed_cents", "paid_cents", "balance_cents"):
            _cents(claim[field], field, nullable=field != "paid_cents")
        writer.writerow(["" if claim[column] is None else claim[column] for column in CSV_COLUMNS])
    return stream.getvalue()
