from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QDialog,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QColor,
)
from aqt.utils import showInfo

ADDON_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_DIR, "config.json")
ADDON_VERSION = "0.1.0"

STATUS_LIMITS = "limits"
STATUS_AVAIL = "availability"
STATUS_NORMAL = "normal"

STATUS_PRIORITY = {
    STATUS_NORMAL: 0,
    STATUS_AVAIL: 1,
    STATUS_LIMITS: 2,
}

STATUS_LABELS = {
    STATUS_LIMITS: "0/day (limits)",
    STATUS_AVAIL: "0 available (unsuspended)",
    STATUS_NORMAL: "Has new cards",
}

STATUS_COLORS = {
    STATUS_LIMITS: QColor(192, 57, 43),
    STATUS_AVAIL: QColor(243, 156, 18),
    STATUS_NORMAL: QColor(39, 174, 96),
}

FILTERED_COLOR = QColor(52, 152, 219)


@dataclass
class DeckInfo:
    did: int
    name: str
    is_filtered: bool
    new_limit: Optional[int]
    limit_source: str
    unsuspended_new: int
    suspended_new: int
    self_status: str
    agg_status: str = STATUS_NORMAL
    agg_unsuspended_new: int = 0
    agg_suspended_new: int = 0


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "menu_title": "Find Empty New-Card Decks",
            "show_when_profile_opens": False,
            "show_all_decks": False,
        }

def _get_deck_config(did: int) -> dict:
    decks = mw.col.decks
    for attr in (
        "config_dict_for_deck_id",
        "config_dict_for_did",
        "deck_config_for_did",
        "config_for_did",
    ):
        fn = getattr(decks, attr, None)
        if callable(fn):
            try:
                return fn(did)
            except Exception:
                continue

    deck = decks.get(did)
    if deck:
        conf_id = deck.get("conf")
        if conf_id is not None:
            fn = getattr(decks, "get_config", None)
            if callable(fn):
                try:
                    return fn(conf_id)
                except Exception:
                    pass

    return {}

def _get_config_new_limit(did: int) -> Tuple[Optional[int], str]:
    config = _get_deck_config(did)
    per_day = config.get("new", {}).get("perDay")
    if per_day is None:
        return None, "unknown"
    try:
        return int(per_day), "config"
    except Exception:
        return None, "unknown"


def _count_new_cards(did: int, suspended: bool) -> int:
    suspended_clause = "is:suspended" if suspended else "-is:suspended"
    query = f"did:{did} is:new {suspended_clause}"
    try:
        return len(mw.col.find_cards(query))
    except Exception:
        return 0


def _compute_self_status(new_limit: Optional[int], unsuspended_new: int) -> str:
    if new_limit is not None and new_limit <= 0:
        return STATUS_LIMITS
    if unsuspended_new <= 0:
        return STATUS_AVAIL
    return STATUS_NORMAL


def _parent_name(deck_name: str) -> Optional[str]:
    if "::" not in deck_name:
        return None
    return deck_name.rsplit("::", 1)[0]


def _aggregate_status(
    deck_names: List[str], self_status: Dict[str, str]
) -> Dict[str, str]:
    agg = dict(self_status)
    for name in sorted(deck_names, key=lambda n: n.count("::"), reverse=True):
        parent = _parent_name(name)
        if not parent:
            continue
        if parent not in agg:
            agg[parent] = STATUS_NORMAL
        if STATUS_PRIORITY[agg[name]] > STATUS_PRIORITY[agg[parent]]:
            agg[parent] = agg[name]
    return agg


def _aggregate_counts(
    deck_names: List[str],
    unsuspended_by_name: Dict[str, int],
    suspended_by_name: Dict[str, int],
) -> Tuple[Dict[str, int], Dict[str, int]]:
    agg_unsuspended = dict(unsuspended_by_name)
    agg_suspended = dict(suspended_by_name)

    for name in sorted(deck_names, key=lambda n: n.count("::"), reverse=True):
        parent = _parent_name(name)
        if not parent:
            continue
        agg_unsuspended[parent] = agg_unsuspended.get(parent, 0) + agg_unsuspended.get(name, 0)
        agg_suspended[parent] = agg_suspended.get(parent, 0) + agg_suspended.get(name, 0)

    return agg_unsuspended, agg_suspended


def _build_deck_info() -> Tuple[Dict[str, DeckInfo], List[str]]:
    decks_manager = mw.col.decks
    deck_items = []
    all_names = getattr(decks_manager, "all_names_and_ids", None)
    if callable(all_names):
        try:
            deck_items = all_names()
        except Exception:
            deck_items = []
    if not deck_items:
        deck_items = decks_manager.all()
    if not deck_items:
        all_ids = getattr(decks_manager, "all_ids", None)
        if callable(all_ids):
            try:
                deck_items = all_ids()
            except Exception:
                deck_items = []
    info_by_name: Dict[str, DeckInfo] = {}
    deck_names: List[str] = []

    for deck in deck_items:
        did = None
        name = None
        if isinstance(deck, dict):
            did = deck.get("id")
            name = deck.get("name")
        elif isinstance(deck, (list, tuple)) and len(deck) >= 2:
            if isinstance(deck[0], int):
                did = deck[0]
                name = deck[1]
            else:
                name = deck[0]
                did = deck[1]
        else:
            did = getattr(deck, "id", None)
            name = getattr(deck, "name", None)
        if isinstance(deck, int) and did is None:
            did = deck
            name_fn = getattr(decks_manager, "name", None)
            if callable(name_fn):
                try:
                    name = name_fn(did)
                except Exception:
                    name = None
        if did is None or not name:
            continue
        deck_dict = decks_manager.get(did)
        is_filtered = bool(deck_dict.get("dyn", False)) if deck_dict else False
        new_limit, limit_source = _get_config_new_limit(did)
        unsuspended_new = _count_new_cards(did, suspended=False)
        suspended_new = _count_new_cards(did, suspended=True)
        self_status = _compute_self_status(new_limit, unsuspended_new)
        info_by_name[name] = DeckInfo(
            did=did,
            name=name,
            is_filtered=is_filtered,
            new_limit=new_limit,
            limit_source=limit_source,
            unsuspended_new=unsuspended_new,
            suspended_new=suspended_new,
            self_status=self_status,
        )
        deck_names.append(name)

    agg_status = _aggregate_status(deck_names, {n: i.self_status for n, i in info_by_name.items()})
    agg_unsuspended, agg_suspended = _aggregate_counts(
        deck_names,
        {n: i.unsuspended_new for n, i in info_by_name.items()},
        {n: i.suspended_new for n, i in info_by_name.items()},
    )
    for name, status in agg_status.items():
        if name in info_by_name:
            info_by_name[name].agg_unsuspended_new = agg_unsuspended.get(name, 0)
            info_by_name[name].agg_suspended_new = agg_suspended.get(name, 0)
            # Recompute aggregated status so it aligns with aggregated counts.
            if status == STATUS_LIMITS:
                info_by_name[name].agg_status = STATUS_LIMITS
            else:
                if info_by_name[name].agg_unsuspended_new <= 0:
                    info_by_name[name].agg_status = STATUS_AVAIL
                else:
                    info_by_name[name].agg_status = STATUS_NORMAL

    return info_by_name, deck_names


def _format_limit(limit: Optional[int], is_filtered: bool) -> str:
    if is_filtered:
        return "N/A"
    if limit is None:
        return "?"
    return str(limit)


def _show_report() -> None:
    if not mw or not mw.col:
        return

    config = _load_config()
    show_all = bool(config.get("show_all_decks", False))

    info_by_name, deck_names = _build_deck_info()
    if not info_by_name:
        showInfo("No decks found.")
        return

    counts = {
        STATUS_LIMITS: 0,
        STATUS_AVAIL: 0,
        STATUS_NORMAL: 0,
    }
    for info in info_by_name.values():
        counts[info.agg_status] += 1

    included_names = [
        name
        for name in deck_names
        if show_all or info_by_name[name].agg_status != STATUS_NORMAL
    ]
    if not included_names:
        showInfo("No empty new-card decks found.")
        return

    dialog = QDialog(mw)
    dialog.setWindowTitle(f"Empty New-Card Decks (v{ADDON_VERSION})")

    layout = QVBoxLayout(dialog)
    summary = (
        f"Decks: {len(deck_names)}  |  "
        f"Limits: {counts[STATUS_LIMITS]}  |  "
        f"Availability: {counts[STATUS_AVAIL]}"
    )
    layout.addWidget(QLabel(summary))
    if not show_all:
        layout.addWidget(QLabel("Showing only empty decks (set show_all_decks=true for all)."))

    tree = QTreeWidget()
    tree.setHeaderLabels(["Deck", "Status", "New/day", "Unsuspended new", "Suspended new"])
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    item_by_name: Dict[str, QTreeWidgetItem] = {}
    for name in sorted(included_names, key=lambda n: n.count("::")):
        info = info_by_name[name]
        parent_name = _parent_name(name)
        status_label = STATUS_LABELS[info.agg_status]
        limit_label = _format_limit(info.new_limit, info.is_filtered)
        unsuspended_label = str(info.agg_unsuspended_new)
        suspended_label = str(info.agg_suspended_new)

        row = [name, status_label, limit_label, unsuspended_label, suspended_label]
        item = QTreeWidgetItem(row)
        color = FILTERED_COLOR if info.is_filtered else STATUS_COLORS[info.agg_status]
        item.setForeground(1, color)

        if parent_name and parent_name in item_by_name:
            item_by_name[parent_name].addChild(item)
        else:
            tree.addTopLevelItem(item)

        item_by_name[name] = item

    tree.expandAll()
    layout.addWidget(tree)

    dialog.resize(760, 520)
    dialog.exec()


def _add_menu_action() -> None:
    config = _load_config()
    title = config.get("menu_title", "Find Empty New-Card Decks")

    action = QAction(title, mw)
    action.triggered.connect(_show_report)
    mw.form.menuTools.addAction(action)


# Add menu action once the profile is ready.

def _on_profile_open() -> None:
    _add_menu_action()
    if _load_config().get("show_when_profile_opens", False):
        _show_report()


gui_hooks.profile_did_open.append(_on_profile_open)
