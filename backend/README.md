# Backend (FastAPI)

Document Copilot API. Code lives in `app/`; config is **`backend/.env`** (copy from `.env.example`).

Python uses the **repo-root** `.venv` (uv workspace), not `backend/.venv`.

## Daily commands

From **repo root** (install / refresh deps):

```bash
uv sync
```

If you still see `invalid peer certificate: UnknownIssuer` when running `uv`, the repo sets `system-certs = true` in the root `pyproject.toml`. You can also run `uv sync --system-certs` once. Put `--system-certs` on **`uv`**, not on `uvicorn`.

From **`backend/`** (all `uv run` commands use the root `.venv`):

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

```bash
uv run pytest -m "not integration"
uv run ruff check .
uv run alembic upgrade head
```

After model changes: `uv run alembic revision --autogenerate -m "…"`, review the file, then apply:

```bash
uv run alembic upgrade head
```

Preview SQL without touching the database: `uv run alembic upgrade head --sql`.

## IDE

Select interpreter: **`<repo>/.venv/Scripts/python.exe`** (see root `.vscode/settings.json`).

## More detail

- Conventions: [AGENTS.md](AGENTS.md)
- Full setup: [../docs/guides/backend-setup.md](../docs/guides/backend-setup.md)
