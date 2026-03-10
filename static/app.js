const setupPanel = document.getElementById('setup-panel');
const gamePanel = document.getElementById('game-panel');
const resultPanel = document.getElementById('result-panel');
const boardEl = document.getElementById('board');
const noticeEl = document.getElementById('notice');
const turnLabelEl = document.getElementById('turn-label');
const blackScoreEl = document.getElementById('black-score');
const whiteScoreEl = document.getElementById('white-score');
const resultTextEl = document.getElementById('result-text');

let gameState = null;

function playerText(player) {
  if (player === 1) return '흑(플레이어)';
  if (player === -1) return '백(AI)';
  return '-';
}

function setNotice(text) {
  noticeEl.textContent = text || '';
}

function drawBoard(state) {
  const size = state.size;
  const validSet = new Set(state.valid_moves.map(([r, c]) => `${r},${c}`));

  boardEl.innerHTML = '';
  boardEl.style.gridTemplateColumns = `repeat(${size}, 1fr)`;

  for (let r = 0; r < size; r += 1) {
    for (let c = 0; c < size; c += 1) {
      const cell = document.createElement('div');
      cell.className = 'cell';
      if (!state.game_over && state.current_player === 1 && validSet.has(`${r},${c}`)) {
        cell.classList.add('valid');
      }
      cell.addEventListener('click', () => onCellClick(r, c));

      const stone = state.board[r][c];
      if (stone !== 0) {
        const piece = document.createElement('div');
        piece.className = `stone ${stone === 1 ? 'black' : 'white'}`;
        cell.appendChild(piece);
      }
      boardEl.appendChild(cell);
    }
  }
}

function renderState(state) {
  gameState = state;
  turnLabelEl.textContent = playerText(state.current_player);
  blackScoreEl.textContent = state.black_score;
  whiteScoreEl.textContent = state.white_score;

  drawBoard(state);

  if (state.pass_message) {
    setNotice(state.pass_message);
  }

  if (state.game_over) {
    const winnerText = state.winner === 1
      ? '플레이어(흑) 승리'
      : state.winner === -1
        ? 'AI(백) 승리'
        : '무승부';

    resultTextEl.textContent = `최종 점수 - 흑 ${state.black_score} : 백 ${state.white_score} / ${winnerText}`;
    resultPanel.classList.remove('hidden');
    turnLabelEl.textContent = '게임 종료';
  } else {
    resultPanel.classList.add('hidden');
  }
}

async function api(url, method = 'GET', body = null) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || '요청 중 오류가 발생했습니다.');
  }
  return data;
}

async function onCellClick(row, col) {
  if (!gameState || gameState.game_over || gameState.current_player !== 1) return;

  try {
    const data = await api('/api/move', 'POST', { row, col });
    renderState(data.state);
    const msg = [data.message, data.ai_message, data.state.pass_message].filter(Boolean).join(' / ');
    setNotice(msg);
  } catch (err) {
    setNotice(err.message);
  }
}

document.getElementById('start-btn').addEventListener('click', async () => {
  const size = Number(document.getElementById('board-size').value);
  const difficulty = document.getElementById('difficulty').value;

  try {
    const data = await api('/api/start', 'POST', { size, difficulty });
    setupPanel.classList.add('hidden');
    gamePanel.classList.remove('hidden');
    resultPanel.classList.add('hidden');
    setNotice(data.message);
    renderState(data.state);
  } catch (err) {
    setNotice(err.message);
  }
});

document.getElementById('forfeit-btn').addEventListener('click', async () => {
  try {
    const data = await api('/api/forfeit', 'POST');
    renderState(data.state);
    setNotice(data.state.pass_message || data.message);
  } catch (err) {
    setNotice(err.message);
  }
});

document.getElementById('restart-btn').addEventListener('click', async () => {
  try {
    await api('/api/restart', 'POST');
    gameState = null;
    boardEl.innerHTML = '';
    setupPanel.classList.remove('hidden');
    gamePanel.classList.add('hidden');
    resultPanel.classList.add('hidden');
    setNotice('게임이 초기화되었습니다. 새 설정으로 시작하세요.');
  } catch (err) {
    setNotice(err.message);
  }
});
