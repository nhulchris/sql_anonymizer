#!/usr/bin/env python3
"""
SQL Data Anonymizer — ICS 499 Assignment 2
Author: Chris Nhul

Anonymizes PII (names, addresses, emails, phone numbers) in a SQL dump
file while preserving structure, formats, and value consistency.

Approach:
  1. Parse CREATE TABLE statements to learn each table's column order.
  2. Classify columns into PII categories by column-name patterns
     (fname, last_name, email_address, cell_phone, shipping_address, ...).
  3. Pass 1 collects every original PII value, so replacements can be
     screened against them (a synthetic value is rejected if it contains
     any real PII token — no original name may resurface inside, say, a
     generated street like '12 Williams Ave').
  4. Pass 2 walks every INSERT statement with a quote-aware tokenizer and
     replaces values in PII columns with realistic synthetic data (Faker).
     A global mapping table guarantees the same original value always
     becomes the same replacement — within a table and across tables.
     Names are mapped token-wise (first/last), so 'Maria' + 'Gonzalez'
     in one table and 'Maria Gonzalez' in another stay consistent.
     One-line addresses ('street, city, ST zip') are decomposed and
     mapped component-wise for the same reason.
     Phone numbers are format-preserving: digits are replaced, every
     punctuation character ((, ), -, +, space) stays where it was.
  5. Pass 3 sweeps the remaining free text (SQL comments) and replaces
     any mapped PII that appears there, using the same mappings.

Anonymization is one-way: mappings live only in memory for the run.

Usage:
    python3 anonymize.py input.sql [output.sql]
    (default output: <input>_anonymized.sql)

Dependencies: faker  (pip install faker)
"""

import random
import re
import sys

from faker import Faker

# Seeded for reproducible test runs; remove the seeds for varied output.
SEED = 499
fake = Faker("en_US")
Faker.seed(SEED)
rng = random.Random(SEED)


# ---------------------------------------------------------------------------
# 1. Column classification
# ---------------------------------------------------------------------------

# Order matters: 'email_address' must classify as EMAIL, not ADDRESS.
CATEGORY_PATTERNS = [
    ("email",      re.compile(r"e[-_]?mail", re.I)),
    ("phone",      re.compile(r"phone|mobile|cell|fax", re.I)),
    ("first_name", re.compile(r"^(f|first)[-_]?name$", re.I)),
    ("last_name",  re.compile(r"^(l|last)[-_]?name$|surname", re.I)),
    # Only person-prefixed *_name columns (product_name, file_name, etc.
    # are NOT PII and must pass through untouched).
    ("full_name",  re.compile(
        r"^(full|customer|employee|contact|person|user|member|client|"
        r"patient|student|owner|manager|agent)[-_]?name$|^name$", re.I)),
    ("address",    re.compile(r"addr|street", re.I)),
    ("city",       re.compile(r"city|town", re.I)),
    ("state",      re.compile(r"^state$|[-_]state$", re.I)),
    ("zip",        re.compile(r"zip|postal", re.I)),
]


def classify_column(col_name):
    """Return the PII category for a column name, or None if not PII."""
    for category, pattern in CATEGORY_PATTERNS:
        if pattern.search(col_name):
            return category
    return None


# ---------------------------------------------------------------------------
# 2. Consistent replacement generation
# ---------------------------------------------------------------------------

class Mapper:
    """Per-category caches: same original value -> same replacement.

    Also enforces two safety properties on every generated replacement:
      - it is unique within its category (distinct originals never merge)
      - it contains no original PII token (screened via a forbidden-token
        regex built in the collection pass)
    """

    def __init__(self):
        self.maps = {}           # {category: {original: replacement}}
        self.used = {}           # {category: set(replacements)}
        self.forbidden_re = None # regex of all original PII tokens
        self.sweep_subs = {}     # {original string: replacement} for pass 3

    def set_forbidden(self, tokens):
        tokens = {t for t in tokens if t and len(t) >= 2}
        if tokens:
            escaped = sorted((re.escape(t) for t in tokens),
                             key=len, reverse=True)
            # (?<!\w)/(?!\w) instead of \b: works for tokens that start or
            # end with a non-word char, e.g. '(612) 555-0143'
            self.forbidden_re = re.compile(
                r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)", re.I)

    def _clean(self, candidate):
        return not (self.forbidden_re and self.forbidden_re.search(candidate))

    def get(self, category, original, generator):
        cache = self.maps.setdefault(category, {})
        if original in cache:
            return cache[original]
        used = self.used.setdefault(category, set())
        candidate = generator()
        for _ in range(200):
            if candidate not in used and self._clean(candidate):
                break
            candidate = generator()
        used.add(candidate)
        cache[original] = candidate
        return candidate


mapper = Mapper()

# 'street, city, ST 55555' or 'street, city, ST 55555-1234'
FULL_ADDR_RE = re.compile(
    r"^(?P<street>.+?),\s*(?P<city>[^,]+?),?\s+(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)$"
)


def _remember(original, replacement):
    """Record a string substitution for the free-text sweep (pass 3)."""
    if original != replacement:
        mapper.sweep_subs[original] = replacement
    return replacement


def replace_first_name(v):
    return _remember(v, mapper.get("first_name", v, fake.first_name))


def replace_last_name(v):
    return _remember(v, mapper.get("last_name", v, fake.last_name))


def replace_full_name(v):
    """Map token-wise so full names agree with first/last name columns."""
    parts = v.split()
    if len(parts) >= 2:
        first = replace_first_name(parts[0])
        last = replace_last_name(parts[-1])
        return _remember(v, f"{first} {last}")
    return _remember(v, mapper.get("first_name", v, fake.first_name))


def replace_email(v):
    return _remember(v, mapper.get("email", v, fake.email))


def replace_street(v):
    return _remember(v, mapper.get("address", v, fake.street_address))


def replace_city(v):
    return _remember(v, mapper.get("city", v, fake.city))


def replace_state(v):
    return mapper.get("state", v, fake.state_abbr)


def replace_zip(v):
    return _remember(v, mapper.get("zip", v, fake.zipcode))


def replace_address(v):
    """Handle both bare streets and full one-line addresses.

    A one-line address is decomposed and mapped component-wise so it stays
    consistent with tables that store street/city/state/zip separately.
    """
    m = FULL_ADDR_RE.match(v.strip())
    if m:
        street = replace_street(m.group("street"))
        city = replace_city(m.group("city"))
        state = replace_state(m.group("state"))
        zipc = replace_zip(m.group("zip"))
        return _remember(v.strip(), f"{street}, {city}, {state} {zipc}")
    return replace_street(v)


def _fake_phone_digits():
    """A plausible 10-digit US number: NXX-NXX-XXXX (N = 2-9)."""
    area = rng.randint(2, 9) * 100 + rng.randint(0, 99)
    exchange = rng.randint(2, 9) * 100 + rng.randint(0, 99)
    line = rng.randint(0, 9999)
    return f"{area:03d}{exchange:03d}{line:04d}"


def replace_phone(v):
    """Format-preserving: map the 10-digit core, keep punctuation and any
    country code exactly where they were in the original string."""
    digits = re.sub(r"\D", "", v)
    if len(digits) < 7:
        return v  # not a parseable phone; leave untouched
    prefix = digits[:-10] if len(digits) > 10 else ""      # e.g. leading '1'
    core = digits[-10:]
    new_core = mapper.get("phone", core, _fake_phone_digits)
    new_digits = iter(prefix + new_core)
    result = "".join(next(new_digits) if ch.isdigit() else ch for ch in v)
    return _remember(v, result)


REPLACERS = {
    "first_name": replace_first_name,
    "last_name": replace_last_name,
    "full_name": replace_full_name,
    "email": replace_email,
    "address": replace_address,
    "city": replace_city,
    "state": replace_state,
    "zip": replace_zip,
    "phone": replace_phone,
}


def collect_tokens(value, category, tokens):
    """Pass 1 helper: record the original-PII tokens a replacement must
    never contain."""
    if category in ("first_name", "last_name", "city"):
        tokens.add(value)
    elif category == "full_name":
        tokens.add(value)
        tokens.update(value.split())
    elif category == "address":
        tokens.add(value)
        m = FULL_ADDR_RE.match(value.strip())
        if m:
            tokens.update(m.group("street", "city", "zip"))
    elif category == "phone":
        tokens.add(value)
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 10:
            tokens.add(digits[-10:])
    elif category in ("email", "zip", "state"):
        tokens.add(value)


# ---------------------------------------------------------------------------
# 3. SQL parsing (quote-aware, handles '' escapes and nested parens)
# ---------------------------------------------------------------------------

CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+[`\"]?(\w+)[`\"]?\s*\((.*?)\)\s*;", re.I | re.S
)
# The column list is optional: 'INSERT INTO t VALUES (...)' uses the
# CREATE TABLE column order instead.
INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+[`\"]?(\w+)[`\"]?\s*(?:\(([^)]*)\))?\s*VALUES\s*", re.I
)


def parse_schemas(sql_text):
    """Map {table: {column: category}} from CREATE TABLE statements."""
    schemas = {}
    for table, body in CREATE_RE.findall(sql_text):
        columns = {}
        depth = 0
        current = []
        defs = []
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                defs.append("".join(current))
                current = []
            else:
                current.append(ch)
        defs.append("".join(current))
        for d in defs:
            tokens = d.strip().split()
            if not tokens:
                continue
            first = tokens[0].strip('`"').upper()
            if first in ("PRIMARY", "FOREIGN", "UNIQUE", "KEY", "CONSTRAINT",
                         "CHECK", "INDEX"):
                continue
            col = tokens[0].strip('`"')
            columns[col.lower()] = classify_column(col)
        schemas[table.lower()] = columns
    return schemas


def split_tuple_values(tuple_body):
    """Split '1, ''O''''Brien'', x' into raw value strings, respecting
    quotes ('' escapes) and nested parentheses."""
    values = []
    current = []
    in_quote = False
    depth = 0
    i = 0
    while i < len(tuple_body):
        ch = tuple_body[i]
        if in_quote:
            current.append(ch)
            if ch == "'":
                if i + 1 < len(tuple_body) and tuple_body[i + 1] == "'":
                    current.append("'")
                    i += 1  # escaped quote, still inside the string
                else:
                    in_quote = False
        elif ch == "'":
            in_quote = True
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            values.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    values.append("".join(current))
    return values


def transform_value(raw, category, handler):
    """Apply handler to one raw SQL value ('...' literal) if it is PII.
    handler(inner_string, category) -> replacement inner string."""
    if category is None:
        return raw
    stripped = raw.strip()
    if not (stripped.startswith("'") and stripped.endswith("'")):
        return raw  # NULL, numbers, etc. — leave untouched
    inner = stripped[1:-1].replace("''", "'")     # unescape
    replaced = handler(inner, category)
    escaped = replaced.replace("'", "''")         # re-escape
    # preserve any leading/trailing whitespace around the literal
    lead = raw[: len(raw) - len(raw.lstrip())]
    trail = raw[len(raw.rstrip()):]
    return f"{lead}'{escaped}'{trail}"


def process_insert(match, sql_text, schemas, handler):
    """Walk the VALUES section of one INSERT statement, applying handler
    to every PII value. Returns (rewritten_statement, end_index)."""
    table = match.group(1).lower()
    if match.group(2) is not None:
        columns = [c.strip().strip('`"').lower()
                   for c in match.group(2).split(",")]
    else:
        # no column list in the INSERT: use CREATE TABLE column order
        columns = list(schemas.get(table, {}).keys())
    categories = [schemas.get(table, {}).get(c) for c in columns]

    out = [sql_text[match.start(): match.end()]]
    i = match.end()
    in_quote = False
    depth = 0
    tuple_start = None
    while i < len(sql_text):
        ch = sql_text[i]
        if in_quote:
            if ch == "'":
                if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                    i += 1
                else:
                    in_quote = False
        elif ch == "'":
            in_quote = True
        elif ch == "(":
            if depth == 0:
                tuple_start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                body = sql_text[tuple_start + 1: i]
                raw_values = split_tuple_values(body)
                new_values = [
                    transform_value(v, categories[j], handler)
                    if j < len(categories) else v
                    for j, v in enumerate(raw_values)
                ]
                out.append("(" + ",".join(new_values) + ")")
        elif ch == ";" and depth == 0:
            out.append(";")
            return "".join(out), i + 1
        elif depth == 0:
            out.append(ch)  # commas/whitespace between tuples
        i += 1
    return "".join(out), i


def walk_inserts(sql_text, schemas, handler):
    """Apply handler across all INSERT statements; return rewritten text."""
    out = []
    pos = 0
    while True:
        match = INSERT_RE.search(sql_text, pos)
        if not match:
            out.append(sql_text[pos:])
            break
        out.append(sql_text[pos: match.start()])
        statement, end = process_insert(match, sql_text, schemas, handler)
        out.append(statement)
        pos = end
    return "".join(out)


def sweep_free_text(text):
    """Pass 3: replace mapped PII that appears outside INSERT values
    (e.g. inside SQL comments), longest original first. Also covers the
    SQL-escaped form of originals that contain quotes (O''Brien)."""
    subs = dict(mapper.sweep_subs)
    for orig, repl in list(subs.items()):
        if "'" in orig:
            subs[orig.replace("'", "''")] = repl.replace("'", "''")
    for orig in sorted(subs, key=len, reverse=True):
        pattern = re.compile(r"(?<!\w)" + re.escape(orig) + r"(?!\w)")
        text = pattern.sub(subs[orig].replace("\\", r"\\"), text)
    return text


def anonymize_sql(sql_text):
    schemas = parse_schemas(sql_text)

    # Pass 1: collect original PII so no replacement can contain it.
    tokens = set()
    walk_inserts(sql_text, schemas,
                 lambda v, cat: (collect_tokens(v, cat, tokens), v)[1])
    mapper.set_forbidden(tokens)

    # Pass 2: replace PII values inside INSERT statements.
    result = walk_inserts(sql_text, schemas,
                          lambda v, cat: REPLACERS[cat](v))

    # Pass 3: scrub mapped PII from comments / free text.
    return sweep_free_text(result)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    in_path = sys.argv[1]
    out_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else re.sub(r"\.sql$", "", in_path) + "_anonymized.sql"
    )
    with open(in_path, encoding="utf-8") as f:
        sql_text = f.read()
    result = anonymize_sql(sql_text)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)
    total = sum(len(m) for m in mapper.maps.values())
    print(f"Anonymized {in_path} -> {out_path}")
    for category, cache in sorted(mapper.maps.items()):
        print(f"  {category:11s}: {len(cache)} unique value(s) replaced")
    print(f"  total unique values mapped: {total}")


if __name__ == "__main__":
    main()
