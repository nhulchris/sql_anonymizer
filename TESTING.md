# Testing Evidence

ICS 499 — Assignment 2 (SQL Data Anonymization)
Author: Chris Nhul

## Test design

`original_test.sql` was written before the anonymizer, as a test
specification. It is a small retail database (customers, employees, orders,
support_tickets) where every graded requirement has a concrete case that
proves it:

| # | Test case in the file | Requirement it proves |
|---|---|---|
| 1 | `john.obrien@gmail.com` appears in customers, orders (twice), and support_tickets | Repeated-value consistency across tables |
| 2 | Maria Gonzalez is both a customer (split `fname`/`last_name` columns) and an employee (single `full_name` column), with the same email, phone, and address | Cross-table person consistency across different schema shapes |
| 3 | PII columns use varied names: `fname`/`last_name`/`full_name`, `email`/`email_address`/`contact_email`/`customer_email`, `phone`/`cell_phone`/`contact_phone`, `street_address`/`home_address`/`shipping_address` | Detection generalizes beyond one naming convention |
| 4 | Phones in four formats: `(612) 555-0143`, `612-555-0198`, `6125550172`, `+1-651-555-0111` | Format preservation |
| 5 | `O''Brien` (escaped quote inside a string literal) | Parser correctness |
| 6 | Multi-row INSERT (customers) and single-row INSERTs (employees) | Both INSERT syntaxes handled |
| 7 | Product names, prices, dates, statuses, IDs, foreign keys | Non-PII must pass through untouched |
| 8 | Two different customers both named 'John' | Same value maps consistently; distinct people stay distinct |
| 9 | Addresses as split columns (customers) and as one-line strings (employees, orders) | Component-wise address consistency |
| 10 | Ticket 9004 uses `INSERT INTO support_tickets VALUES (...)` with no column list | Columns resolved from CREATE TABLE order (the syntax used in the assignment spec's own example) |

## Automated verification

`verify.py` compares the original and anonymized files programmatically. It
is generic — it re-derives the schema and value positions from both files, so
it works on any input/output pair, not just the bundled test file. Final run:

```
$ python3 verify.py original_test.sql anonymized_test.sql
[PASS] Same number of INSERT values                                    (134 vs 134)
[PASS] Same table/column layout
[PASS] Non-PII values unchanged (ids, prices, dates, products...)
[PASS] Every PII value replaced
[PASS] No original PII present anywhere in output (comments included)
[PASS] Repeated values map consistently (incl. across tables)
[PASS] Distinct originals get distinct replacements
[PASS] Phone formats preserved (punctuation skeleton identical)
[PASS] Replacement emails are valid email shapes
[PASS] original file executes as valid SQL (sqlite3)                   (row counts: {'customers': 5, 'employees': 3, 'orders': 4, 'support_tickets': 4})
[PASS] anonymized file executes as valid SQL (sqlite3)                 (row counts: {'customers': 5, 'employees': 3, 'orders': 4, 'support_tickets': 4})

11/11 checks passed
```

Notable checks:

- **Validity is proven by execution, not inspection**: both files are loaded
  into an in-memory SQLite database and must produce identical table row
  counts.
- **The leak check is token-level**: it searches the entire output (comments
  included) for every original PII value *and* every individual name token,
  using lookaround boundaries so values beginning with punctuation
  (`(612) 555-0143`) are still caught.

## Bugs found and fixed during testing

Four real defects were caught during development — each one produced a fix,
a regression test case, and, where the harness had the same blind spot, a
hardened check.

**1. `product_name` classified as a person name.** The first name-detection
pattern matched any column ending in `_name`, so 'Wireless Mouse' became
'Kevin Jordan' in the orders table — a violation of the "non-PII unchanged"
requirement. Fix: full-name matching is restricted to person-type prefixes
(`customer_name`, `employee_name`, `full_name`, ...). Caught by a manual
spot-check diff; the automated "Non-PII values unchanged" check now guards
it.

**2. PII survived in SQL comments.** The original file's header comment
mentions specific test values; pass 2 only rewrites INSERT values, so those
survived into the output. The leak check failed with 17 hits. Fix: pass 3
sweeps free text with the established mappings, and the forbidden-token
screen was added so no *generated* value can contain an original PII token
either (Faker had generated a street containing a real surname from the
data).

**3. Word-boundary blind spot.** After fix 2, phones like `(612) 555-0143`
still survived in comments: regex `\b` does not match before `(`, so both
the sweep and the leak check silently skipped them. Fix: `(?<!\w) ... (?!\w)`
lookarounds in the sweep, the forbidden-token screen, and the verifier.

**4. INSERT statements without a column list were skipped entirely.** The
INSERT matcher required an explicit column list, but
`INSERT INTO customers VALUES (...)` — the exact syntax in the assignment's
own example — is legal SQL, and such statements passed through with their
PII intact. Caught by auditing the parser against the assignment spec. Fix:
the column list is now optional, falling back to the CREATE TABLE column
order; test case 10 covers it and confirms the no-column-list row still
receives the same consistent replacements as the rest of the file.

## Manual spot-checks

- diffed `original_test.sql` against `anonymized_test.sql` line by line:
  structure, whitespace, comments-minus-PII, and all non-PII values
  identical.
- Confirmed Maria Gonzalez's customer row and employee row agree on synthetic
  name, email, phone, and address — with the employee's one-line address
  decomposing to the same street/city/state/zip as the customer's split
  columns.
- Confirmed reproducibility: two runs with the fixed seed produce
  byte-identical output.
