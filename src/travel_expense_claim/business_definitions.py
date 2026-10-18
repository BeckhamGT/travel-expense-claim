"""Reviewed business interpretations bound to an original interview export.

These records classify a previously undefined category or route a package gap.
They never supply a claim decision, Finance exception or financial event.
"""
from hashlib import sha256
from pathlib import Path
import re

from .monetary import KNOWN_CATEGORIES


def load_definitions(manifest_path, data):
    base = Path(manifest_path).resolve().parent
    documents, lines_by_id = {}, {}
    for entry in data.get('documents', []):
        identity = entry.get('source_id')
        if identity != 'INTERVIEW' or identity in documents:
            raise ValueError('Business definitions require one original INTERVIEW document binding')
        relative = entry.get('path', '')
        path = (base / relative).resolve()
        if (not relative or Path(relative).is_absolute() or not path.is_relative_to(base)
                or path == Path(manifest_path).resolve() or entry.get('status') != 'read'
                or entry.get('error') is not None or not entry.get('source_version')
                or not entry.get('locator') or not entry.get('url')):
            raise ValueError('Incomplete or unsafe original interview document binding')
        if sha256(path.read_bytes()).hexdigest() != entry.get('sha256'):
            raise ValueError('Original interview document hash mismatch')
        documents[identity] = entry
        lines_by_id[identity] = path.read_text(encoding='utf-8').splitlines()

    def statement(record):
        match = re.fullmatch(r'(INTERVIEW):line([1-9][0-9]*)', record.get('source_ref', ''))
        if not match or match[1] not in lines_by_id:
            raise ValueError('Definition must cite an exact bound original interview line')
        lines = lines_by_id[match[1]]
        number = int(match[2])
        if number > len(lines) or lines[number - 1] != record.get('statement'):
            raise ValueError('Definition excerpt does not match its original line')
        headers = [line for line in lines[:number - 1] if line.startswith('**')]
        if (record.get('speaker') != 'Travel Administration Lead' or not headers
                or not headers[-1].startswith('**Travel Administration Lead** · ')):
            raise ValueError('Definition must be an actual lead statement, not a learner prompt')
        return record['statement']

    definitions = data.get('business_definitions', {})
    categories = {}
    for record in definitions.get('category_classifications', []):
        category = record.get('category')
        if (not isinstance(category, str) or not category or category in KNOWN_CATEGORIES
                or category in categories or record.get('policy_category') != 'personal'):
            raise ValueError('Clarification may classify an undefined category as personal; it cannot override an eligible category')
        explicit = category + ' is classified as a personal expense under company policy, meaning it carries zero entitlement for reimbursement.'
        if not statement(record).casefold().startswith(explicit.casefold()):
            raise ValueError('Need explicit personal classification; tentative or unrelated text is insufficient')
        categories[category] = dict(record)
    route = definitions.get('missing_definition_route')
    if route is not None:
        text = statement(route)
        if (route.get('owner') != 'Exercise operator'
                or not text.startswith('The exercise operator owns missing definitions')
                or 'remains on hold and cannot be cleared with an exception.' not in text):
            raise ValueError('Missing-definition route must bind the operator ownership and hold rule')
        route = dict(route)
    return documents, categories, route
