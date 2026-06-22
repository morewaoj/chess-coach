# RS Chess Coach

A chess coaching AI that combines Stockfish 18 engine 
analysis with a RAG knowledge base to give grounded, 
cited coaching advice for every move of a real game.

---

## What It Does

RS Chess Coach is not a chess engine wrapper. It is a 
coaching system. For every position it:

1. Calculates the mathematically best move using Stockfish 18
2. Retrieves relevant chess knowledge from a RAG pipeline
3. Explains the best move using that knowledge with citations
4. Warns about traps and tactical threats specific to the position
5. Gives a concrete 3-5 move strategic plan
6. Remembers every move played so advice builds on game history

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│                                                             │
│  index.html                                                 │
│  - Interactive chess board                                  │
│  - Move input, hint requests, coaching chat                 │
│  - Calls FastAPI with fetch()                               │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / JSON
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│                                                             │
│  api.py                                                     │
│  - /game/state, /game/move, /game/ask, /game/hint, /reset   │
│  - Request validation with Pydantic                         │
│  - CORS for browser frontend                                │
│  - Lazy Stockfish startup and clean shutdown                │
└───────────────┬──────────────────────┬──────────────────────┘
                │                      │
                ▼                      ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│      Game State Layer      │   │      Chess Engine Layer     │
│                            │   │                             │
│  src/board.py              │   │  src/engine.py              │
│  - python-chess Board      │   │  - Stockfish 18 UCI process │
│  - Legal move validation   │   │  - Best move                │
│  - SAN/UCI/plain parsing   │   │  - Evaluation score         │
│  - Move history            │   │  - Top candidate moves      │
│  - FEN position state      │   │  - Move quality analysis    │
└───────────────┬───────────┘   └──────────────┬──────────────┘
                │                              │
                └──────────────┬───────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI Coaching Layer                         │
│                                                             │
│  src/coach.py                                               │
│  - Builds full coaching prompt                              │
│  - Combines board state + Stockfish + retrieved knowledge   │
│  - Sends grounded prompt to Groq LLM                        │
│  - Returns structured coaching response                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        RAG Layer                             │
│                                                             │
│  documents/raw/*.txt                                        │
│       ↓ ingest.py                                           │
│       ↓ chunk.py                                            │
│       ↓ embed.py                                            │
│  data/chroma_store                                          │
│       ↓ retrieve.py                                         │
│  Top-k chess knowledge chunks                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Runtime Flow

When a player makes a move or asks for help, the system
follows a deterministic pipeline before involving the LLM:

1. The frontend sends a JSON request to FastAPI.
2. `api.py` validates the request and calls the game layer.
3. `board.py` checks legality, updates the board, and stores
   the move history in standard algebraic notation.
4. `engine.py` asks Stockfish for the best move and evaluation.
5. `coach.py` builds a retrieval query using the user message,
   recent moves, current turn, and game state.
6. `retrieve.py` embeds the query and searches ChromaDB for the
   most relevant chess knowledge chunks.
7. `coach.py` builds a grounded prompt containing the FEN,
   move history, Stockfish output, and retrieved knowledge.
8. Groq's LLM generates a human coaching explanation.
9. FastAPI returns the best move, evaluation, citations, and
   coaching response to the frontend.

This keeps calculation, retrieval, and explanation separate.
That separation is the central engineering decision in the app.

---

## Why This Architecture

**Why Stockfish instead of asking the LLM for moves:**
LLMs are trained on text about chess, not on chess 
calculation. They can describe tactics but cannot 
reliably calculate positions. Stockfish is deterministic 
and correct. The LLM explains. Stockfish calculates. 
These are separate jobs done by the best tool for each.

**Why RAG instead of just prompting the LLM:**
A general LLM gives generic chess advice. RAG grounds 
every response in specific knowledge about openings, 
tactics, strategy, and endgames. The coach can cite 
which document its advice comes from, making it 
verifiable and specific rather than plausible-sounding.

**Why game memory:**
Without explicit state tracking the coach treats every 
move in isolation. The ChessGame class records every 
move in standard algebraic notation and maintains the 
full FEN position string. Every coaching response 
includes the complete game history so the LLM 
understands the full narrative of the game.

---

## AI Engineering Relevance

This project demonstrates a production-style AI pattern:

```
Deterministic tool + state management + retrieval + LLM generation + API + UI
```

The app does not treat the LLM as an all-knowing black box.
Instead, it gives each subsystem the job it is best suited for:

| Problem | System Used | Why |
|---------|-------------|-----|
| Legal move validation | python-chess | Deterministic rules, no hallucination |
| Best move calculation | Stockfish 18 | Search and evaluation are engine tasks |
| Domain knowledge | ChromaDB + fastembed | Retrieves relevant chess concepts |
| Explanation | Groq LLM | Converts analysis into coaching language |
| State and orchestration | FastAPI backend | Owns API flow and system boundaries |
| User experience | HTML/CSS/JS frontend | Makes the AI system usable |

That is directly relevant to AI engineering because many useful
AI products are not just prompts. They are orchestrated systems
where the LLM is one component among tools, databases, APIs,
validators, and user-facing workflows.

This same architecture maps to other domains:

| Domain | Deterministic Tool | Retrieval Source | LLM Role |
|--------|--------------------|------------------|----------|
| Healthcare | Clinical rules / calculators | Medical guidelines | Explain and summarize |
| Legal | Citation and statute lookup | Case law corpus | Draft and reason with citations |
| Finance | Pricing / risk models | Market reports | Explain portfolio decisions |
| Developer tools | Tests / compilers | Docs and codebase | Debug and propose fixes |
| Education | Grading logic | Curriculum content | Tutor the student |

The chess coach is a compact example of the same engineering
pattern used in real AI products: ground the model, constrain
the model, verify with tools, and expose the result through a
usable product interface.

---

## AI Engineering Skills Demonstrated

This project is useful as an AI engineering portfolio project
because it shows the following skills:

| Skill | Where It Shows Up |
|-------|-------------------|
| LLM application design | `src/coach.py` prompt construction and response format |
| RAG pipeline development | `ingest.py`, `chunk.py`, `embed.py`, `retrieve.py` |
| Vector database usage | ChromaDB persistent store in `data/chroma_store` |
| Embedding model selection | fastembed with BAAI/bge-small-en-v1.5 |
| Tool orchestration | Stockfish + RAG + Groq combined in one response |
| Deterministic validation | python-chess move legality and FEN state |
| API engineering | FastAPI endpoints, Pydantic request models, CORS |
| State management | Persistent in-memory game state across API calls |
| Prompt engineering | Structured coach prompt with citations and constraints |
| Reliability thinking | LLM does not calculate moves; Stockfish does |
| Testing and debugging | Backend smoke tests under `tests/test_backend.py` |
| Deployment awareness | Vercel frontend and Render backend architecture |

Interview positioning:

- Built a multi-component AI system instead of a simple chatbot.
- Used RAG to ground responses in a domain-specific knowledge base.
- Integrated an external deterministic engine to prevent LLM
  hallucination in a high-precision task.
- Designed API boundaries between frontend, backend, retrieval,
  engine analysis, and generation.
- Added tests for backend behavior without depending on live LLM calls.
- Made model output structured, cited, and product-ready.

Strong resume framing:

> Built an AI chess coaching platform combining Stockfish 18,
> FastAPI, ChromaDB, fastembed, and Groq LLMs to deliver grounded,
> cited coaching advice from live game state. Designed a RAG
> pipeline over chess knowledge documents, orchestrated deterministic
> engine analysis with LLM explanation, and implemented API endpoints
> plus backend smoke tests for reliable local operation.

---

## Document Sources

8 chess knowledge documents covering the full range 
of topics a 1200-1800 rated player needs:

| File | Type | Coverage |
|------|------|----------|
| openings_sicilian.txt | chess_opening | Najdorf, Dragon, Classical, Scheveningen |
| openings_e4_responses.txt | chess_opening | French, Caro-Kann, Pirc, Scandinavian |
| openings_d4_systems.txt | chess_opening | QGD, King's Indian, Nimzo, QID |
| tactics_fundamentals.txt | chess_tactics | Forks, pins, skewers, discovered attacks, mating patterns |
| middlegame_positional_play.txt | chess_strategy | Pawn structures, piece activity, outposts, weak squares |
| attack_defense_king_safety.txt | chess_strategy | Attack signals, Greek Gift, defensive technique |
| endgames_king_pawn.txt | chess_endgame | Opposition, triangulation, outside passers |
| endgames_rook_endings.txt | chess_endgame | Lucena, Philidor, rook activity |

---

## Chunking Strategy

**Method:** RecursiveCharacterTextSplitter
**Chunk size:** 800 characters
**Overlap:** 100 characters
**Result:** 64 chunks across 8 documents (8.0 average per document)

**Why these numbers for chess content:**
Chess explanations require full paragraph context to 
be meaningful. A tactical pattern or opening idea 
needs at least 150-200 words to explain correctly. 
Smaller chunks (under 500 chars) would split move 
sequences mid-explanation, destroying their meaning. 
Larger chunks (over 1200 chars) would blend multiple 
unrelated concepts into one embedding, diluting 
retrieval precision.

The 100 character overlap ensures move sequences 
that span paragraph boundaries — common in chess 
writing — are captured in at least one complete chunk.

---

## Embedding Model

**Model:** BAAI/bge-small-en-v1.5 via fastembed
**Why fastembed instead of sentence-transformers:**
PyTorch dropped Intel Mac support in 2024. fastembed 
uses ONNX Runtime instead — lighter, faster on CPU, 
works on Intel Mac without PyTorch. Same embedding 
quality, different execution engine.

**Why BAAI/bge-small-en-v1.5:**
Outperforms all-MiniLM-L6-v2 on retrieval benchmarks. 
Distances under 0.27 observed on chess queries — 
significantly stronger semantic matching than the 
0.4-0.5 range typical of MiniLM.

**Production tradeoffs:**

| Factor | Current | Production Alternative |
|--------|---------|----------------------|
| Cost | Free local | OpenAI text-embedding-3-large |
| Context length | 512 tokens | ada-002 (8191 tokens) |
| Multilingual | English only | multilingual-e5-large |
| Accuracy | Strong | e5-mistral-7b (higher, slower) |

---

## Retrieval Test Results

**Query 1 — Opening identification**
Query: "I played e4 and opponent played c5 what opening is this"
Top result: openings_sicilian.txt | distance: 0.21
Why relevant: Direct match to Sicilian Defense content. 
Distance of 0.21 indicates near-perfect semantic match.

**Query 2 — Tactical pattern**
Query: "my knight can fork the king and rook how do I calculate"
Top result: tactics_fundamentals.txt | distance: 0.24
Why relevant: Tactics document covers fork patterns 
and calculation methodology precisely.

**Query 3 — Endgame technique**
Query: "I am in a king and pawn endgame how do I use opposition"
Top result: endgames_king_pawn.txt | distance: 0.19
Why relevant: Endgame document covers opposition, 
key squares, and king and pawn technique directly.

All distances under 0.27 — significantly stronger 
than typical RAG retrieval benchmarks.

---

## Grounded Generation

Grounding is enforced through the system prompt in 
src/coach.py. The LLM receives:

1. Complete game state — FEN, move history, whose turn
2. Stockfish analysis — best move and centipawn evaluation
3. Retrieved knowledge chunks with [Knowledge N: source] labels
4. Explicit instruction to answer only from retrieved context

The system prompt instructs the LLM to:
- Always lead with the Stockfish best move
- Cite knowledge sources using [Knowledge N: filename] labels
- Explain moves using chess principles from the knowledge base
- Warn about specific tactical threats with square names
- Give concrete 3-5 move plans, not generic advice
- Decline to speculate beyond what the knowledge base contains

---

## Example Coach Response

Query: After 1.e4 c5 — what should I play?

♟ BEST MOVE: Nf3

📊 EVALUATION: +0.30 — White has a slight but real 
advantage. Your pieces are more active and you control 
more central space.

📖 OPENING / POSITION TYPE: Sicilian Defense. One of 
the most theoretically rich openings in chess. Black's 
c5 contests d4 from the side rather than occupying 
the center directly.

⚡ WHY THIS MOVE: Nf3 develops naturally, controls d4 
and e5, and keeps all options open. You can follow 
with d4 for the Open Sicilian or stay in Anti-Sicilian 
territory. [Knowledge 1: openings_sicilian.txt]

🎯 YOUR PLAN: 1.Nf3 2.d4 cxd4 3.Nxd4 — enter the 
Open Sicilian. Then Nc3 and Be3 for the English Attack.

⚔️ WHAT YOUR OPPONENT WANTS: Black will aim for 
...d6, ...Nf6, and queenside expansion with ...b5. 
They want active piece play and long-term counterplay.

⚠️ CRITICAL WARNING: Do not push d4 without Nf3 
first — you risk losing the pawn or entering an 
inferior structure.

📚 SOURCES: openings_sicilian.txt

---

## Evaluation Plan

5 test questions designed to cover the full game lifecycle:

**Q1 — Opening recognition**
Question: I played e4 and opponent played c5. What is this?
Expected: Identifies Sicilian Defense, recommends Nf3, 
cites openings_sicilian.txt

**Q2 — Tactical awareness**
Question: My knight is on e5, opponent has pieces on 
c6 and g6. What should I look for?
Expected: Identifies fork possibility, cites 
tactics_fundamentals.txt

**Q3 — Trap warning**
Question: I played e4 e5 Nf3 and opponent played Nd4
Expected: Identifies knight on d4 as aggressive, 
warns about resulting complications

**Q4 — Endgame technique**
Question: I have king on e4, pawn on e5. Opponent 
has king on e6. Whose move matters?
Expected: Explains opposition, key squares, 
cites endgames_king_pawn.txt

**Q5 — Out of scope**
Question: What is the best chess.com membership plan?
Expected: System declines — not in knowledge base

---

## Failure Case

Question 5 is deliberately out of scope. No document 
in the corpus covers chess.com pricing or membership. 
The system prompt instructs the coach to acknowledge 
when the knowledge base lacks information rather than 
generating a plausible-sounding answer from general 
AI knowledge.

This is the grounding mechanism working correctly. 
A coach that invents answers it does not have is 
less trustworthy than one that says "I don't have 
that information."

---

## Anticipated Challenges

**Challenge 1 — Move format parsing**
The frontend sends moves in UCI format (e2e4) but 
chess coaching literature uses algebraic notation (e4). 
The board.py parser handles both formats plus plain 
English descriptions.

**Challenge 2 — Opening coverage gaps**
The knowledge base covers major openings but not 
every variation. A highly specific line may not 
retrieve precise theory. The coach falls back to 
general chess principles when specific opening 
knowledge is unavailable.

**Challenge 3 — Conflicting engine and knowledge**
Stockfish occasionally recommends moves that contradict 
classical opening theory — the engine sees deeper than 
human-written guides. The system prompt instructs the 
coach to present both the engine recommendation and 
the theoretical context.

**Challenge 4 — Game state across sessions**
The backend holds game state in memory. Restarting 
the server resets the game. Production deployment 
would use Redis or a database for persistent state.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Health check |
| GET | /game/state | Current board position and history |
| POST | /game/move | Make a move and get coaching |
| POST | /game/ask | Ask a question without moving |
| GET | /game/hint | Get best move recommendation |
| GET | /game/best-move | Fast Stockfish-only move for UI highlighting |
| POST | /game/reset | Reset to starting position |

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Chess engine | Stockfish 18 |
| Embeddings | fastembed BAAI/bge-small-en-v1.5 |
| Vector store | ChromaDB |
| LLM | Groq llama-3.3-70b-versatile |
| Backend | FastAPI + uvicorn |
| Frontend | HTML/CSS/JS + Chessboard.js |
| Deployment | Vercel (frontend) + Render (backend) |
| Language | Python 3.11 |

---

## Setup

```bash
git clone https://github.com/morewaoj/chess-coach
cd chess-coach
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Add Stockfish binary to project root
# Download from stockfishchess.org
chmod +x stockfish

# Add API key
cp .env.example .env
# Edit .env and add GROQ_API_KEY

# Optional Groq/token controls
# GROQ_MAX_TOKENS=650
# RAG_TOP_K=3
# RAG_CHUNK_CHARS=450

# Build vector store
python3 src/embed.py

# Start backend
python3 api.py

# Open frontend
open index.html
```

---

## Running Tests

Backend smoke tests are included so the API can be checked
without making live Groq calls:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

The tests cover:

- FastAPI import behavior
- Health and game state endpoints
- Invalid move handling
- Move endpoint response shape
- Fast Stockfish-only best move endpoint
- Engine fallback when the AI provider fails
- Reset behavior
- SAN, UCI, and plain-English move parsing

This keeps core backend behavior testable even when the LLM
provider is unavailable or API keys are not configured.

---

## Deployment

Recommended production setup:

```txt
Frontend: Vercel
Backend: Render using Docker
```

### 1. Deploy Backend To Render

The backend includes:

- `Dockerfile` — installs Python dependencies and Linux Stockfish
- `render.yaml` — Render web service blueprint
- `api.py` — FastAPI app served by uvicorn

On Render:

1. Create a new Blueprint or Web Service from this repository.
2. Use the Docker environment.
3. Add environment variables:

```bash
GROQ_API_KEY=your_groq_key
GROQ_MAX_TOKENS=650
RAG_TOP_K=3
RAG_CHUNK_CHARS=450
```

The Docker image builds the Chroma vector store during deploy:

```bash
python src/embed.py
```

After deploy, Render gives you a backend URL like:

```txt
https://chess-coach-api.onrender.com
```

### 2. Deploy Frontend To Vercel

The frontend is static and uses:

- `frontend/index.html`
- `frontend/package.json`
- `frontend/scripts/write-config.js`
- `frontend/vercel.json`

In Vercel project settings, set:

```txt
Root Directory: frontend
Framework Preset: Other
Build Command: npm run build
Output Directory: .
Install Command: npm install
```

Then add this environment variable:

```bash
CHESS_COACH_API_BASE=https://your-render-backend-url.onrender.com
```

During `npm run build`, the script writes `config.js`:

```js
window.CHESS_COACH_CONFIG = {
  API_BASE: "https://your-render-backend-url.onrender.com"
};
```

Locally, if `config.js` is missing, the frontend falls back to:

```txt
http://localhost:8000
```

### Deployment Notes

- Do not deploy the backend to Vercel for the portfolio version.
  The backend uses Stockfish and in-memory game state, which fit
  better on a persistent Docker web service.
- The Docker deployment uses `requirements-prod.txt` and a
  lightweight text retriever to avoid loading ChromaDB/ONNX
  embedding models on small-memory hosts.
- Setting the Vercel root directory to `frontend` prevents Vercel
  from detecting the FastAPI backend files.
- The included `.vercelignore` keeps backend files out of the
  frontend deployment.
- The included `.dockerignore` keeps local-only files out of the
  backend image.
- Current game state is in memory. Restarting the backend resets
  the game. For multi-user production, add Redis or database-backed
  sessions.

---

## Deployment Troubleshooting Log

This section records deployment issues encountered during the
project and the fix that worked. Add new issues here whenever
deployment or runtime behavior breaks.

### Issue: Render Backend Exceeded Memory Limit

**Symptoms**

- Render sent an alert:
  `Web Service chess-coach-api exceeded its memory limit`.
- The backend restarted automatically.
- The frontend appeared to fail because it could not reliably
  reach the backend during restarts.
- Possible frontend symptoms:
  - `Failed to fetch`
  - `Backend unavailable`
  - `502` or `503`
  - temporary CORS-looking errors caused by the backend being down

**Root Cause**

The original backend loaded a heavy RAG stack at runtime:

```txt
fastembed + ChromaDB + ONNX runtime + vector store
```

That was too much memory for a small/free Render instance,
especially alongside:

```txt
FastAPI + Stockfish subprocess + Groq client
```

The corpus only has 8 small chess documents, so a vector database
was unnecessary for the hosted portfolio version.

**Fix That Worked**

- Replaced runtime Chroma/fastembed retrieval with lightweight
  pure-Python text retrieval in `src/retrieve.py`.
- Added `requirements-prod.txt` so Docker installs only production
  backend dependencies.
- Updated `Dockerfile` to use `requirements-prod.txt`.
- Removed `RUN python src/embed.py` from Docker because the hosted
  app no longer builds a Chroma vector store.
- Kept the local embedding/Chroma files in the repo for learning
  and experimentation, but production no longer depends on them.

**Verification**

```bash
python -m unittest discover -s tests -v
python src/retrieve.py
```

Expected:

- Tests pass.
- Sicilian queries return `openings_sicilian.txt`.
- Fork queries return `tactics_fundamentals.txt`.
- Opposition queries return `endgames_king_pawn.txt`.

After pushing the fix, redeploy Render with **Manual Sync** and
watch logs/metrics for memory restarts.

### Issue: Vercel Tried To Deploy FastAPI Backend

**Symptoms**

Vercel failed with:

```txt
No FastAPI entrypoint found.
Set "tool.vercel.entrypoint" in pyproject.toml...
```

**Root Cause**

Vercel detected Python/FastAPI files in the repository root and
tried to deploy the backend. In this architecture, Vercel should
only deploy the static frontend. The backend is already deployed
on Render.

**Fix That Worked**

- Added a dedicated `frontend/` directory containing only:
  - `index.html`
  - `package.json`
  - `vercel.json`
  - `scripts/write-config.js`
  - `config.example.js`
- Set Vercel **Root Directory** to:

```txt
frontend
```

- Set Vercel build settings:

```txt
Framework Preset: Other
Build Command: npm run build
Output Directory: .
Install Command: npm install
```

- Added Vercel environment variable:

```txt
CHESS_COACH_API_BASE=https://your-render-backend-url.onrender.com
```

**Important**

Do not use `VITE_API_URL` for this app. The frontend expects:

```txt
CHESS_COACH_API_BASE
```

### Issue: Groq Rate Limit

**Symptoms**

The coaching response includes a technical detail like:

```txt
Error code: 429
rate_limit_exceeded
tokens per day
```

**Root Cause**

Groq daily token quota was reached. The backend is still running;
the LLM provider temporarily refused the request.

**Fixes That Worked**

- Added `/game/best-move` so UI highlighting uses Stockfish only
  and does not call Groq.
- Reduced default LLM output:

```txt
GROQ_MAX_TOKENS=650
RAG_TOP_K=3
RAG_CHUNK_CHARS=450
```

- Shortened the default frontend coaching prompt.
- Added a backend fallback so if Groq fails, the API still returns
  a Stockfish-based response instead of making the app look dead.

### Issue: Browser And Backend Board State Out Of Sync

**Symptoms**

A legal-looking move such as `e2e3` returned an error.

**Root Cause**

The backend was already at a later game state, for example after
`1.e4`, so it was Black's turn. The move was valid notation but
illegal in the current backend position.

**Fix That Worked**

- Reset backend state with:

```bash
curl -H "Content-Type: application/json" \
  -d '{"confirm":true}' \
  https://your-render-backend-url.onrender.com/game/reset
```

- Improved `src/board.py` so UCI moves that parse but are illegal
  now return a clearer error:

```txt
Illegal move for current position...
It is Black's turn...
Current move history...
```

---

## AI Usage

**Instance 1 — fastembed swap**
When sentence-transformers failed on Intel Mac due 
to PyTorch dropping x86_64 support, I diagnosed the 
dependency chain and directed Claude to swap the 
embedding library to fastembed with ONNX Runtime. 
The model selection (BAAI/bge-small-en-v1.5) was 
chosen based on retrieval benchmark comparisons.

**Instance 2 — coach.py system prompt**
The initial system prompt produced shallow responses. 
I directed Claude to restructure it with 10 mandatory 
coaching rules and a strict 8-section output format 
requiring specific squares, move sequences, and trap 
warnings. The final prompt enforces depth rather than 
just suggesting it.

---

## Deployment Status

- [x] Backend built and tested locally
- [x] Frontend built and tested locally
- [ ] Backend deployed to Render
- [ ] Frontend deployed to Vercel
- [ ] Custom domain (optional)
- [ ] README updated with live URLs
