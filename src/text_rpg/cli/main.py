"""Typer CLI application."""
from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(
    name="text-rpg",
    help="A D&D-like high fantasy text RPG powered by LLMs",
    no_args_is_help=False,
)


@app.command()
def play(
    save_name: Optional[str] = typer.Option(None, "--save", "-s", help="Load a saved game"),
    new: bool = typer.Option(False, "--new", "-n", help="Start a new game"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
) -> None:
    """Start or continue your adventure."""
    from text_rpg.app import GameApp

    game_app = GameApp(model_override=model)
    if new:
        game_app.new_game()
    elif save_name:
        game_app.load_game(save_name)
    else:
        game_app.main_menu()


@app.command()
def saves() -> None:
    """List all saved games."""
    from text_rpg.app import GameApp

    game_app = GameApp()
    game_app.list_saves()


@app.command()
def check() -> None:
    """Check system requirements (Ollama, models, etc)."""
    from text_rpg.cli.display import Display

    display = Display()
    display.show_system_check()


if __name__ == "__main__":
    app()
