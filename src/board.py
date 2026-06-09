import chess
import re
from typing import Optional


class ChessGame:
    """
    Tracks the complete state of a chess game.

    Why this exists as a separate class:
    The LLM has no memory between API calls. Without explicit
    game state tracking, every question would be answered in
    isolation — the coach couldn't say "given that you played
    the Sicilian three moves ago, now you should..."

    This class maintains:
    - The actual board position (python-chess Board object)
    - The full move history in algebraic notation
    - The detected opening name
    - Any position notes the coach generates

    The board state is serialized to FEN notation when passed
    to Stockfish and included in the LLM context. FEN is a
    standard string that encodes the complete position —
    every chess engine and library understands it.
    """

    def __init__(self):
        self.board = chess.Board()
        self.move_history = []
        self.opening_name = None
        self.position_notes = []

    def reset(self):
        """Start a new game — clears all state."""
        self.board = chess.Board()
        self.move_history = []
        self.opening_name = None
        self.position_notes = []

    def parse_move(self, move_input: str) -> Optional[chess.Move]:
        """
        Parse a move from either algebraic notation or
        plain English description.

        Handles both:
        - Standard algebraic: "e4", "Nf3", "Bb5+", "O-O"
        - Plain English: "pawn to e4", "knight to f3",
          "bishop to b5", "castle kingside"

        Why both formats:
        Players at 1200-1800 know notation but may describe
        moves conversationally mid-game. The coach should
        understand both without forcing the user to be precise.
        """
        move_input = move_input.strip()

        # Try direct algebraic notation first
        try:
            move = self.board.parse_san(move_input)
            return move
        except Exception:
            pass

        # Try UCI format (e.g. e2e4)
        try:
            move = chess.Move.from_uci(move_input.lower())
            if move in self.board.legal_moves:
                return move
        except Exception:
            pass

        # Parse plain English descriptions
        plain = move_input.lower()

        # Handle castling
        if any(w in plain for w in ["castle kingside", "kingside castle",
                                     "short castle", "o-o"]):
            try:
                return self.board.parse_san("O-O")
            except Exception:
                pass

        if any(w in plain for w in ["castle queenside", "queenside castle",
                                     "long castle", "o-o-o"]):
            try:
                return self.board.parse_san("O-O-O")
            except Exception:
                pass

        # Extract square from plain English
        # Looks for patterns like "to e4", "e4", "e-4"
        square_pattern = r'\b([a-h][-]?[1-8])\b'
        squares = re.findall(square_pattern, plain.replace("-", ""))

        if squares:
            target_square = squares[-1]
            # Try all legal moves that land on target square
            for legal_move in self.board.legal_moves:
                if chess.square_name(legal_move.to_square) == target_square:
                    # If piece type mentioned, match it
                    piece_map = {
                        "pawn": chess.PAWN,
                        "knight": chess.KNIGHT,
                        "bishop": chess.BISHOP,
                        "rook": chess.ROOK,
                        "queen": chess.QUEEN,
                        "king": chess.KING
                    }
                    for piece_word, piece_type in piece_map.items():
                        if piece_word in plain:
                            piece = self.board.piece_at(
                                legal_move.from_square
                            )
                            if piece and piece.piece_type == piece_type:
                                return legal_move
                    # No piece specified — return first legal move
                    # to that square
                    return legal_move

        return None

    def make_move(self, move_input: str) -> dict:
        """
        Apply a move to the board and record it.

        Returns a result dict with:
        - success: whether the move was valid
        - move_san: the move in standard algebraic notation
        - fen: the new board position in FEN notation
        - move_number: which move this is
        - error: description if move failed
        """
        move = self.parse_move(move_input)

        if move is None:
            return {
                "success": False,
                "error": f"Could not parse move: '{move_input}'. "
                         f"Try algebraic notation like 'e4' or 'Nf3'."
            }

        if move not in self.board.legal_moves:
            return {
                "success": False,
                "error": f"Illegal move: '{move_input}' in this position."
            }

        # Record move in standard algebraic notation
        move_san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(move_san)

        return {
            "success": True,
            "move_san": move_san,
            "fen": self.board.fen(),
            "move_number": len(self.move_history),
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_game_over": self.board.is_game_over()
        }

    def get_context(self) -> dict:
        """
        Return complete game context for the coach.

        This dict gets passed to both Stockfish (for best move
        calculation) and the LLM prompt (for explanation).
        It contains everything needed to understand the
        current position without seeing the board visually.
        """
        return {
            "fen": self.board.fen(),
            "move_history": self.move_history,
            "move_count": len(self.move_history),
            "turn": "White" if self.board.turn == chess.WHITE else "Black",
            "opening_name": self.opening_name,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_game_over": self.board.is_game_over(),
            "legal_moves_count": self.board.legal_moves.count()
        }

    def get_move_history_string(self) -> str:
        """
        Format move history as a readable string.
        Example: "1. e4 e5 2. Nf3 Nc6 3. Bb5"
        This is included in every prompt so the LLM
        understands the full game narrative.
        """
        if not self.move_history:
            return "No moves played yet — game just started."

        pairs = []
        for i in range(0, len(self.move_history), 2):
            move_num = (i // 2) + 1
            white = self.move_history[i]
            black = self.move_history[i + 1] if i + 1 < len(
                self.move_history) else ""
            pairs.append(f"{move_num}. {white} {black}".strip())

        return " ".join(pairs)


if __name__ == "__main__":
    """
    Test the game state tracker with a real opening sequence.
    Plays the first 5 moves of the Ruy Lopez and verifies
    that move parsing, FEN generation, and history tracking
    all work correctly.
    """
    game = ChessGame()

    test_moves = [
        "e4",           # White pawn to e4
        "e5",           # Black pawn to e5
        "Nf3",          # White knight to f3
        "Nc6",          # Black knight to c6
        "Bb5",          # White bishop to b5 — Ruy Lopez
    ]

    print("Testing Ruy Lopez opening sequence:")
    print("=" * 50)

    for move in test_moves:
        result = game.make_move(move)
        if result["success"]:
            print(f"Move: {result['move_san']} | "
                  f"Move #{result['move_number']}")
        else:
            print(f"ERROR: {result['error']}")

    print(f"\nMove history: {game.get_move_history_string()}")
    print(f"Current FEN: {game.get_context()['fen']}")
    print(f"Turn: {game.get_context()['turn']}")
    print(f"Legal moves available: {game.get_context()['legal_moves_count']}")

    print("\nTesting plain English input:")
    game2 = ChessGame()
    result = game2.make_move("pawn to e4")
    print(f"'pawn to e4' parsed as: {result.get('move_san', result.get('error'))}")
