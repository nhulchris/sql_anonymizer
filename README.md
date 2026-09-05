# SQL Data Anonymizer

ICS 499 — Assignment 2 (SQL Data Anonymization)
Author: Chris Nhul

A Python tool that anonymizes personally identifiable information (PII) in SQL
dump files. It replaces names, addresses, email addresses, and phone numbers
with realistic synthetic data while preserving the file's structure, value
formats, and internal consistency. Anonymization is one-way: the mapping from
real to synthetic values exists only in memory during a run and is never
written anywhere.

## Files

| File | Purpose |
|---|---|
| `anonymize.py` | The anonymizer |
| `verify.py` | Automated verification harness (checks every graded requirement) |
| `original_test.sql` | Original test database (4 tables, PII spread across them) |
| `anonymized_test.sql` | Anonymized output produced from the test file |
| `TESTING.md` | Testing evidence and bugs found during development |
| `requirements.txt` | Python dependencies |

## Dependencies

- Python 3.10+
- [Faker](https://faker.readthedocs.io/) — synthetic data generation

```
pip install -r requirements.txt
```

## Usage

```
python3 anonymize.py input.sql [output.sql]
```

If no output path is given, the tool writes `<input>_anonymized.sql`. To
verify a result:

```
python3 verify.py input.sql output.sql
```

## How it works

The tool makes three passes over the file.

**Pass 1 — schema analysis and PII collection.** CREATE TABLE statements are
parsed to learn each table's column order. Columns are classified into PII
categories by name pattern, so the tool generalizes to unseen schemas:
`fname`, `first_name` → first name; `email`, `email_address`,
`contact_email` → email; `phone`, `cell_phone`, `mobile` → phone;
`street_address`, `shipping_address`, `addr` → address; plus city, state, and
zip columns. Pattern order matters (`email_address` must classify as email,
not address), and name-column matching is restricted to person-type prefixes
so that `product_name` or `file_name` is never touched. This pass also
collects every original PII value into a forbidden-token set.

**Pass 2 — value replacement.** Every INSERT statement is walked with a
quote-aware tokenizer (handles `''` escapes like `O''Brien`, multi-row VALUES
lists, and nested parentheses). Values in PII columns are replaced with Faker
output through a global mapping table with three guarantees:

1. *Consistency* — the same original value always maps to the same
   replacement, within a table and across tables.
2. *Distinctness* — two different originals never map to the same
   replacement.
3. *No resurfacing* — a generated replacement is rejected if it contains any
   original PII token (Faker could otherwise invent a street named after a
   real surname in the data).

**Pass 3 — free-text sweep.** Mapped PII appearing outside INSERT values
(for example in SQL comments) is replaced using the same mappings, so a
comment mentioning a customer's email does not survive anonymization.

## Design decisions

**Column-name detection over value-pattern detection.** Emails and phones are
detectable by regex, but names and addresses are not reliably — 'Wireless
Mouse' and 'Maria Gonzalez' look identical to a pattern matcher. Driving
detection from the schema is more robust and makes cross-table consistency
straightforward. The tradeoff (PII hiding in unconventionally named columns
would be missed) is documented under Limitations.

**Token-wise name mapping.** First and last names are mapped independently,
and full-name columns are mapped token-by-token. A person stored as
`fname='Maria', last_name='Gonzalez'` in one table and
`full_name='Maria Gonzalez'` in another stays the same synthetic person in
both places.

**Component-wise address mapping.** One-line addresses
(`street, city, ST zip`) are decomposed and each component mapped separately,
so they stay consistent with tables that store street/city/state/zip in
separate columns.

**Format-preserving phones.** The 10-digit core is mapped; every
non-digit character stays exactly where it was. `(612) 555-0143` becomes
`(322) 938-9600`, `+1-651-555-0111` keeps its country code and dashes.
Generated numbers follow the NANP shape (area code and exchange never start
with 0 or 1).

**RFC-reserved email domains.** Replacement emails use `example.com/.org/.net`
(Faker's default), the domains reserved by RFC 2606 for exactly this purpose.
Using real domains (gmail.com, yahoo.com) would look marginally more
realistic but risks generating an address that belongs to a real person —
the wrong tradeoff for a privacy tool.

**Seeded randomness.** Faker and the phone generator are seeded (`SEED = 499`)
so runs are reproducible, which makes testing and grading deterministic.
Removing the seed gives varied output.

**Standard library parsing over a SQL parser dependency.** The tool needs
exact positional rewriting of INSERT values while leaving every other byte of
the file untouched. General-purpose SQL parsers (sqlparse) tokenize well but
do not round-trip a file byte-for-byte, so a purpose-built quote-aware
scanner was the safer choice, and it keeps the dependency footprint to just
Faker.

## Limitations

- Detection is schema-driven: PII stored in columns with unrelated names
  (e.g. an email inside a generic `notes` column) is only caught by the
  pass-3 sweep, and then only if the same value also appears in a PII column.
- The free-text sweep replaces whole mapped values and name tokens; novel PII
  that appears *only* in comments is not detected.
- Tested against MySQL/standard SQL dump syntax (`CREATE TABLE` +
  `INSERT INTO ... VALUES`); `UPDATE` statements and dialect-specific bulk
  formats (e.g. PostgreSQL `COPY`) are out of scope.
