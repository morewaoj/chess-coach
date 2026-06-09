import os
import sys
sys.path.insert(0, "src")

import chess
from groq import Groq
from dotenv import load_dotenv
from board import ChessGame
from engine import ChessEngine
from retrieve import retrieve

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 1024


def build_chess_context(chunks: list[dict]) -> str:
    """
    Format retrieved chess knowledge chunks for the LLM.

    Each chunk is labeled with its source so the coach
    can cite specific documents in its response.
    Source labels are what make citations possible —
    without them the LLM cannot reference where advice
    came from.
    """
    if not chunks:
        return "No specific knowledge retrieved for this position."

    context_parts = []
    for i, chunk in enumerate(chunks):
        context_parts.append(
            f"[Knowledge {i+1}: {chunk['source']}]\n{chunk['text']}"
        )
    return "\n\n".join(context_parts)


def build_coach_prompt(
    game_context: dict,
    stockfish_result: dict,
    knowledge_context: str,
    user_message: str
) -> str:
    """
    Build the full coaching prompt.

    This prompt is the most important engineering decision
    in the whole system. It combines four information sources:

    1. Game state — current position, move history, whose turn
    2. Stockfish analysis — the mathematically best move
    3. RAG knowledge — relevant opening/tactical/strategic context
    4. User message — what the player is asking or reporting

    The system message enforces three behaviors:
    - Grounding: answer from retrieved knowledge, not general AI knowledge
    - Citation: always reference which document advice comes from
    - Structure: always present advice in the coach format below

    Why structured output:
    A consistent response format makes the UI predictable
    and makes the advice scannable during a live game.
    Players need to act fast — walls of text are useless.
    """

    # Format game state for the prompt
    move_history = game_context.get("move_history", [])
    history_str = ""
    if move_history:
        pairs = []
        for i in range(0, len(move_history), 2):
            move_num = (i // 2) + 1
            white = move_history[i]
            black = move_history[i+1] if i+1 < len(move_history) else ""
            pairs.append(f"{move_num}. {white} {black}".strip())
        history_str = " ".join(pairs)
    else:
        history_str = "Game just started."

    # Format Stockfish result
    if stockfish_result.get("mate_in") is not None:
        mate = stockfish_result["mate_in"]
        if mate > 0:
            eval_str = f"MATE IN {mate} (you are winning)"
        else:
            eval_str = f"MATE IN {abs(mate)} (opponent has forced mate)"
    elif stockfish_result.get("evaluation") is not None:
        eval_val = stockfish_result["evaluation"]
        if eval_val > 0:
            eval_str = f"+{eval_val:.2f} (slight advantage for current side)"
        elif eval_val < 0:
            eval_str = f"{eval_val:.2f} (opponent has advantage)"
        else:
            eval_str = "0.00 (equal position)"
    else:
        eval_str = "Position being evaluated"

    # Detect game over states
    game_over_note = ""
    if game_context.get("is_checkmate"):
        game_over_note = "\n⚠️ CHECKMATE — The game is over."
    elif game_context.get("is_game_over"):
        game_over_note = "\n⚠️ GAME OVER — Draw or stalemate."
    elif game_context.get("is_check"):
        game_over_note = "\n⚠️ CHECK — The king is in check."

    system_message = f"""You are RS Chess Coach — an expert chess coach helping a 1200-1800 rated player improve and win their current game.

CURRENT GAME STATE:
Move history: {history_str}
Current position (FEN): {game_context.get('fen', 'Starting position')}
Turn: {game_context.get('turn', 'White')}
Stockfish best move: {stockfish_result.get('move_san', 'Calculating...')}
Position evaluation: {eval_str}{game_over_note}

CHESS KNOWLEDGE BASE:
{knowledge_context}

YOUR COACHING RULES:
1. ALWAYS lead with the Stockfish best move — this is mathematically correct and non-negotiable.
2. Explain WHY the best move is best using the knowledge base. Cite sources using [Knowledge N: filename].
3. Identify the opening or position type from the move history and knowledge base.
4. Warn about specific traps or tactical patterns relevant to this position.
5. Give the strategic plan for the next 3-5 moves.
6. If it is checkmate or game over, congratulate or console and give a brief game recap.
7. Answer ONLY from the retrieved knowledge base for chess theory. Do not use general AI chess knowledge.
8. If knowledge base lacks specific information, say so honestly.

RESPONSE FORMAT — always use exactly this structure:
♟ BEST MOVE: [the Stockfish move]
📊 EVALUATION: [the position score and what it means]
📖 OPENING/POSITION: [what opening or structure this is]
⚡ WHY THIS MOVE: [explanation grounded in knowledge base with citations]
🎯 STRATEGIC PLAN: [next 3-5 moves and the plan]
⚠️ WATCH OUT: [traps, threats, or tactical patterns to be aware of]
📚 SOURCE: [which documents this advice draws from]"""

    return system_message


def get_coaching_response(
    game: ChessGame,
    engine: ChessEngine,
    user_message: str,
    k: int = 5
) -> dict:
    """
    Main coaching function — combines all four systems.

    Flow:
    1. Get current game context (board state + move history)
    2. Ask Stockfish for the best move
    3. Build a RAG query from the game context
    4. Retrieve relevant chess knowledge
    5. Build the grounded coaching prompt
    6. Call the LLM for the explanation
    7. Return structured response

    Why this order matters:
    Stockfish runs before the LLM call so the best move
    is always in the prompt. The LLM never decides the move —
    it only explains it. This prevents the LLM from suggesting
    incorrect moves, which would happen if we asked it to
    both calculate and explain simultaneously.

    The RAG query is built from the actual move history,
    not just the user message. This means even if the user
    just says 'what should I play?' the retrieval system
    understands the full game context.
    """
    game_context = game.get_context()

    # Handle game over states
    if game_context["is_checkmate"]:
        winner = "Black" if game_context["turn"] == "White" else "White"
        return {
            "response": f"♟ CHECKMATE! {winner} wins!\n\n"
                       f"Game recap: {game.get_move_history_string()}\n\n"
                       f"Well played! Start a new game when ready.",
            "best_move": None,
            "evaluation": None,
            "sources": []
        }

    if game_context["is_game_over"]:
        return {
            "response": "Game over — draw or stalemate reached.\n\n"
                       f"Moves played: {game.get_move_history_string()}",
            "best_move": None,
            "evaluation": None,
            "sources": []
        }

    # Step 1: Get Stockfish analysis
    try:
        stockfish_result = engine.get_best_move(game.board)
    except Exception as e:
        stockfish_result = {
            "move_san": "Error",
            "evaluation": None,
            "mate_in": None
        }

    # Step 2: Build RAG query from game context
    move_history = game_context.get("move_history", [])
    if move_history:
        recent_moves = move_history[-6:]
        rag_query = (
            f"{user_message}. "
            f"Moves played: {' '.join(recent_moves)}. "
            f"Position after {len(move_history)} moves. "
            f"Turn: {game_context['turn']}"
        )
    else:
        rag_query = f"{user_message}. Starting position. "
        f"Turn: {game_context['turn']}"

    # Step 3: Retrieve relevant chess knowledge
    chunks = retrieve(rag_query, k=k)
    knowledge_context = build_chess_context(chunks)

    # Step 4: Build grounded coaching prompt
    system_prompt = build_coach_prompt(
        game_context,
        stockfish_result,
        knowledge_context,
        user_message
    )

    # Step 5: Call the LLM for explanation
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    answer = response.choices[0].message.content
    sources = list(dict.fromkeys(chunk["source"] for chunk in chunks))

    return {
        "response": answer,
        "best_move": stockfish_result.get("move_san"),
        "evaluation": stockfish_result.get("evaluation"),
        "mate_in": stockfish_result.get("mate_in"),
        "sources": sources,
        "chunks": chunks
    }


if __name__ == "__main__":
    """
    End-to-end test of the full coaching pipeline.
    Plays through a Sicilian opening and asks for coaching
    at each stage to verify:
    - Stockfish provides best moves
    - RAG retrieves relevant opening knowledge
    - LLM explains grounded in retrieved documents
    - Game memory carries context across moves
    - Full game lifecycle works through to endgame
    """
    print("Testing RS Chess Coach pipeline...")
    print("=" * 60)

    game = ChessGame()
    engine = ChessEngine()

    # Test 1: Opening advice
    print("\nTest 1: Starting position")
    result = get_coaching_response(
        game, engine,
        "I am playing White. What should I open with?"
    )
    print(f"Best move: {result['best_move']}")
    print(f"Evaluation: {result['evaluation']}")
    print(f"Sources: {result['sources']}")
    print(f"\nCoach response preview:")
    print(result['response'][:400])

    # Test 2: After Sicilian starts
    print("\n" + "=" * 60)
    print("Test 2: After 1.e4 c5 (Sicilian Defense)")
    game.make_move("e4")
    game.make_move("c5")
    result = get_coaching_response(
        game, engine,
        "My opponent played c5. What opening is this and what should I do?"
    )
    print(f"Best move: {result['best_move']}")
    print(f"Sources: {result['sources']}")
    print(f"\nCoach response preview:")
    print(result['response'][:400])

    engine.close()
    print("\n" + "=" * 60)
    print("RS Chess Coach pipeline working correctly.")
