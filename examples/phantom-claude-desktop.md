# Claude plays Phantom from Claude Desktop

A real game, played on 14 October 2026 by Claude in Claude Desktop with this server installed
through `uvx`. The conversation is in Spanish, the language of the account. The request was:

> Juega una partida de Phantom contra el rival MO-ISMCTS. Lee primero las reglas, analiza cada
> posición antes de mover y explica cada jugada en una frase usando los datos del análisis.

*(Play a game of Phantom against the MO-ISMCTS opponent. Read the rules first, analyse each
position before you move and explain each move in one sentence using the analysis.)*

Claude moved first, called `analyze_position` before each move and played the move it ranked best
every time. It won in four moves. One game shows how the tools are used, not how strong the
player is: for that, see the [benchmark](../benchmarks/).

![Claude Desktop calling play_move and analyze_position during the game](phantom-claude-desktop.png)

## Claude's replies

**Jugada 1 — a4:** la mejor según MO-ISMCTS, con 784 visitas y un 57,2 % de victorias simuladas. Las demás candidatas (d4, c3) se quedan entre el 54 % y el 55 %.

**Jugada 2 — c2:** es la que más se ha explorado (751 visitas, 58,3 %) y está en la antidiagonal a4–b3–c2–d1, que ya empecé con a4.

**Jugada 3 — b3:** destaca con claridad (1423 visitas, 61,3 %) porque pone tres en la antidiagonal y solo me faltaría d1.

**Jugada 4 — d1:** se lleva casi todo el árbol (13 678 de 14 472 iteraciones, 87,9 %), porque si la casilla está libre completo la antidiagonal y gano.

He ganado la partida en 4 jugadas, completando la antidiagonal a4–b3–c2–d1. Antes de cada jugada analicé la posición con MO-ISMCTS durante 3 segundos.

| # | Jugada | Victorias simuladas | Por qué |
|---|---|---|---|
| 1 | a4 | 57,2 % (784 visitas) | La mejor desde el tablero vacío; d4 y c3 se quedaban entre el 54 % y el 55 %. |
| 2 | c2 | 58,3 % (751 visitas) | Seguía la diagonal de a4; b2 era la siguiente, con un 57,0 %. |
| 3 | b3 | 61,3 % (1423 visitas) | Ponía la tercera ficha en la diagonal, así que solo faltaba d1. |
| 4 | d1 | 87,9 % (13 678 de 14 472 iteraciones) | La casilla estaba libre y cerró las cuatro en línea. |

**Tablero final** (1 = yo, 2 = rival):

```
  a b c d
1 2 . . 1
2 . 2 1 .
3 . 1 . .
4 1 . . 2
```

El rival iba montando la otra diagonal (a1, b2, d4) y solo le faltaba c3. No llegó a bloquearme: sin ver mis fichas, sus tres piedras fueron a casillas que no me cortaban.
