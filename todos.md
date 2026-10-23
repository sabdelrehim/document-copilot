# Document Copilot — build checklist

Work top to bottom. Each phase has a stop condition. Do not start the next phase until that condition is true.

The product is a grounded chat over SEC filings. The risky parts are retrieval quality and citation trust, not the screen chrome. Build a thin authenticated chat path first so the wire format is real, then load the corpus, then turn on the model. The backend owns each contract (schema, auth, streaming, retrieval). The frontend follows in the same phase so you can see the contract work.

## Already in the repo

- [x] Client brief, architecture, and setup guides
- [x] Backend and frontend env templates
- [x] `data/download.py` for the sample 10-K corpus
- [x] Supabase project created and credentials filled into local `.env` files
- [x] OpenAI API key in `backend/.env` (verified: API responds)
- [x] Sample filings downloaded (25 × 10-K on disk; see note on `USER_AGENT` below)

## 0. Accounts and corpus on disk

Nothing else can be verified without these.

- [x] Create the hosted Supabase project ([docs/guides/supabase-setup.md](docs/guides/supabase-setup.md))
- [ ] Enable email auth only. For local dev, turn off email confirmation *(confirm in Supabase dashboard — not verifiable from the repo)*
- [x] Copy project URL, anon key, service-role key, and the **direct** database URL into `backend/.env`
- [x] Copy project URL and anon key into `frontend/.env`. Leave the service-role key and `DATABASE_URL` out of the frontend
- [x] Create an OpenAI key and set `OPENAI_API_KEY` in `backend/.env`
- [ ] Set a real SEC `USER_AGENT` in `data/download.py` *(still `your.email@example.com` in source; corpus already downloaded)*

**Step 0 audit (local):** Supabase Auth health OK; OpenAI key OK; backend/frontend Supabase URL + anon key match; `DATABASE_URL` uses direct `db.<ref>.supabase.co` (not pooler); 25 `.htm` files + `manifest.json` (5 tickers × 5 filings). Postgres login not re-tested here (Windows OpenSSL/psycopg quirk); first `alembic upgrade head` in phase 1 is the real DB proof.

**Stop when:** both `.env` files have real values, and `data/downloads/` plus `manifest.json` exist locally.

## 1. Scaffold both apps

Scaffold the backend first, then the frontend. You need a process that can own migrations before the UI is worth building. Keep both apps empty of product behavior in this phase.

- [x] From `backend/`, install the stack in [docs/guides/backend-setup.md](docs/guides/backend-setup.md): FastAPI, uvicorn, Pydantic, pydantic-settings, httpx, structlog, OpenAI, Supabase, PydanticAI, SQLAlchemy, Alembic, psycopg, pgvector; dev deps pytest and ruff
- [x] Make `backend/app` an installable package so `from app...` works under uvicorn and pytest
- [x] Add `app/config.py` as the only place that reads environment variables. Fail startup if a required value is missing
- [x] Add `app/main.py` with a health route and CORS from `ALLOWED_ORIGINS`
- [x] Initialize Alembic and point `alembic/env.py` at SQLAlchemy metadata and the direct `DATABASE_URL`
- [x] From `frontend/`, scaffold Vite React TypeScript ([docs/guides/frontend-setup.md](docs/guides/frontend-setup.md))
- [x] Add Tailwind, shadcn/ui, and React Router. Keep the `@/*` import alias
- [x] Add `src/lib/env.ts` that validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` at boot
- [x] Confirm `pnpm tsc --noEmit` and `pnpm lint` pass, and `uv run uvicorn app.main:app --reload` serves the health route

**Stop when:** the API answers a health check on `http://localhost:8000` and the SPA renders a blank shell on `http://localhost:5173`.

## 2. Schema, identity, and the API client

Auth and tables are the shared contract. Put them in place before any chat or ingestion code.

- [x] Model `users`, `chat_threads`, `chat_messages`, `message_citations`, `source_documents`, and `document_chunks` in `app/database/models.py`
- [x] Generate and review the first Alembic migration. Add by hand what autogenerate will miss: `vector` extension, `vector(1536)` embeddings, generated `tsvector`, HNSW and GIN indexes, RLS enablement and policies (`alembic/versions/8b3166d00f01_initial_schema.py`)
- [ ] Apply it with `uv run alembic upgrade head` against the direct connection, not the pooler URL *(prepared — not run yet)*
- [ ] On signup, create a `users` row keyed by `auth.users.id`
- [ ] Backend: `app/auth/dependencies.py` verifies `Authorization: Bearer <supabase access token>` by calling Supabase Auth, and exposes `get_current_user`. Reject missing or invalid tokens with 401 before any other work
- [ ] Frontend: `src/lib/supabase.ts` browser client, email sign-in and sign-out pages, and a route guard. No Google and no SSO
- [ ] Frontend: `src/lib/http.ts` and `src/lib/api.ts`. The client adds the bearer token, applies `VITE_API_BASE_URL`, times out, and turns failures into typed `ApiError`s, including a flag that separates network or CORS failures from HTTP errors
- [ ] Prove a protected backend route returns the signed-in user, and returns 401 with no token

**Stop when:** you can sign in with email in the browser and call one authenticated backend route. Another user's rows are not readable.

## 3. Walking skeleton for chat

Prove threads, history, and streaming before any LLM or retrieval work. A stub answer is enough.

- [ ] `POST /chat/threads`, `GET /chat/threads`, and `GET /chat/threads/{id}/messages`, all scoped to the current user. Accessing another user's thread returns 403. A missing thread returns 404
- [ ] `POST /chat/stream` accepts `{ threadId, messages }` and streams an AI SDK-compatible stub reply
- [ ] Translate AI SDK UI messages into internal Pydantic models in `app/chat/messages.py`. Emit stream events from `app/chat/streaming.py`
- [ ] Persist the user message and the final assistant message only after the stub run finishes
- [ ] Frontend chat route using the Vercel AI SDK `useChat` transport pointed at `/chat/stream`, with the Supabase access token on the request
- [ ] Thread list and the ability to reopen a past conversation
- [ ] Empty state when a user has no threads yet

**Stop when:** two browser sessions can each create a thread, send a message, see a streamed stub, reload, and still see only their own history.

## 4. Ingestion

Turn the downloaded 10-Ks into citeable passages. Do this before the real assistant. The agent has nothing trustworthy to say until chunks exist.

- [ ] Parse each downloaded filing into normalized Markdown and keep filing metadata: ticker, company, form type, filing date, fiscal year, accession number, source URL
- [ ] Store that Markdown on `source_documents` so later re-chunking does not depend on the raw HTML
- [ ] Chunk on section boundaries an analyst would recognize (business, risk factors, MD&A, segments, financials). Record chunk index, page or section, token count, and source offsets
- [ ] Embed chunks with the configured OpenAI embedding model and write `document_chunks` rows, including the generated full-text vector
- [ ] Make the ingest script idempotent for a given accession number
- [ ] Unit-test parsing and chunking with fixtures. No network and no database in the fast suite
- [ ] Ingest the sample corpus and confirm row counts for five companies across the downloaded years

**Stop when:** every sample filing is queryable as chunks with company, year, section, and page metadata, and re-running ingest does not duplicate them.

## 5. Hybrid retrieval

Retrieval stays independent of PydanticAI so it can be tested without calling the model.

- [ ] Embed the user query and run a bounded `pgvector` search over `document_chunks.embedding`
- [ ] Run a bounded Postgres full-text search over `document_chunks.search_vector`
- [ ] Fuse the two ranked lists in Python with Reciprocal Rank Fusion (`app/retrieval/fusion.py`)
- [ ] Return selected chunks plus neighboring chunks and source-document metadata
- [ ] Expose this as bounded operations the agent can call later: search filings, read a chunk, read surrounding chunks. The agent must not generate SQL
- [ ] Unit-test fusion and passage assembly with fixed rankings. Mark live Supabase or OpenAI tests as integration

**Stop when:** a query such as "NVIDIA data center demand" returns chunks from the right filings, and the fast test suite stays green offline.

## 6. Grounded assistant

This is the product contract from the brief: never invent, always cite, show the passage, refuse to go past the filings.

- [ ] Define `DocumentAgentDeps`, `GroundedAnswer`, `Citation`, and `SourcePassage`
- [ ] Write `app/assistant/instructions.md`: answer only from retrieved passages, cite every factual claim, say when the corpus is insufficient, do not give stock recommendations or investment advice, stay concise enough to review
- [ ] PydanticAI agent with those deps and tools. No globals
- [ ] `app/chat/orchestrator.py` runs one turn: retrieve, generate, validate, stream, then persist
- [ ] Grounding validator rejects any citation that does not map to a passage retrieved for this request
- [ ] An answer with factual claims and zero citations fails closed. An explicit "not enough evidence" answer may have no citations
- [ ] On validation failure, stream a controlled error. Do not persist a polished unsupported answer
- [ ] Persist `message_citations` with company, filing, date, page or section, and excerpt
- [ ] Unit-test the validator: valid citation, invented citation, and insufficient-evidence
- [ ] Replace the phase 3 stub with this agent on `/chat/stream`. Stream text deltas, then citation parts

**Stop when:** a question answered by the corpus returns cited passages, a question outside the corpus says so, and a recommendation request is refused.

## 7. Analyst-facing chat UI

The browser stays thin. It renders state, holds the session, and streams. It never calls OpenAI or holds the service-role key.

- [ ] Render the answer with inline citations
- [ ] One click, or an equivalent disclosure, shows the underlying passage and the filing label (company, form, date, page or section)
- [ ] Show streaming status, empty thread state, and friendly errors for 401, 403, 404, grounding failure, and upstream failure. Keep technical detail in logs
- [ ] Generate a short thread title from the first question
- [ ] Sign-out returns to the email login screen and does not leave another user's threads visible
- [ ] Check the flow in the browser: sign in, ask, inspect a citation, reload, open the old thread, sign out

**Stop when:** an analyst can verify a claim against the filing text without leaving the page, and past conversations survive a reload.

## 8. Trust check against the brief

Run these by hand against the ingested sample. A miss here is a product bug, not a polish item. The questions are listed in [docs/client-brief.md](docs/client-brief.md).

- [ ] Apple 2021–2025 revenue mix across iPhone, Services, Mac, iPad, and Wearables, with the category that moved the mix
- [ ] Amazon AWS operating income and margin versus North America and International, and years where AWS appears to fund weaker segments
- [ ] NVIDIA data center demand, customer concentration, and supply constraints, fiscal 2021–2025
- [ ] Microsoft language changes on Azure, AI infrastructure, and cloud capacity
- [ ] Alphabet revenue trends for Search, YouTube ads, Network, subscriptions/platforms/devices, and Google Cloud
- [ ] Risk-factor language that was added, removed, or materially changed for AI, cloud, export controls, supply-chain concentration, or regulation
- [ ] Apple and NVIDIA supplier concentration and third-party manufacturing, and whether the wording got more or less urgent
- [ ] Capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA
- [ ] Latest-year geographic revenue exposure for each company, plus year-over-year changes
- [ ] A question that asks the filings to prove generative AI improved margins. The bot must stick to disclosed evidence and refuse to infer past it
- [ ] A question about a company or year that is not in the corpus. The bot says the corpus does not contain it
- [ ] A request for a stock pick or a price target. The bot refuses

**Stop when:** each answer cites filing and page, the passage matches the claim, and the two refusal cases stay refusals.

## 9. Deploy the pilot

Driftwood has no infra team. Two Railway services plus hosted Supabase is the whole footprint.

- [ ] Railway frontend service: Vite static build. Railway backend service: Uvicorn. Backend stays stateless
- [ ] Production env vars match `app/config.py` and `src/lib/env.ts`. Service-role key and `DATABASE_URL` exist only on the backend
- [ ] Set `ALLOWED_ORIGINS` to the deployed frontend origin
- [ ] Run Alembic against the hosted database before serving traffic
- [ ] Re-enable email confirmation if it was disabled for local dev
- [ ] Create logins for the five senior analysts in the pilot
- [ ] Write the local run steps into the README, replacing the "to be added" note
- [ ] Smoke-test production: sign in, ask one corpus question, open the citation, reopen the thread later

**Stop when:** the pilot group can use the hosted app for a week. The brief's bar is at least three hours saved per analyst. Firm-wide rollout is a decision after that week, not part of this build.
