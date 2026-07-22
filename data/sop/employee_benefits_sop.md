# SOP — Employee Benefits Roster Canonicalization

This Standard Operating Procedure is the grounding document retrieved by the Mapper and Transformer
agents (via RAG) when canonicalizing an employee-benefits roster.

## Column mapping guidance
- A single "Full Name" / "Name" / "Employee Name" column is typically `Last, First` and must be
  **split** into `first_name` and `last_name` (a Derived/Split mapping).
- `FN` almost always means First Name; `LN` / `Last Nm` means Last Name.
- `DoB`, `DOB`, `D.O.B` mean Date-Of-Birth.
- `Sex` and `Gndr` map to the canonical `gender` field.
- `Rel` / `Reln` map to `relationship`.

## Cell-value guidance
- **Gender**: `M`/`1`/`male` → `Male`; `F`/`0`/`female` → `Female`. Ambiguous tokens (e.g. `X`, `U`,
  blanks) must NOT be silently inferred — route to human review.
- **Dates**: accept `MM/DD/YYYY`, `YYYY-MM-DD`, `DD-MMM-YYYY`, `YYYY/MM/DD`; output strict ISO
  `YYYY-MM-DD`. Reject impossible dates (e.g. Feb 29 on a non-leap year) to review.
- **Relationship**: `Employee`/`EE`/`Subscriber` → `Self`; `Spouse`/`Husband`/`Wife` → `Spouse`;
  `Child`/`Son`/`Daughter`/`Dep`/`Dependent` → `Child`.

## Governance
- `date_of_birth`, `gender`, and `ssn` are **sensitive**; inferred mappings require a higher
  confidence and human confirmation before acceptance.
