from __future__ import annotations

import math
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = "odello-secret-key"  # 데모용 키(실서비스에서는 환경변수 사용 권장)

EMPTY = 0
BLACK = 1
WHITE = -1
DIRECTIONS = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]


@dataclass
class MoveEval:
    score: float
    move: Optional[Tuple[int, int]]


class OthelloGame:
    """오델로 규칙(유효수 판정/뒤집기/게임종료/AI 탐색)을 담당하는 클래스."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.board = [[EMPTY for _ in range(size)] for _ in range(size)]
        self.current_player = BLACK
        self.game_over = False
        self.winner = 0
        self.pass_message = ""
        self._setup_initial_board()

    def _setup_initial_board(self) -> None:
        # 중앙 4칸에 초기 돌 배치
        c1 = self.size // 2 - 1
        c2 = self.size // 2
        self.board[c1][c1] = WHITE
        self.board[c2][c2] = WHITE
        self.board[c1][c2] = BLACK
        self.board[c2][c1] = BLACK

    def _inside(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def _collect_flips(self, board: List[List[int]], row: int, col: int, player: int) -> List[Tuple[int, int]]:
        # 특정 위치에 player를 두었을 때 뒤집히는 좌표 목록 계산
        if board[row][col] != EMPTY:
            return []

        flips: List[Tuple[int, int]] = []
        for dr, dc in DIRECTIONS:
            path: List[Tuple[int, int]] = []
            r, c = row + dr, col + dc
            while self._inside(r, c) and board[r][c] == -player:
                path.append((r, c))
                r += dr
                c += dc
            if path and self._inside(r, c) and board[r][c] == player:
                flips.extend(path)
        return flips

    def valid_moves(self, board: Optional[List[List[int]]] = None, player: Optional[int] = None) -> List[Tuple[int, int]]:
        board = board if board is not None else self.board
        player = player if player is not None else self.current_player
        moves = []
        for r in range(self.size):
            for c in range(self.size):
                if self._collect_flips(board, r, c, player):
                    moves.append((r, c))
        return moves

    def apply_move(self, row: int, col: int, player: Optional[int] = None, board: Optional[List[List[int]]] = None) -> bool:
        # 실제 게임 진행/탐색 공통으로 사용하는 착수 함수
        board = board if board is not None else self.board
        player = player if player is not None else self.current_player

        flips = self._collect_flips(board, row, col, player)
        if not flips:
            return False

        board[row][col] = player
        for r, c in flips:
            board[r][c] = player
        return True

    def count_stones(self, board: Optional[List[List[int]]] = None) -> Tuple[int, int]:
        board = board if board is not None else self.board
        black = sum(cell == BLACK for row in board for cell in row)
        white = sum(cell == WHITE for row in board for cell in row)
        return black, white

    def _finalize_winner(self) -> None:
        black, white = self.count_stones()
        if black > white:
            self.winner = BLACK
        elif white > black:
            self.winner = WHITE
        else:
            self.winner = 0
        self.game_over = True

    def _maybe_handle_pass_or_end(self) -> None:
        current_moves = self.valid_moves(self.board, self.current_player)
        if current_moves:
            self.pass_message = ""
            return

        # 현재 플레이어가 둘 수 없으면 패스
        self.current_player *= -1
        other_moves = self.valid_moves(self.board, self.current_player)
        if other_moves:
            who = "흑" if -self.current_player == BLACK else "백"
            self.pass_message = f"{who} 플레이어가 둘 수 없어 자동 패스되었습니다."
            return

        # 양쪽 모두 둘 수 없으면 종료
        self.pass_message = "양쪽 모두 둘 수 있는 수가 없어 게임이 종료되었습니다."
        self._finalize_winner()

    def player_move(self, row: int, col: int) -> Tuple[bool, str]:
        if self.game_over:
            return False, "이미 게임이 종료되었습니다."
        if self.current_player != BLACK:
            return False, "지금은 플레이어의 턴이 아닙니다."
        if not self.apply_move(row, col):
            return False, "유효하지 않은 위치입니다."

        self.current_player = WHITE
        self._maybe_handle_pass_or_end()
        return True, "정상적으로 착수했습니다."

    def ai_move(self, difficulty: str) -> str:
        if self.game_over or self.current_player != WHITE:
            return ""

        moves = self.valid_moves(self.board, WHITE)
        if not moves:
            self.current_player = BLACK
            self._maybe_handle_pass_or_end()
            return "AI가 둘 수 없어 패스했습니다."

        if difficulty == "easy":
            move = random.choice(moves)
        elif difficulty == "medium":
            move = self._pick_medium_move(moves)
        else:
            move = self._pick_hard_move()

        self.apply_move(move[0], move[1], WHITE)
        self.current_player = BLACK
        self._maybe_handle_pass_or_end()
        return f"AI가 ({move[0] + 1}, {move[1] + 1}) 위치에 착수했습니다."

    def _pick_medium_move(self, moves: List[Tuple[int, int]]) -> Tuple[int, int]:
        # 기본 휴리스틱: 코너 > 가장자리 > 최대 뒤집기 수
        corners = {
            (0, 0),
            (0, self.size - 1),
            (self.size - 1, 0),
            (self.size - 1, self.size - 1),
        }

        corner_moves = [m for m in moves if m in corners]
        if corner_moves:
            return random.choice(corner_moves)

        edge_moves = [
            (r, c)
            for r, c in moves
            if r in (0, self.size - 1) or c in (0, self.size - 1)
        ]
        candidates = edge_moves if edge_moves else moves

        # 동일 우선순위 내에서는 뒤집는 돌 수가 큰 수를 선택
        best = max(candidates, key=lambda mv: len(self._collect_flips(self.board, mv[0], mv[1], WHITE)))
        return best

    def _pick_hard_move(self) -> Tuple[int, int]:
        # 보드 크기가 커질수록 탐색 비용이 커지므로 깊이를 제한
        depth = 4 if self.size <= 8 else 3
        result = self._minimax(self.board, WHITE, depth, -math.inf, math.inf)
        return result.move if result.move is not None else random.choice(self.valid_moves(self.board, WHITE))

    def _minimax(
        self,
        board: List[List[int]],
        player: int,
        depth: int,
        alpha: float,
        beta: float,
    ) -> MoveEval:
        moves = self.valid_moves(board, player)
        opponent_moves = self.valid_moves(board, -player)

        # 종료/깊이 한계 조건
        if depth == 0 or (not moves and not opponent_moves):
            return MoveEval(self._evaluate_board(board), None)

        # 현재 플레이어가 둘 수 없으면 패스 처리
        if not moves:
            return self._minimax(board, -player, depth - 1, alpha, beta)

        maximizing = player == WHITE
        best_move: Optional[Tuple[int, int]] = None

        if maximizing:
            value = -math.inf
            for move in moves:
                new_board = deepcopy(board)
                self.apply_move(move[0], move[1], player, new_board)
                child = self._minimax(new_board, -player, depth - 1, alpha, beta)
                if child.score > value:
                    value = child.score
                    best_move = move
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return MoveEval(value, best_move)

        value = math.inf
        for move in moves:
            new_board = deepcopy(board)
            self.apply_move(move[0], move[1], player, new_board)
            child = self._minimax(new_board, -player, depth - 1, alpha, beta)
            if child.score < value:
                value = child.score
                best_move = move
            beta = min(beta, value)
            if beta <= alpha:
                break
        return MoveEval(value, best_move)

    def _evaluate_board(self, board: List[List[int]]) -> float:
        # 휴리스틱 평가: 돌 개수 + 코너 점수 + 가장자리 점수 + 기동성
        black, white = self.count_stones(board)
        stone_score = (white - black) * 1.0

        corners = [(0, 0), (0, self.size - 1), (self.size - 1, 0), (self.size - 1, self.size - 1)]
        corner_score = 0
        for r, c in corners:
            if board[r][c] == WHITE:
                corner_score += 25
            elif board[r][c] == BLACK:
                corner_score -= 25

        edge_score = 0
        for i in range(self.size):
            for r, c in ((0, i), (self.size - 1, i), (i, 0), (i, self.size - 1)):
                if board[r][c] == WHITE:
                    edge_score += 2
                elif board[r][c] == BLACK:
                    edge_score -= 2

        mobility = len(self.valid_moves(board, WHITE)) - len(self.valid_moves(board, BLACK))
        mobility_score = mobility * 3

        return stone_score + corner_score + edge_score + mobility_score

    def to_dict(self) -> dict:
        black, white = self.count_stones()
        return {
            "size": self.size,
            "board": self.board,
            "current_player": self.current_player,
            "valid_moves": self.valid_moves(),
            "black_score": black,
            "white_score": white,
            "game_over": self.game_over,
            "winner": self.winner,
            "pass_message": self.pass_message,
        }


def save_game(game: OthelloGame, difficulty: str) -> None:
    session["game"] = {
        "size": game.size,
        "board": game.board,
        "current_player": game.current_player,
        "game_over": game.game_over,
        "winner": game.winner,
        "pass_message": game.pass_message,
        "difficulty": difficulty,
    }


def load_game() -> Tuple[Optional[OthelloGame], Optional[str]]:
    raw = session.get("game")
    if not raw:
        return None, None

    game = OthelloGame(raw["size"])
    game.board = raw["board"]
    game.current_player = raw["current_player"]
    game.game_over = raw["game_over"]
    game.winner = raw["winner"]
    game.pass_message = raw.get("pass_message", "")
    return game, raw.get("difficulty", "easy")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/start")
def start_game():
    payload = request.get_json(force=True)
    size = int(payload.get("size", 8))
    difficulty = payload.get("difficulty", "easy")

    if size not in (6, 8, 10):
        return jsonify({"error": "지원하지 않는 보드 크기입니다."}), 400
    if difficulty not in ("easy", "medium", "hard"):
        return jsonify({"error": "지원하지 않는 난이도입니다."}), 400

    game = OthelloGame(size)
    save_game(game, difficulty)
    return jsonify({"message": "게임이 시작되었습니다.", "state": game.to_dict()})


@app.get("/api/state")
def game_state():
    game, difficulty = load_game()
    if not game:
        return jsonify({"error": "진행 중인 게임이 없습니다."}), 404
    return jsonify({"difficulty": difficulty, "state": game.to_dict()})


@app.post("/api/move")
def player_move():
    game, difficulty = load_game()
    if not game:
        return jsonify({"error": "진행 중인 게임이 없습니다."}), 404

    payload = request.get_json(force=True)
    row = int(payload.get("row", -1))
    col = int(payload.get("col", -1))

    if not game._inside(row, col):
        return jsonify({"error": "보드 범위를 벗어난 좌표입니다."}), 400

    ok, msg = game.player_move(row, col)
    if not ok:
        save_game(game, difficulty)
        return jsonify({"error": msg, "state": game.to_dict()}), 400

    ai_msg = ""
    if not game.game_over:
        ai_msg = game.ai_move(difficulty or "easy")

    save_game(game, difficulty or "easy")
    return jsonify({"message": msg, "ai_message": ai_msg, "state": game.to_dict()})


@app.post("/api/forfeit")
def forfeit():
    game, difficulty = load_game()
    if not game:
        return jsonify({"error": "진행 중인 게임이 없습니다."}), 404

    game.game_over = True
    game.winner = WHITE
    game.pass_message = "플레이어가 포기하여 AI 승리로 종료되었습니다."
    save_game(game, difficulty or "easy")
    return jsonify({"message": "포기 처리되었습니다.", "state": game.to_dict()})


@app.post("/api/restart")
def restart():
    session.pop("game", None)
    return jsonify({"message": "게임이 초기화되었습니다."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
