import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import api
from board import ChessGame


def fake_coaching_response():
    return {
        "response": "coach response",
        "best_move": "Nf3",
        "evaluation": 0.25,
        "mate_in": None,
        "sources": ["openings_sicilian.txt"],
    }


def fake_engine_response():
    return {
        "move_san": "Nf3",
        "move_uci": "g1f3",
        "evaluation": 0.25,
        "mate_in": None,
    }


class BackendSmokeTests(unittest.TestCase):
    def setUp(self):
        api.game.reset()
        api.shutdown_engine()
        self.client = TestClient(api.app)

    def tearDown(self):
        api.shutdown_engine()

    def test_import_does_not_start_engine(self):
        self.assertIsNone(api._engine)

    def test_root_and_game_state(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["version"], "1.0.0")

        state = self.client.get("/game/state")
        self.assertEqual(state.status_code, 200)
        body = state.json()
        self.assertEqual(body["turn"], "White")
        self.assertEqual(body["move_count"], 0)
        self.assertEqual(body["move_history_string"], "No moves played yet.")

    def test_invalid_move_returns_400_without_changing_state(self):
        response = self.client.post("/game/move", json={"move": "not a move"})
        self.assertEqual(response.status_code, 400)

        state = self.client.get("/game/state").json()
        self.assertEqual(state["move_count"], 0)
        self.assertEqual(state["turn"], "White")

    def test_make_move_returns_coaching_payload(self):
        fake_engine = Mock()
        with patch.object(api, "get_engine", return_value=fake_engine):
            with patch.object(
                api,
                "get_coaching_response",
                return_value=fake_coaching_response(),
            ) as coaching:
                response = self.client.post(
                    "/game/move",
                    json={"move": "e4", "message": "What next?"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["move_applied"], "e4")
        self.assertEqual(body["move_number"], 1)
        self.assertEqual(body["coaching"]["best_move"], "Nf3")
        coaching.assert_called_once_with(api.game, fake_engine, "What next?")

    def test_best_move_endpoint_does_not_call_coach(self):
        fake_engine = Mock()
        fake_engine.get_best_move.return_value = fake_engine_response()

        with patch.object(api, "get_engine", return_value=fake_engine):
            with patch.object(api, "get_coaching_response") as coaching:
                response = self.client.get("/game/best-move")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["best_move"], "Nf3")
        self.assertEqual(body["move_uci"], "g1f3")
        coaching.assert_not_called()

    def test_coaching_failure_returns_engine_fallback(self):
        fake_engine = Mock()
        fake_engine.get_best_move.return_value = fake_engine_response()

        with patch.object(api, "get_engine", return_value=fake_engine):
            with patch.object(
                api,
                "get_coaching_response",
                side_effect=RuntimeError("rate limited"),
            ):
                response = self.client.post(
                    "/game/ask",
                    json={"message": "What should I play?"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        coaching = body["coaching"]
        self.assertEqual(coaching["best_move"], "Nf3")
        self.assertIn("AI coaching layer", coaching["response"])
        self.assertIn("rate limited", coaching["response"])

    def test_reset_clears_game_state(self):
        api.game.make_move("e4")

        response = self.client.post("/game/reset", json={"confirm": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Game reset successfully")

        state = self.client.get("/game/state").json()
        self.assertEqual(state["move_count"], 0)
        self.assertEqual(state["turn"], "White")


class ChessGameTests(unittest.TestCase):
    def test_move_parser_accepts_san_uci_and_plain_english(self):
        game = ChessGame()

        self.assertEqual(game.make_move("e2e4")["move_san"], "e4")
        self.assertEqual(game.make_move("pawn to e5")["move_san"], "e5")
        self.assertEqual(game.make_move("Nf3")["move_san"], "Nf3")
        self.assertEqual(game.get_move_history_string(), "1. e4 e5 2. Nf3")

    def test_uci_move_illegal_for_position_gets_clear_error(self):
        game = ChessGame()
        self.assertTrue(game.make_move("e2e3")["success"])

        result = game.make_move("e2e4")
        self.assertFalse(result["success"])
        self.assertIn("Illegal move for current position", result["error"])
        self.assertIn("Black's turn", result["error"])


if __name__ == "__main__":
    unittest.main()
