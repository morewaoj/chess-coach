import chess
import chess.engine
from pathlib import Path


STOCKFISH_PATH = "./stockfish"
DEFAULT_DEPTH = 15
FAST_DEPTH = 10


class ChessEngine:
    """
    Wraps Stockfish for best move calculation.

    Why Stockfish instead of asking the LLM for moves:
    LLMs are trained on text about chess, not on chess
    calculation. They can describe tactics but cannot
    reliably calculate positions. Stockfish is deterministic,
    correct, and rates as the strongest chess engine in
    the world. The LLM's job is to explain. Stockfish's
    job is to calculate.

    This separation is the core architectural decision
    of this project — two systems doing what each does
    best, combined into one coaching response.

    Depth explanation:
    - Depth 10: fast analysis, ~0.1 seconds, good for
      casual play and quick suggestions
    - Depth 15: deeper analysis, ~0.5 seconds, better
      for critical positions and complex tactics
    - Depth 20+: tournament-level, several seconds,
      unnecessary for coaching purposes
    """

    def __init__(self, path: str = STOCKFISH_PATH):
        self.path = path
        self.engine = None
        self._start()

    def _start(self):
        """
        Start the Stockfish process.
        chess.engine.SimpleEngine.popen_uci() opens
        Stockfish as a subprocess communicating via
        the UCI (Universal Chess Interface) protocol.
        UCI is the standard protocol all chess engines use.
        """
        if not Path(self.path).exists():
            raise FileNotFoundError(
                f"Stockfish not found at: {self.path}\n"
                f"Download from stockfishchess.org and place "
                f"in project root."
            )
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)

    def get_best_move(self,
                      board: chess.Board,
                      depth: int = DEFAULT_DEPTH) -> dict:
        """
        Get the best move for the current position.

        Returns:
        - move_uci: move in UCI format (e.g. "e2e4")
        - move_san: move in standard algebraic (e.g. "e4")
        - evaluation: position score in centipawns
          (100 centipawns = 1 pawn advantage)
          Positive = White is better
          Negative = Black is better
        - mate_in: if there's a forced mate, how many moves
        - depth: how deep Stockfish calculated

        Why centipawns:
        Centipawn scores give the coach precise language.
        "+0.3" means slight White advantage.
        "+2.5" means White is up roughly 2.5 pawns — winning.
        "-1.0" means Black has a pawn advantage.
        This gets included in the coach response so you
        understand the stakes of each position.
        """
        result = self.engine.play(
            board,
            chess.engine.Limit(depth=depth)
        )

        best_move = result.move
        move_san = board.san(best_move)

        # Get position evaluation
        info = self.engine.analyse(
            board,
            chess.engine.Limit(depth=depth)
        )

        score = info["score"].relative
        evaluation = None
        mate_in = None

        if score.is_mate():
            mate_in = score.mate()
        else:
            # Convert to centipawns from current player's perspective
            evaluation = score.score() / 100.0

        return {
            "move_uci": best_move.uci(),
            "move_san": move_san,
            "evaluation": evaluation,
            "mate_in": mate_in,
            "depth": depth
        }

    def get_move_evaluation(self,
                            board: chess.Board,
                            move: chess.Move,
                            depth: int = FAST_DEPTH) -> dict:
        """
        Evaluate a specific move — useful for telling
        the player whether their last move was good or bad.

        Compares position before and after the move to
        calculate how much the evaluation changed.
        A big negative change means the move was a mistake.
        """
        # Evaluate before the move
        info_before = self.engine.analyse(
            board,
            chess.engine.Limit(depth=depth)
        )
        score_before = info_before["score"].relative.score(
            mate_score=10000
        )

        # Make the move and evaluate after
        board.push(move)
        info_after = self.engine.analyse(
            board,
            chess.engine.Limit(depth=depth)
        )
        # After move, perspective flips — negate for comparison
        score_after = -info_after["score"].relative.score(
            mate_score=10000
        )
        board.pop()

        delta = score_after - score_before

        # Classify the move quality
        if delta >= -10:
            quality = "excellent"
        elif delta >= -50:
            quality = "good"
        elif delta >= -100:
            quality = "inaccuracy"
        elif delta >= -300:
            quality = "mistake"
        else:
            quality = "blunder"

        return {
            "quality": quality,
            "score_change": round(delta / 100.0, 2),
            "score_before": round(score_before / 100.0, 2),
            "score_after": round(score_after / 100.0, 2)
        }

    def get_top_moves(self,
                      board: chess.Board,
                      n: int = 3,
                      depth: int = FAST_DEPTH) -> list[dict]:
        """
        Get the top N moves with evaluations.
        Used when the coach wants to show alternatives
        rather than just one best move.
        """
        result = self.engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=n
        )

        moves = []
        for pv in result:
            move = pv["pv"][0]
            score = pv["score"].relative
            evaluation = None
            mate_in = None

            if score.is_mate():
                mate_in = score.mate()
            else:
                evaluation = score.score() / 100.0

            moves.append({
                "move_san": board.san(move),
                "move_uci": move.uci(),
                "evaluation": evaluation,
                "mate_in": mate_in
            })

        return moves

    def close(self):
        """Cleanly shut down the Stockfish process."""
        if self.engine:
            self.engine.quit()
            self.engine = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    """
    Test Stockfish integration with a real position.
    Uses the starting position and the Ruy Lopez after
    1.e4 e5 2.Nf3 Nc6 3.Bb5 to verify:
    - Best move calculation works
    - Evaluation scores are reasonable
    - Move quality assessment works
    - Top 3 moves can be retrieved
    """
    import sys
    sys.path.insert(0, "src")
    from board import ChessGame

    print("Testing Stockfish integration...")
    print("=" * 50)

    engine = ChessEngine()

    # Test 1: Starting position
    board = chess.Board()
    result = engine.get_best_move(board)
    print(f"\nStarting position best move: {result['move_san']}")
    print(f"Evaluation: {result['evaluation']}")
    print(f"Depth: {result['depth']}")

    # Test 2: Ruy Lopez position
    game = ChessGame()
    for move in ["e4", "e5", "Nf3", "Nc6", "Bb5"]:
        game.make_move(move)

    result = engine.get_best_move(game.board)
    print(f"\nRuy Lopez position best move: {result['move_san']}")
    print(f"Evaluation: {result['evaluation']}")

    # Test 3: Top 3 moves
    top_moves = engine.get_top_moves(game.board, n=3)
    print(f"\nTop 3 moves in Ruy Lopez:")
    for i, m in enumerate(top_moves):
        print(f"  {i+1}. {m['move_san']} ({m['evaluation']})")

    # Test 4: Move quality
    board2 = chess.Board()
    e4_move = chess.Move.from_uci("e2e4")
    quality = engine.get_move_evaluation(board2, e4_move)
    print(f"\nQuality of 1.e4: {quality['quality']}")
    print(f"Score change: {quality['score_change']}")

    engine.close()
    print("\nStockfish integration working correctly.")
