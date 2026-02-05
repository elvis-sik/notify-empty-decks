from __future__ import annotations

import json
import os
from typing import List

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import showInfo

ADDON_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_DIR, "config.json")


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "menu_title": "Find Empty New-Card Decks",
            "show_when_profile_opens": False,
        }


def find_decks_with_no_new_cards() -> List[str]:
    """Return deck names that currently have zero new cards.

    TODO: Implement using Anki's deck/scheduler APIs.
    """
    # Placeholder to keep the UI wired up while core logic is developed.
    return []


def _show_empty_decks() -> None:
    if not mw or not mw.col:
        return

    empty_decks = find_decks_with_no_new_cards()
    if not empty_decks:
        showInfo("No empty new-card decks found (or not implemented yet).")
        return

    message = "Decks with zero new cards:\n\n" + "\n".join(empty_decks)
    showInfo(message)


def _add_menu_action() -> None:
    config = _load_config()
    title = config.get("menu_title", "Find Empty New-Card Decks")

    action = QAction(title, mw)
    action.triggered.connect(_show_empty_decks)
    mw.form.menuTools.addAction(action)


# Add menu action once the profile is ready.

def _on_profile_open() -> None:
    _add_menu_action()


gui_hooks.profile_did_open.append(_on_profile_open)
