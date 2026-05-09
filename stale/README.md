# Stale Modules

These files are from the original async/aiosqlite implementation and are **no longer used**. The active codebase uses synchronous SQLAlchemy in `grocery/db.py`.

## Contents

- `database.py` — Old async aiosqlite connection manager + schema DDL
- `repository.py` — Old async CRUD repository layer
- `test_obscura_cdp.py` — Obscura CDP probe (websocket-based AH GraphQL interception)
- `test_obscura_cdp2.py` — Second attempt at Obscura CDP probe

These are kept for reference only. Do not import from this directory.
