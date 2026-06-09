import sys
sys.path.insert(0, "src")

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from board import ChessGame
from engine import ChessEngine
from coach import get_coaching_response

load_dotenv()

app = FastAPI(
    title="RS Chess Coach API",
    description="Chess coaching API combining Stockfish engine analysis with RAG knowledge retrieval",
    version="1.0.0"
)

# CORS middleware — required so the Vercel frontend
# can call this API from a different domain.
# Without this, browsers block cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global game and engine instances
# These persist for the server lifetime so game state
# is maintained across multiple API calls.
# In production with multiple users you would use
# session-based state — for personal use this is fine.
game = ChessGame()
engine = ChessEngine()


class MoveRequest(BaseModel):
    """Request body for making a move."""
    move: str
    message: str = "What should I play next?"


class QuestionRequest(BaseModel):
    """Request body for asking a question without making a move."""
    message: str


class ResetRequest(BaseModel):
    """Request body for resetting the game."""
    confirm: bool = True


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "RS Chess Coach API is running",
        "version": "1.0.0"
    }


@app.get("/game/state")
def get_game_state():
    """
    Get current game state.
    Called by frontend on load and after each move
    to sync the board display.
    """
    context = game.get_context()
    return {
        "fen": context["fen"],
        "move_history": context["move_history"],
        "move_count": context["move_count"],
        "turn": context["turn"],
        "is_check": context["is_check"],
        "is_checkmate": context["is_checkmate"],
        "is_game_over": context["is_game_over"],
        "move_history_string": game.get_move_history_string()
    }


@app.post("/game/move")
def make_move(request: MoveRequest):
    """
    Make a move and get coaching response.

    Flow:
    1. Validate and apply the move to the board
    2. Get Stockfish analysis of the new position
    3. Retrieve relevant chess knowledge
    4. Return coaching response with best move + explanation

    If the move is invalid, returns an error without
    changing the game state.
    """
    # Apply the move
    move_result = game.make_move(request.move)

    if not move_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=move_result["error"]
        )

    # Get coaching response for the new position
    coaching = get_coaching_response(
        game,
        engine,
        request.message
    )

    return {
        "move_applied": move_result["move_san"],
        "fen": move_result["fen"],
        "move_number": move_result["move_number"],
        "is_check": move_result["is_check"],
        "is_checkmate": move_result["is_checkmate"],
        "is_game_over": move_result["is_game_over"],
        "coaching": {
            "response": coaching["response"],
            "best_move": coaching["best_move"],
            "evaluation": coaching["evaluation"],
            "mate_in": coaching.get("mate_in"),
            "sources": coaching["sources"]
        }
    }


@app.post("/game/ask")
def ask_question(request: QuestionRequest):
    """
    Ask a chess question without making a move.
    Useful for asking about the current position,
    requesting explanation of a concept, or getting
    advice before deciding on a move.
    """
    coaching = get_coaching_response(
        game,
        engine,
        request.message
    )

    return {
        "fen": game.get_context()["fen"],
        "coaching": {
            "response": coaching["response"],
            "best_move": coaching["best_move"],
            "evaluation": coaching["evaluation"],
            "mate_in": coaching.get("mate_in"),
            "sources": coaching["sources"]
        }
    }


@app.post("/game/reset")
def reset_game(request: ResetRequest):
    """
    Reset the game to starting position.
    Clears all move history and game state.
    """
    if request.confirm:
        game.reset()
        return {
            "status": "Game reset successfully",
            "fen": game.get_context()["fen"]
        }
    return {"status": "Reset cancelled"}


@app.get("/game/hint")
def get_hint():
    """
    Get the best move hint without making a move.
    Shows Stockfish recommendation for current position.
    """
    coaching = get_coaching_response(
        game,
        engine,
        "What is the best move in this position and why?"
    )

    return {
        "best_move": coaching["best_move"],
        "evaluation": coaching["evaluation"],
        "response": coaching["response"],
        "sources": coaching["sources"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
