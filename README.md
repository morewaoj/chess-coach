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
HTML Frontend (Vercel)
        ↓ fetch() API calls
FastAPI Backend (Render)
        ↓
┌───────────────────────────────────┐
│             coach.py              │
│                                   │
│  ┌──────────┐  ┌───────────────┐  │
│  │Stockfish │  │ RAG Pipeline  │  │
│  │    18    │  │               │  │
│  │best move │  │   ChromaDB    │  │
│  │eval score│  │   64 chunks   │  │
│  └──────────┘  │  8 documents  │  │
│                └───────────────┘  │
│  ┌──────────────────────────────┐ │
│  │   Game Memory (board.py)     │ │
│  │  full move history + FEN     │ │
│  └──────────────────────────────┘ │
│  ┌──────────────────────────────┐ │
│  │    Groq llama-3.3-70b        │ │
│  │    grounded explanation      │ │
│  └──────────────────────────────┘ │
└───────────────────────────────────┘
```

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

# Build vector store
python3 src/embed.py

# Start backend
python3 api.py

# Open frontend
open index.html
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
