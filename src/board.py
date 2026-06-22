import chess
import re
from typing import Optional


class ChessGame:
    """
    Tracks the complete state of a chess game.

    Maintains board position, move history, and game state
    across multiple API calls. Without this class the coach
    would have no memory of what was played.
    """

    def __init__(self):
        self.board = chess.Board()
        self.move_history = []
        self.opening_name = None
        self.position_notes = []

    def reset(self):
        self.board = chess.Board()
        self.move_history = []
        self.opening_name = None
        self.position_notes = []

    def make_move(self, move_input: str) -> dict:
        """
        Accept a move in ANY format:
        - UCI:        e2e4, c7c5, g1f3
        - Algebraic:  e4, Nf3, Bb5+, O-O
        - Plain text: pawn to e4, knight f3

        Strategy: try every known format in order.
        First success wins.
        """
        move_input = move_input.strip()
        move = None
        parsed_but_illegal = None

        # 1. Try UCI format (e.g. e2e4, c7c5, g1f3, e7e8q)
        uci_pattern = re.match(
            r'^([a-h][1-8])([a-h][1-8])([qrbn]?)$',
            move_input.lower()
        )
        if uci_pattern:
            try:
                uci_str = move_input.lower()
                candidate = chess.Move.from_uci(uci_str)
                if candidate in self.board.legal_moves:
                    move = candidate
                else:
                    parsed_but_illegal = candidate
            except Exception:
                pass

        # 2. Try standard algebraic notation (e4, Nf3, O-O)
        if move is None:
            try:
                move = self.board.parse_san(move_input)
            except Exception:
                pass

        # 3. Try plain English (pawn to e4, knight to f3)
        if move is None:
            move = self._parse_plain_english(move_input)

        # 4. Last resort — try as UCI with lowercase
        if move is None:
            try:
                candidate = chess.Move.from_uci(
                    move_input.lower()
                )
                if candidate in self.board.legal_moves:
                    move = candidate
            except Exception:
                pass

        if move is None:
            if parsed_but_illegal is not None:
                return {
                    "success": False,
                    "error": (
                        f"Illegal move for current position: '{move_input}'. "
                        f"It is {self.get_context()['turn']}'s turn. "
                        f"Current move history: {self.get_move_history_string()}"
                    )
                }
            return {
                "success": False,
                "error": (
                    f"Could not parse: '{move_input}'. "
                    f"Try e4, Nf3, or drag a piece."
                )
            }

        if move not in self.board.legal_moves:
            return {
                "success": False,
                "error": f"Illegal move: '{move_input}'."
            }

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

    def _parse_plain_english(self,
                              text: str) -> Optional[chess.Move]:
        """Parse plain English move descriptions."""
        text = text.lower().strip()

        # Castling
        if any(w in text for w in [
            "castle kingside", "kingside castle",
            "short castle", "o-o"
        ]):
            try:
                return self.board.parse_san("O-O")
            except Exception:
                pass

        if any(w in text for w in [
            "castle queenside", "queenside castle",
            "long castle", "o-o-o"
        ]):
            try:
                return self.board.parse_san("O-O-O")
            except Exception:
                pass

        # Extract target square
        squares = re.findall(r'\b([a-h][1-8])\b', text)
        if not squares:
            return None

        target = squares[-1]
        piece_map = {
            "pawn": chess.PAWN,
            "knight": chess.KNIGHT,
            "bishop": chess.BISHOP,
            "rook": chess.ROOK,
            "queen": chess.QUEEN,
            "king": chess.KING
        }

        for legal_move in self.board.legal_moves:
            if chess.square_name(legal_move.to_square) == target:
                for word, piece_type in piece_map.items():
                    if word in text:
                        piece = self.board.piece_at(
                            legal_move.from_square
                        )
                        if piece and piece.piece_type == piece_type:
                            return legal_move
                return legal_move

        return None

    def get_context(self) -> dict:
        return {
            "fen": self.board.fen(),
            "move_history": self.move_history,
            "move_count": len(self.move_history),
            "turn": "White" if self.board.turn == chess.WHITE
                    else "Black",
            "opening_name": self.opening_name,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_game_over": self.board.is_game_over(),
            "legal_moves_count": self.board.legal_moves.count()
        }

    def get_move_history_string(self) -> str:
        if not self.move_history:
            return "No moves played yet."

        pairs = []
        for i in range(0, len(self.move_history), 2):
            move_num = (i // 2) + 1
            white = self.move_history[i]
            black = (self.move_history[i + 1]
                     if i + 1 < len(self.move_history) else "")
            pairs.append(f"{move_num}. {white} {black}".strip())

        return " ".join(pairs)
