# Benchmark: a small local LLM, with and without search

How much better does a small language model play when it can call pyplAI's search through this
server? The benchmark lets a model served locally with [Ollama](https://ollama.com) play full
games through the real MCP server, with no human in the loop, and compares it with pyplAI's search
alone and with random play.

## Method

`run.py` starts the server over stdio and acts as both the MCP client and the agent: it turns the
server's tools into Ollama tool definitions and lets the model play whole games through them.

| Player | What it does each turn |
| --- | --- |
| `llm` | The model sees the board as its player sees it and its legal moves, and calls `play_move`. |
| `llm+search` | The same, but it can also call `analyze_position` first, which ranks its legal moves by the share of simulated games they win. The system prompt says so and nothing more: the model decides when to call it and whether to follow it. |
| `search` | Plays the move `analyze_position` ranks best. The ceiling for `llm+search`. |
| `random` | Plays a random legal move. The floor. |

- **Model:** Llama 3.2 3B (`llama3.2:3b`, Q4_K_M, 2.0 GB), temperature 0, with Ollama's default
  4,096-token context (each turn starts a new conversation; prompts average 400 to 1,000 tokens per call), on an RTX 3050 Ti
  laptop GPU with 4 GB, which holds 80% of the model. Qwen3 4B was also tried: it kept reasoning at length even with thinking turned
  off and took 16 minutes for one game of tic-tac-toe, so it was dropped.
- **Opponents:** the strongest pyplAI algorithm the server offers for each game, with 0.2 seconds per
  move: MCTS in tic-tac-toe and Ultimate tic-tac-toe, and MO-ISMCTS in Phantom (4,4,4), where the
  model cannot see its opponent's stones.
- **Search budget:** `analyze_position` runs for 1 second, the same for `llm+search` and `search`. The
  harness fixes it and fills in `game_id`, so the model only chooses moves.
- **Games:** 100 per player in tic-tac-toe and Phantom, and 40 in Ultimate. Game `n` uses seed `n` for
  the opponent, and the benchmarked player moves first in even games and second in odd ones.
- **Mistakes:** an illegal move comes back as a tool error with the legal moves, as it would for any
  client, and a reply without a tool call gets a reminder. Replies are capped at 512 tokens (a tool
  call takes under 100), because the model sometimes falls into a loop of text: before the cap, one
  reply in Ultimate ran to 42,000 tokens. A cut reply counts as an attempt. After 6 attempts in one turn the harness
  plays a random legal move and records it as a fallback.

Every game is one row of `results.csv`: result, turns, illegal moves, replies without a tool call,
fallbacks, analyses, moves played after an analysis and how many of those were the search's best
move, tokens and seconds. `summary.py` turns it into the table below, with 95% Wilson intervals.

## Results

960 games: tic-tac-toe and Phantom run on 14 October 2026, and Ultimate tic-tac-toe on 15 October,
after a change that made its rules about three times as fast to search (see below). `summary.py`
prints these tables from `results.csv`.

| Game | Player | Model | Games | Wins [95% CI] | Draws | Losses [95% CI] | Analysed | Follows | Illegal moves / game | Fallback moves / game | Median seconds / game |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tictactoe | llm | llama3.2:3b | 100 | 0% [0-4] | 0% | 100% [96-100] | - | - | 0.00 | 0.00 | 1 |
| tictactoe | llm+search | llama3.2:3b | 100 | 3% [1-8] | 66% | 31% [23-41] | 100% | 80% | 0.00 | 0.00 | 9 |
| tictactoe | search | - | 100 | 0% [0-4] | 100% | 0% [0-4] | - | - | 0.00 | 0.00 | 5 |
| tictactoe | random | - | 100 | 0% [0-4] | 8% | 92% [85-96] | - | - | 0.00 | 0.00 | 1 |
| ultimate | llm | llama3.2:3b | 40 | 0% [0-9] | 0% | 100% [91-100] | - | - | 0.10 | 0.00 | 10 |
| ultimate | llm+search | llama3.2:3b | 40 | 0% [0-9] | 8% | 92% [80-97] | 67% | 60% | 0.00 | 0.50 | 46 |
| ultimate | search | - | 40 | 82% [68-91] | 8% | 10% [4-23] | - | - | 0.00 | 0.00 | 28 |
| ultimate | random | - | 40 | 0% [0-9] | 0% | 100% [91-100] | - | - | 0.00 | 0.00 | 4 |
| phantom | llm | llama3.2:3b | 100 | 57% [47-66] | 1% | 42% [33-52] | - | - | 0.00 | 0.00 | 2 |
| phantom | llm+search | llama3.2:3b | 100 | 45% [36-55] | 28% | 27% [19-36] | 100% | 91% | 0.00 | 0.00 | 12 |
| phantom | search | - | 100 | 48% [38-58] | 32% | 20% [13-29] | - | - | 0.00 | 0.00 | 6 |
| phantom | random | - | 100 | 1% [0-5] | 25% | 74% [65-82] | - | - | 0.00 | 0.00 | 1 |

| Game | LLM with search | Games | Wins | Draws | Losses |
| --- | --- | --- | --- | --- | --- |
| tictactoe | followed every move | 34 | 0 | 34 | 0 |
| tictactoe | deviated at least once | 66 | 3 | 32 | 31 |
| ultimate | followed every move | 0 | 0 | 0 | 0 |
| ultimate | deviated at least once | 40 | 0 | 3 | 37 |
| phantom | followed every move | 56 | 28 | 5 | 23 |
| phantom | deviated at least once | 44 | 17 | 23 | 4 |

What the numbers say:

- **On its own, the model plays the perfect-information games no better than chance.** It lost all
  100 games of tic-tac-toe and all 40 of Ultimate, where random play lost 92% and 100%. It made
  almost no illegal moves: the problem is choosing, not following the rules.
- **In tic-tac-toe the search tool cut its losses from 100% to 31%.** It analysed before every move
  but played the recommended move 80% of the time. In the 34 games where it followed every
  recommendation it drew all 34, as the search does on its own; all 31 losses came from games where
  it overrode the search at least once.
- **In Ultimate the tool did not help: no wins and 92% losses, against 82% wins for the search
  alone.** The model analysed before 67% of its moves, followed the analysis 60% of the time when it
  did, and never followed it for a whole game. Half a move per game was a fallback, after six
  attempts without a legal move.
- **Phantom behaves differently.** The model alone already won 57%, close to the search's 48%,
  though it lost twice as often (42% against 20%). With the tool it followed 91% of the
  recommendations and ended close to the search: 45% wins and 27% losses. The split by
  "followed every move" means little here: games the opponent wins quickly leave few moves to
  deviate on (median 4 turns, against 13 in the other group).

The search tool helps a small model about as much as the model trusts it. In tic-tac-toe and
Phantom, where Llama 3.2 3B followed most recommendations, it came close to the search; in
Ultimate, the hardest of the three, it ignored them most often and gained nothing.

### The Ultimate tic-tac-toe rerun

The first run of Ultimate (14 October) used rules that rescanned the big board for a winner
several times per simulated move. They now keep the winner in the state: the game behaves exactly
as before, but a search of 1 second runs 2.5 to 3.2 times as many iterations, for the opponent
and for `analyze_position` alike. The rerun changed no conclusion, and every difference falls
inside the 95% intervals of both runs:

| Ultimate | 14 October (wins / draws / losses) | 15 October |
| --- | --- | --- |
| llm | 0 / 0 / 100% | 0 / 0 / 100% |
| llm+search | 8 / 2 / 90% | 0 / 8 / 92% |
| search | 90 / 5 / 5% | 82 / 8 / 10% |
| random | 0 / 0 / 100% | 0 / 0 / 100% |

## Run it

```bash
ollama pull llama3.2:3b
uv run --group bench python benchmarks/run.py                 # about 3 hours on a 4 GB laptop GPU
uv run --group bench python benchmarks/run.py --games tictactoe --per-game 2   # quick pilot
uv run python benchmarks/summary.py
```

`run.py` appends to `results.csv` and skips games already in it, so a stopped run resumes where it
left off. `--models`, `--games`, `--conditions`, `--per-game`, `--opponent-seconds` and
`--analysis-seconds` change the setup. The tests in `tests/test_benchmark.py` play every player
with fake models, so they run without Ollama.
