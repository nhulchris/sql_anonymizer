#!/usr/bin/env python3
"""
Verification harness for the SQL Data Anonymizer — ICS 499 Assignment 2
Author: Chris Nhul

Programmatically checks every graded requirement by comparing the
original and anonymized SQL files. Generic: works on any input/output
pair produced by anonymize.py, not just the bundled test file.

Usage:
    python3 verify.py original.sql anonymized.sql
"""

import re
import sqlite3
import sys

from anonymize import (INSERT_RE, classify_column, parse_schemas,
                       process_insert, split_tuple_values)

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, ok, detail=""):
    results.append((PASS if ok else FAIL, name, detail))


def extract_rows(sql_text):
    """Yield (table, column, category, value) for every INSERT value,
    plus per-tuple ordering info for structural comparison."""
    schemas = parse_schemas(sql_text)
    rows = []
    pos = 0
    while True:
        m = INSERT_RE.search(sql_text, pos)
        if not m:
            break
        table = m.group(1).lower()
        columns = [c.strip().strip('`"').lower() for c in m.group(2).split(",")]
        # reuse the tokenizer by scanning tuples the same way anonymize does
        i = m.end()
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
                    values = [v.strip() for v in split_tuple_values(body)]
                    for col, val in zip(columns, values):
                        cat = schemas.get(table, {}).get(col)
                        rows.append((table, col, cat, val))
            elif ch == ";" and depth == 0:
                break
            i += 1
        pos = i
    return rows


def unquote(v):
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1].replace("''", "'")
    return None  # not a string literal


def main():
    orig_path, anon_path = sys.argv[1], sys.argv[2]
    orig_text = open(orig_path, encoding="utf-8").read()
    anon_text = open(anon_path, encoding="utf-8").read()

    orig_rows = extract_rows(orig_text)
    anon_rows = extract_rows(anon_text)

    # --- Structure: same tables, columns, value counts, positions -------
    check("Same number of INSERT values",
          len(orig_rows) == len(anon_rows),
          f"{len(orig_rows)} vs {len(anon_rows)}")
    check("Same table/column layout",
          [(r[0], r[1]) for r in orig_rows] == [(r[0], r[1]) for r in anon_rows])

    pairs = list(zip(orig_rows, anon_rows))

    # --- Non-PII values unchanged ---------------------------------------
    bad = [(o, a) for o, a in pairs if o[2] is None and o[3] != a[3]]
    check("Non-PII values unchanged (ids, prices, dates, products...)",
          not bad, f"{len(bad)} changed" if bad else "")

    # --- Every PII string literal actually changed ----------------------
    unchanged = [o for o, a in pairs
                 if o[2] and unquote(o[3]) is not None
                 and o[3] == a[3] and unquote(o[3]) not in ("", " ")]
    check("Every PII value replaced", not unchanged,
          f"{len(unchanged)} untouched" if unchanged else "")

    # --- No original PII leaks into the anonymized file -----------------
    # Word-boundary match on every original PII value AND its name tokens
    # (catches 'Maria Gonzalez' surviving in a comment, or an original
    # surname resurfacing inside a generated street name).
    leak_tokens = set()
    for o, _ in pairs:
        v = unquote(o[3])
        if not (o[2] and v):
            continue
        leak_tokens.add(v)
        if o[2] in ("full_name", "first_name", "last_name"):
            leak_tokens.update(v.split())
    leaked = sorted(
        t for t in leak_tokens
        if len(t) >= 2
        and re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", anon_text)
    )
    check("No original PII present anywhere in output (comments included)",
          not leaked, f"leaked: {leaked}" if leaked else "")

    # --- Consistent mapping: same original -> same replacement ----------
    mapping = {}
    inconsistent = []
    for o, a in pairs:
        if not o[2]:
            continue
        key = (o[2], o[3])
        if key in mapping and mapping[key] != a[3]:
            inconsistent.append(key)
        mapping[key] = a[3]
    check("Repeated values map consistently (incl. across tables)",
          not inconsistent, f"{inconsistent}" if inconsistent else "")

    # --- Distinct originals stay distinct (no merging) ------------------
    by_cat = {}
    for (cat, orig), repl in mapping.items():
        by_cat.setdefault(cat, {}).setdefault(repl, set()).add(orig)
    merged = [(c, r, o) for c, m in by_cat.items()
              for r, o in m.items() if len(o) > 1]
    check("Distinct originals get distinct replacements", not merged,
          f"{merged}" if merged else "")

    # --- Phone format preservation --------------------------------------
    bad_fmt = []
    for o, a in pairs:
        if o[2] == "phone" and unquote(o[3]) is not None:
            skel_o = re.sub(r"\d", "#", unquote(o[3]))
            skel_a = re.sub(r"\d", "#", unquote(a[3]))
            if skel_o != skel_a:
                bad_fmt.append((unquote(o[3]), unquote(a[3])))
    check("Phone formats preserved (punctuation skeleton identical)",
          not bad_fmt, f"{bad_fmt}" if bad_fmt else "")

    # --- Email shape ----------------------------------------------------
    bad_email = [unquote(a[3]) for o, a in pairs
                 if o[2] == "email" and unquote(a[3]) is not None
                 and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", unquote(a[3]))]
    check("Replacement emails are valid email shapes", not bad_email,
          f"{bad_email}" if bad_email else "")

    # --- Output is valid, executable SQL --------------------------------
    for label, text in (("original", orig_text), ("anonymized", anon_text)):
        try:
            conn = sqlite3.connect(":memory:")
            conn.executescript(text)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in tables}
            check(f"{label} file executes as valid SQL (sqlite3)", True,
                  f"row counts: {counts}")
        except sqlite3.Error as e:
            check(f"{label} file executes as valid SQL (sqlite3)", False, str(e))

    # --- Report ---------------------------------------------------------
    width = max(len(n) for _, n, _ in results)
    failures = 0
    for status, name, detail in results:
        line = f"[{status}] {name:<{width}}"
        if detail:
            line += f"  ({detail})"
        print(line)
        failures += status == FAIL
    print(f"\n{len(results) - failures}/{len(results)} checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
