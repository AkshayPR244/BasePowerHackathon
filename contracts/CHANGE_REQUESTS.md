# Contract change requests

The contract in `backend/app/contracts/` is frozen as of the scaffold commit. Full protocol: `docs/CONTRACTS.md`.

- Additive (optional field with a default, new model, new enum member nothing requires): make the change, regenerate types and mocks in the same commit, add one line to the Log.
- Breaking (rename, remove, type or unit change, new required field, changed meaning): add a PROPOSED entry below. Keep working around it. A human decides.

## Log

| Date | Lane | Change | Reason |
|---|---|---|---|

## Proposed (waiting for a human)

| Date | Lane | Proposed change | Reason | Affects |
|---|---|---|---|---|
