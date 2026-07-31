"""Generate the local UI debug views and an overview page linking them together.

This orchestrates the existing building and player board generators; it adds no new
rendering domain of its own. Everything it writes is a local debug artifact.

Run from the repo root:

    python3 tools/ui_debug/generate_debug_overview.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.generate_buildings import (  # noqa: E402
    OUTPUT_FILENAME as BUILDING_TILES_FILENAME,
)
from tools.ui_debug.generate_buildings import (  # noqa: E402
    generate_building_tiles_page,
)
from tools.ui_debug.generate_donated_buildings import (  # noqa: E402
    OUTPUT_FILENAME as DONATED_BUILDING_TILES_FILENAME,
)
from tools.ui_debug.generate_donated_buildings import (  # noqa: E402
    generate_donated_building_tiles_page,
)
from tools.ui_debug.generate_map import (  # noqa: E402
    OUTPUT_FILENAME as MAP_FILENAME,
)
from tools.ui_debug.generate_map import (  # noqa: E402
    generate_map_page,
)
from tools.ui_debug.generate_player_board import (  # noqa: E402
    OUTPUT_FILENAME as PLAYER_BOARD_FILENAME,
)
from tools.ui_debug.generate_player_board import (  # noqa: E402
    generate_player_board_page,
)
from tools.ui_debug.generate_ship_marker import (  # noqa: E402
    OUTPUT_FILENAME as SHIP_MARKER_FILENAME,
)
from tools.ui_debug.generate_ship_marker import (  # noqa: E402
    generate_ship_marker_page,
)

GENERATED_DIRNAME = "generated"
OVERVIEW_FILENAME = "debug_overview.html"
TITLE = "Pilgrim UI Debug — Generated Views"

NOTES = (
    "Generated map rendering is visual/debug only and is not connected to GameState yet.",
    "No GameState integration yet.",
    "No gameplay rules are implemented in the UI layer.",
)


@dataclass(frozen=True)
class GeneratedViews:
    map_page: Path
    building_tiles: Path
    player_board: Path
    donated_building_tiles: Path
    ship_marker: Path
    overview: Path

    def as_tuple(self) -> tuple[Path, ...]:
        return (
            self.map_page,
            self.building_tiles,
            self.player_board,
            self.donated_building_tiles,
            self.ship_marker,
            self.overview,
        )


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME


def render_debug_overview_html() -> str:
    notes = "\n".join(f"    <li>{note}</li>" for note in NOTES)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{TITLE}</title>
  <style>
    body {{
      margin: 0;
      background: #000;
      color: #F2EEDF;
      font-family: Helvetica, Arial, sans-serif;
      padding: 32px;
    }}
    h1 {{ font-family: Georgia, serif; }}
    a {{ color: #8FBEDB; font-size: 18px; }}
    li {{ margin: 12px 0; }}
    ul.notes li {{ color: #A8A296; font-size: 14px; margin: 6px 0; }}
  </style>
</head>
<body>
  <h1>{TITLE}</h1>
  <ul>
    <li><a href="{MAP_FILENAME}">Generated map</a></li>
    <li><a href="{BUILDING_TILES_FILENAME}">Generated building tiles</a></li>
    <li><a href="{PLAYER_BOARD_FILENAME}">Generated player board</a></li>
    <li><a href="{DONATED_BUILDING_TILES_FILENAME}">Generated donated building tiles</a></li>
    <li><a href="{SHIP_MARKER_FILENAME}">Generated ship marker</a></li>
    <li><a href="../index.html">Back to prototype index</a></li>
  </ul>
  <ul class="notes">
{notes}
  </ul>
</body>
</html>
"""


def generate_debug_views(*, output_dir: Path | None = None) -> GeneratedViews:
    destination_dir = default_output_dir() if output_dir is None else Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    map_page = generate_map_page(output_path=destination_dir / MAP_FILENAME)
    building_tiles = generate_building_tiles_page(
        output_path=destination_dir / BUILDING_TILES_FILENAME
    )
    player_board = generate_player_board_page(output_path=destination_dir / PLAYER_BOARD_FILENAME)
    donated_building_tiles = generate_donated_building_tiles_page(
        output_path=destination_dir / DONATED_BUILDING_TILES_FILENAME
    )
    ship_marker = generate_ship_marker_page(output_path=destination_dir / SHIP_MARKER_FILENAME)

    overview = destination_dir / OVERVIEW_FILENAME
    overview.write_text(render_debug_overview_html(), encoding="utf-8")

    return GeneratedViews(
        map_page=map_page,
        building_tiles=building_tiles,
        player_board=player_board,
        donated_building_tiles=donated_building_tiles,
        ship_marker=ship_marker,
        overview=overview,
    )


def main() -> None:
    for written in generate_debug_views().as_tuple():
        print(f"wrote {written}")


if __name__ == "__main__":
    main()
