# AIAjedrez

Entorno local completo para jugar ajedrez contra la computadora o en modo Humano vs Humano, con análisis de IA integrado mediante Stockfish. Funciona **100% sin internet** — sin APIs externas, sin servicios en la nube.

---

## Características

- **Dos modos de juego** — Humano vs IA o Humano vs Humano, seleccionables desde el menú
- **Selector de color y dificultad** — Elige jugar con Blancas o Negras, y el nivel de la IA (Principiante → Gran Maestro)
- **Interfaz gráfica con Pygame** — Tablero 8×8 con piezas del set *cburnett*, drag & drop y clic para mover
- **Validación completa de reglas** — Movimientos legales, jaque, jaque mate, tablas, enroque, en passant y promoción mediante `python-chess`
- **Barra de evaluación en tiempo real** — Análisis continuo de Stockfish en hilo secundario con indicador visual y valor numérico
- **Flecha de sugerencia** — Visualiza la mejor jugada del motor mientras juegas
- **Voltear tablero** — Rota la perspectiva del tablero en cualquier momento (`F` o botón)
- **Deshacer movimiento** — Retrocede una jugada completa (en H vs IA deshace el par humano + IA) con `Z` o botón
- **Guardar partida** — Exporta la partida en formato PGN a la carpeta `saves/`
- **Análisis post-partida** — Pantalla dedicada con evaluación jugada por jugada, rating 1–5, justificación contextual y flechas de mejor alternativa
- **Botones clickeables en el panel** — Toda la interfaz es navegable con el ratón; los atajos de teclado siguen disponibles en paralelo

---

## Requisitos

### Sistema

| Componente | Versión mínima |
|---|---|
| Python | 3.10+ |
| Stockfish | Cualquier versión reciente |
| Sistema operativo | Linux (probado en Ubuntu/Fedora) |

### Dependencias Python

```bash
pip install -r requirements.txt
```

```
pygame >= 2.5.2
python-chess >= 1.999
python-dotenv >= 1.0.0
requests >= 2.31.0
cairosvg >= 2.7.0
```

### Instalar Stockfish (si no lo tienes)

```bash
# Debian / Ubuntu / Fedora (con apt)
sudo apt install stockfish

# Fedora / RHEL
sudo dnf install stockfish

# O descarga el binario desde https://stockfishchess.org/download/
```

---

## Instalación

```bash
# Clona o descarga el repositorio
git clone <url-del-repo> AIAjedrez
cd AIAjedrez

# (Opcional) Crea un entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instala dependencias
pip install -r requirements.txt

# Ejecuta
python3 main.py
```

Las piezas gráficas (set *cburnett*) se descargan automáticamente la primera vez que se inicia el juego. Requiere conexión a internet **solo en esa primera ejecución**.

---

## Estructura del proyecto

```
AIAjedrez/
├── main.py                  # Punto de entrada y game loop principal
├── config.py                # Constantes de layout, colores y configuración
├── requirements.txt
├── .env.example             # Ejemplo de variables de entorno (ruta Stockfish, etc.)
├── assets/                  # Imágenes de piezas (descargadas automáticamente)
├── saves/                   # Partidas guardadas en formato PGN
└── src/
    ├── menu.py              # Pantalla de menú principal
    ├── board_gui.py         # Renderizado del tablero y panel lateral
    ├── game_state.py        # Estado del juego, lógica de turnos y snapshots
    ├── engine_wrapper.py    # Hilo de Stockfish para análisis asíncrono
    ├── analysis_screen.py   # Pantalla de análisis post-partida
    ├── asset_loader.py      # Descarga y carga de piezas cburnett
    └── font_manager.py      # Detección automática de fuentes del sistema
```

---

## Controles

### Ratón
Toda la interfaz es 100% clickeable. Los botones del panel lateral y los overlays responden al ratón con efecto hover.

### Teclado

| Tecla | Acción |
|---|---|
| `Clic` / `Arrastre` | Mover pieza |
| `Z` | Deshacer último movimiento |
| `F` | Voltear tablero |
| `S` | Guardar partida (PGN) |
| `A` | Abrir análisis post-partida |
| `R` | Reiniciar partida |
| `M` / `Esc` | Volver al menú |
| `Q` | Salir |

### En la pantalla de análisis

| Tecla / Botón | Acción |
|---|---|
| `←` / `→` | Jugada anterior / siguiente |
| `<<` `>>` | Primera / última jugada |
| Clic en lista | Ir directamente a esa jugada |
| `Esc` / `M` | Volver al juego |

---

## Sistema de análisis

Al presionar **Analisis** (tecla `A` o botón), Stockfish evalúa cada jugada de la partida y asigna un rating:

| Rating | Etiqueta | Pérdida (cp) | Descripción |
|---|---|---|---|
| **[5]** | Excelente | 0 – 20 | Jugada óptima o casi óptima |
| **[4]** | Bueno | 21 – 50 | Buena decisión, error mínimo |
| **[3]** | Imprecisión | 51 – 100 | Jugable pero no la mejor opción |
| **[2]** | Error | 101 – 200 | Cede ventaja significativa |
| **[1]** | Error grave | > 200 | Cambia el balance de la partida |

La justificación es **contextual y variada**: tiene en cuenta el tipo de pieza, si es captura, jaque o enroque, la fase de la partida (apertura / mediojuego / final) y el bando que mueve.

Las flechas sobre el tablero muestran:
- **Azul** — Jugada realizada
- **Naranja** — Mejor jugada según el motor

---

## Configuración avanzada

Copia `.env.example` a `.env` para personalizar rutas:

```bash
cp .env.example .env
```

Variables disponibles:

```env
STOCKFISH_PATH=/usr/games/stockfish   # Ruta al binario de Stockfish
STOCKFISH_SKILL=10                    # Nivel base (0-20)
```

Los niveles de dificultad del menú sobreescriben `STOCKFISH_SKILL` en tiempo de ejecución.

---

## Notas técnicas

- El análisis de Stockfish durante la partida corre en un **hilo separado** para no bloquear la interfaz.
- El análisis post-partida es **sincrónico por diseño**: analiza todas las jugadas de una vez al abrir la pantalla.
- Los snapshots del tablero se guardan en memoria durante la partida para permitir el deshacer y el análisis sin releer el historial.
- Las fuentes se detectan automáticamente del sistema (Ubuntu Sans → Cantarell → DejaVu Sans → fallback de pygame).

---

## Licencia

Proyecto personal de uso libre. Las piezas gráficas pertenecen al set [cburnett](https://github.com/nicvagn/html-chessclock) bajo licencia CC BY-SA 3.0.
