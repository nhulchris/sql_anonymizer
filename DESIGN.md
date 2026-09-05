# Design and Approach

ICS 499 — Assignment 2 (SQL Data Anonymization)
Author: Chris Nhul

## Problem framing

The tool must take a SQL dump containing real PII and produce an equivalent
dump where every name, address, email, and phone number is synthetic — while
an analyst using the anonymized file would notice nothing else changed. That
framing produces four hard requirements: replacements must look real,
identical originals must map to identical replacements everywhere in the
file, everything that is not PII must survive byte-for-byte, and the output
must still execute as SQL. It also rules out the easy approaches: deleting
or masking values fails realism, and rewriting the file through a SQL
parser/pretty-printer fails byte preservation.

## Key decision: schema-driven detection

The first design fork was how to *find* PII: scan values for patterns, or
read the schema. Value scanning works for emails and phones, which have
distinctive shapes, but not for names and addresses — a pattern matcher
cannot tell 'Maria Gonzalez' from 'Wireless Mouse' or a street address from
a product description. Since SQL dumps carry their own schema, the tool
parses CREATE TABLE statements and classifies each column by name into one
of nine categories: first name, last name, full name, email, phone, street
address, city, state, zip.

Two subtleties in the classification:

- Pattern order matters. `email_address` contains "address" and must be
  tested against the email pattern first.
- Name matching must be conservative. An early version matched any column
  ending in `_name`, which turned product names into people. The pattern now
  requires a person-type prefix (`customer_name`, `employee_name`,
  `full_name`, ...), accepting that an exotic person-column name could be
  missed rather than risking corruption of non-PII data.

## Consistency model

All replacement flows through one global `Mapper` holding per-category
dictionaries of original → replacement. Because the mapping is global
rather than per-table, cross-table consistency is not a special case — the
orders table asking for `john.obrien@gmail.com` simply gets the same cache
entry the customers table created.

Two structural problems need more than a flat dictionary:

**Names appear at two granularities.** One table stores
`fname='Maria', last_name='Gonzalez'`; another stores
`full_name='Maria Gonzalez'`. Mapping full names as opaque strings would
give the two rows unrelated synthetic identities. Instead, full names are
split and mapped token-wise through the same first-name and last-name
caches, so both representations resolve to the same synthetic person.

**Addresses appear at two granularities.** Split columns
(street/city/state/zip) versus one-line strings
(`'77 Lakeview Ave Apt 3B, Minneapolis, MN 55401'`). One-line addresses are
decomposed with a regex and each component is mapped through the component
caches, so both forms stay consistent.

The Mapper also enforces two properties on every generated value:

1. *Distinctness* — a replacement already used in a category is rejected, so
   two different people never collapse into one synthetic identity.
2. *No resurfacing* — before any replacement is generated, a first pass
   collects every original PII value into a forbidden-token set, and
   candidates containing any of those tokens are rejected. Without this,
   Faker occasionally invents output containing real data from the file
   (during testing it generated a street name containing an actual surname
   from the dataset).

## Format preservation

Phone numbers get special treatment because the requirement is to preserve
each value's format, not normalize it. The 10-digit core is extracted and
mapped (generated numbers follow the NANP rule that area code and exchange
start with 2–9); the replacement digits are then written back into the
original string one digit at a time, leaving every non-digit character —
parentheses, dashes, spaces, a `+1` country code — exactly where it was.

Emails use Faker's default RFC 2606 reserved domains (`example.com/.org/.net`)
rather than real providers. Real domains would look marginally more
authentic but could produce an address that actually belongs to someone —
the wrong failure mode for a privacy tool.

## Parsing: why not a SQL parser library

The INSERT rewriter is a hand-written scanner rather than sqlparse or
another parsing library. The reason is the preservation requirement:
general-purpose parsers tokenize and re-emit SQL, which does not guarantee a
byte-for-byte round trip of untouched content (whitespace, comments, casing,
multi-row layout). The scanner tracks exactly three things — quote state
(including `''` escapes, so `O''Brien` parses correctly), parenthesis depth,
and statement boundaries — and rewrites only the string literals in PII
columns, copying every other byte through unchanged. It handles both
multi-row and single-row INSERT syntax. This also keeps the dependency
footprint to Faker alone.

## Three-pass architecture

1. **Collect** — parse schemas, walk all INSERTs, gather every original PII
   value into the forbidden-token set.
2. **Replace** — walk all INSERTs again, substituting PII values through the
   Mapper.
3. **Sweep** — replace mapped PII appearing in free text (SQL comments)
   using the same mappings, with lookaround-based boundaries because `\b`
   fails on values that begin with punctuation like `(612) 555-0143`.

Pass 3 exists because pass 2 only touches INSERT values: a comment
mentioning a customer's email would otherwise survive anonymization intact.

## One-way guarantee

The original → replacement mapping lives only in program memory and is never
written to disk or embedded in the output. Reproducibility for grading comes
from seeding (`SEED = 499`), not from stored mappings; removing the seed
yields different synthetic data on every run.

## Verification as part of the design

`verify.py` is a standalone harness that re-derives schema and value
positions from an original/anonymized pair and checks every requirement
programmatically — including loading both files into SQLite and comparing
row counts, which proves validity by execution rather than inspection. It is
generic to any file pair, so the same evidence can be produced for an unseen
grading input. TESTING.md documents the full run and the three defects
testing caught.

## Known limitations

- Detection is schema-driven; PII in unconventionally named columns (an
  email inside a generic `notes` column) is caught only if the same value
  also appears in a PII column.
- Novel PII appearing *only* in comments is not detected.
- Scope is standard `CREATE TABLE` + `INSERT ... VALUES` dump syntax;
  `UPDATE` statements and dialect bulk formats (PostgreSQL `COPY`) are out
  of scope.
