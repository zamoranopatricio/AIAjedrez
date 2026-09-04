# AIAjedrez

Entorno local completo para jugar ajedrez contra la computadora o en modo Humano vs Humano, con análisis de IA integrado mediante Stockfish. Funciona **100% sin internet** — sin APIs externas, sin servicios en la nube.

---

## Características

- **Dos modos de juego** — Humano vs IA o Humano vs Humano, seleccionables desde el menú
- **Selector de color y dificultad** — Elige jugar con Blancas o Negras, y el nivel de la IA (Principiante → Gran Maestro)
- **Soporte Multiplataforma** — Compatible de forma nativa con **Linux** y **Windows (10/11)**
- **Interfaz gráfica con Pygame** — Tablero 8×8 con piezas del set *cburnett*, drag & drop y clic para mover
- **Validación completa de reglas** — Movimientos legales, jaque, jaque mate, tablas, enroque, en passant y promoción mediante `python-chess`
- **Barra de evaluación en tiempo real** — Análisis continuo de Stockfish en hilo secundario con indicador visual y valor numérico
- **Flecha de sugerencia estilizada** — Visualiza la mejor jugada del motor con vectorización limpia
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
| Stockfish | Cualquier versión reciente (`stockfish` en Linux, `stockfish.exe` en Windows) |
| Sistema operativo | Linux (Ubuntu, Fedora, Arch, etc.) / Windows 10/11 |

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
pyinstaller >= 6.0.0
```

---

## Obtener Stockfish

### Linux
```bash
# Ubuntu / Debian
sudo apt install stockfish

# Fedora / RHEL
sudo dnf install stockfish

# Arch Linux
sudo pacman -S stockfish
```

### Windows
1. Descarga el ejecutable desde la web oficial de [Stockfish Download](https://stockfishchess.org/download/).
2. Descomprime y coloca `stockfish.exe` dentro de la carpeta `bin/` del proyecto.
3. *Alternativa:* Agrega `stockfish.exe` a tus Variables de Entorno del Sistema (PATH).

---

## Instalación y Ejecución

### En Linux / macOS

```bash
# 1. Clona el repositorio
git clone https://github.com/zamoranopatricio/AIAjedrez.git
cd AIAjedrez

# 2. (Opcional) Crea y activa un entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Ejecuta el juego
python3 main.py
```

### En Windows

#### Opción A: Ejecución Directa (Doble Clic)
Simplemente haz **doble clic en `ejecutar_windows.bat`**. El script verificará tu instalación de Python, instalará las dependencias necesarias y lanzará el juego de forma automática.

#### Opción B: Desde Consola PowerShell / CMD
```cmd
# 1. Instala las dependencias
pip install -r requirements.txt

# 2. Ejecuta el juego
python main.py
```

#### Opción C: Compilar un ejecutable ejecutable (.exe) autónomo
Para generar un paquete ejecutable ejecutable autónomo en la carpeta `dist/`:
```cmd
python build_windows.py
```

---

## Estructura del proyecto

```
AIAjedrez/
├── main.py                  # Punto de entrada y game loop principal
├── config.py                # Constantes de layout, colores y configuración global
├── requirements.txt         # Lista de dependencias del proyecto
├── build_windows.py         # Script de empaquetado PyInstaller para Windows (.exe)
├── ejecutar_windows.bat     # Lanzador de un solo clic para Windows
├── bin/                     # Directorio para binarios ejecutables de Stockfish
├── assets/                  # Imágenes de piezas (descargadas automáticamente)
├── saves/                   # Partidas guardadas en formato PGN
└── src/
    ├── menu.py              # Pantalla de menú principal
    ├── board_gui.py         # Renderizado del tablero y panel lateral
    ├── game_state.py        # Estado del juego, lógica de turnos y snapshots
    ├── engine_wrapper.py    # Hilo de Stockfish para análisis asíncrono
    ├── analysis_screen.py   # Pantalla de análisis post-partida
    ├── platform_utils.py    # Abstracción multiplataforma (Rutas, SO, Stockfish)
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
| `I` | Alternar visibilidad del Indicador de IA |
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

Al presionar **Análisis** (tecla `A` o botón), Stockfish evalúa cada jugada de la partida y asigna un rating:

| Rating | Etiqueta | Pérdida (cp) | Descripción |
|---|---|---|---|
| **[5]** | Excelente | 0 – 20 | Jugada óptima o casi óptima |
| **[4]** | Bueno | 21 – 50 | Buena decisión, error mínimo |
| **[3]** | Imprecisión | 51 – 100 | Jugable pero no la mejor opción |
| **[2]** | Error | 101 – 200 | Cede ventaja significativa |
| **[1]** | Error grave | > 200 | Cambia el balance de la partida |

Las flechas sobre el tablero muestran:
- **Azul** — Jugada realizada
- **Naranja** — Mejor jugada según el motor

---

## Licencia

Proyecto personal de uso libre. Las piezas gráficas pertenecen al set [cburnett](https://github.com/nicvagn/html-chessclock) bajo licencia CC BY-SA 3.0.
