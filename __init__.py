from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    Qt,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QColor,
)
from aqt.utils import showInfo

ADDON_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_DIR, "config.json")
ADDON_VERSION = "0.1.0"
_report_dialog: Optional[QDialog] = None
_report_tree: Optional[QTreeWidget] = None


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout:
            _clear_layout(child_layout)
            continue
        widget = item.widget()
        if widget:
            widget.setParent(None)

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
CONTAINER_COLOR = QColor(0, 0, 0)
EMPTY_COLOR = QColor(127, 140, 141)


@dataclass
class DeckInfo:
    did: int
    name: str
    is_filtered: bool
    is_container: bool
    is_empty: bool
    total_cards: int
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
            "notify_every_n_days": 0,
            "notify_never": True,
            "last_opened_at": 0,
            "name_filter": "",
            "filter_filtered_decks": True,
            "filter_container_decks": True,
            "filter_empty_decks": True,
            "filter_limits_zero": True,
            "filter_available_zero": True,
            "filter_has_new": True,
        }


def _save_config(config: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, sort_keys=False)
    except Exception:
        pass


def _is_problematic(info: DeckInfo) -> bool:
    return info.agg_status in (STATUS_LIMITS, STATUS_AVAIL)


def _include_deck(name: str, info: DeckInfo, config: dict) -> bool:
    name_filter = str(config.get("name_filter", "")).strip().lower()
    if name_filter and name_filter not in name.lower():
        return False

    if info.is_filtered and not config.get("filter_filtered_decks", True):
        return False
    if info.is_container and not config.get("filter_container_decks", True):
        return False
    if info.is_empty and not config.get("filter_empty_decks", True):
        return False

    include_limits = config.get("filter_limits_zero", True)
    include_avail = config.get("filter_available_zero", True)
    include_has_new = config.get("filter_has_new", True)

    if info.agg_status == STATUS_LIMITS:
        return bool(include_limits)
    if info.agg_status == STATUS_AVAIL:
        return bool(include_avail)
    return bool(include_has_new)

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
    deck = mw.col.decks.get(did) or {}
    # Per-deck overrides (This deck) should win over preset values.
    for key in ("new_per_day", "newPerDay", "newLimit", "new_limit"):
        if key in deck:
            try:
                return int(deck[key]), "deck"
            except Exception:
                pass
    limits = deck.get("limits")
    if isinstance(limits, dict):
        for key in ("new", "perDay", "new_per_day"):
            if key in limits:
                try:
                    return int(limits[key]), "deck"
                except Exception:
                    pass

    config = _get_deck_config(did)
    per_day = config.get("new", {}).get("perDay")
    if per_day is None:
        return None, "unknown"
    try:
        return int(per_day), "config"
    except Exception:
        return None, "unknown"

def _count_new_cards(did: int, suspended: bool) -> int:
    queue = -1 if suspended else 0
    try:
        count = mw.col.db.scalar(
            "select count() from cards where did=? and type=0 and queue=?",
            did,
            queue,
        )
        return int(count or 0)
    except Exception:
        return 0


def _count_total_cards(did: int) -> int:
    try:
        count = mw.col.db.scalar(
            "select count() from cards where did=?",
            did,
        )
        return int(count or 0)
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


def _ancestor_names(deck_name: str, known_names: Dict[str, DeckInfo]) -> List[str]:
    ancestors: List[str] = []
    parent = _parent_name(deck_name)
    while parent:
        if parent in known_names:
            ancestors.append(parent)
        parent = _parent_name(parent)
    return ancestors


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
        total_cards = _count_total_cards(did)
        is_container = total_cards == 0
        is_empty = False
        new_limit, limit_source = _get_config_new_limit(did)
        unsuspended_new = _count_new_cards(did, suspended=False)
        suspended_new = _count_new_cards(did, suspended=True)
        self_status = _compute_self_status(new_limit, unsuspended_new)
        info_by_name[name] = DeckInfo(
            did=did,
            name=name,
            is_filtered=is_filtered,
            is_container=is_container,
            is_empty=is_empty,
            total_cards=total_cards,
            new_limit=new_limit,
            limit_source=limit_source,
            unsuspended_new=unsuspended_new,
            suspended_new=suspended_new,
            self_status=self_status,
        )
        deck_names.append(name)

    agg_status = _aggregate_status(deck_names, {n: i.self_status for n, i in info_by_name.items()})
    # Mark container decks only if they have children.
    parents = set()
    for name in deck_names:
        parent = _parent_name(name)
        while parent:
            parents.add(parent)
            parent = _parent_name(parent)
    for name, info in info_by_name.items():
        if info.total_cards == 0 and name in parents:
            info.is_container = True
            info.is_empty = False
        elif info.total_cards == 0 and name not in parents:
            info.is_container = False
            info.is_empty = True
        else:
            info.is_container = False
            info.is_empty = False
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


def _populate_report(dialog: QDialog) -> None:
    global _report_tree
    if not mw or not mw.col:
        return

    config = _load_config()

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
        name for name in deck_names if _include_deck(name, info_by_name[name], config)
    ]
    matched_names = set(included_names)

    visible_names = set(matched_names)
    for name in matched_names:
        for ancestor in _ancestor_names(name, info_by_name):
            visible_names.add(ancestor)

    no_matches = not matched_names

    dialog.setWindowTitle(f"Empty New-Card Decks (v{ADDON_VERSION})")
    if dialog.layout() is None:
        dialog.setLayout(QVBoxLayout())
    layout = dialog.layout()
    _clear_layout(layout)

    summary = (
        f"Decks: {len(deck_names)}  |  "
        f"Limits: {counts[STATUS_LIMITS]}  |  "
        f"Availability: {counts[STATUS_AVAIL]}"
    )
    layout.addWidget(QLabel(summary))
    if no_matches:
        layout.addWidget(QLabel("No decks match the current filters."))

    options_grid = QGridLayout()

    filter_box = QLineEdit()
    filter_box.setPlaceholderText("Filter by name")
    filter_box.setText(config.get("name_filter", ""))
    filter_box.textChanged.connect(lambda text: _update_option("name_filter", text, dialog))
    filter_box.setToolTip("Filter decks by name substring. Parent context remains visible.")

    notify_spin = QSpinBox()
    notify_spin.setMinimum(0)
    notify_spin.setMaximum(365)
    notify_spin.setValue(int(config.get("notify_every_n_days", 0) or 0))
    notify_spin.setSuffix(" days")
    notify_spin.valueChanged.connect(
        lambda value: _update_option("notify_every_n_days", int(value), dialog, refresh=False)
    )
    notify_spin.setToolTip("0 = open every time. Use with Never notify to disable.")

    options_grid.addWidget(QLabel("Filter by name"), 0, 0)
    options_grid.addWidget(filter_box, 0, 1)
    options_grid.addWidget(QLabel("Open automatically if last opened >="), 1, 0)
    notify_never = QCheckBox("Never notify")
    notify_never.setChecked(bool(config.get("notify_never", True)))
    notify_never.stateChanged.connect(
        lambda state: _update_option("notify_never", bool(state), dialog)
    )
    notify_never.setToolTip("Disable automatic opening on profile load.")
    notify_row = QGridLayout()
    notify_row.addWidget(notify_spin, 0, 0)
    notify_row.addWidget(notify_never, 0, 1)
    options_grid.addLayout(notify_row, 1, 1)

    cb_filtered = QCheckBox("Filtered decks")
    cb_filtered.setChecked(bool(config.get("filter_filtered_decks", True)))
    cb_filtered.stateChanged.connect(
        lambda state: _update_option("filter_filtered_decks", bool(state), dialog)
    )
    cb_filtered.setToolTip("Show filtered (dynamic) decks.")
    cb_container = QCheckBox("Container decks")
    cb_container.setChecked(bool(config.get("filter_container_decks", True)))
    cb_container.stateChanged.connect(
        lambda state: _update_option("filter_container_decks", bool(state), dialog)
    )
    cb_container.setToolTip(
        "Container decks have no cards directly in the deck, but do have child decks."
    )

    cb_empty = QCheckBox("Empty decks")
    cb_empty.setChecked(bool(config.get("filter_empty_decks", True)))
    cb_empty.stateChanged.connect(
        lambda state: _update_option("filter_empty_decks", bool(state), dialog)
    )
    cb_empty.setToolTip(
        "Empty decks have no cards and no child decks."
    )
    cb_limits = QCheckBox("0/day limits")
    cb_limits.setChecked(bool(config.get("filter_limits_zero", True)))
    cb_limits.stateChanged.connect(
        lambda state: _update_option("filter_limits_zero", bool(state), dialog)
    )
    cb_limits.setToolTip("Decks whose effective new/day limit is 0.")
    cb_avail = QCheckBox("0 available (unsuspended)")
    cb_avail.setChecked(bool(config.get("filter_available_zero", True)))
    cb_avail.stateChanged.connect(
        lambda state: _update_option("filter_available_zero", bool(state), dialog)
    )
    cb_avail.setToolTip("Decks with 0 unsuspended new cards.")
    cb_has_new = QCheckBox("Has new cards")
    cb_has_new.setChecked(bool(config.get("filter_has_new", True)))
    cb_has_new.stateChanged.connect(
        lambda state: _update_option("filter_has_new", bool(state), dialog)
    )
    cb_has_new.setToolTip("Decks with available unsuspended new cards.")

    layout.addLayout(options_grid)

    filters_grid = QGridLayout()
    filters_grid.addWidget(cb_filtered, 0, 0)
    filters_grid.addWidget(cb_container, 0, 1)
    filters_grid.addWidget(cb_empty, 0, 2)
    filters_grid.addWidget(cb_limits, 1, 0)
    filters_grid.addWidget(cb_avail, 1, 1)
    filters_grid.addWidget(cb_has_new, 1, 2)
    for col in range(3):
        filters_grid.setColumnStretch(col, 1)
    layout.addLayout(filters_grid)

    refresh_button = QPushButton("Refresh")
    refresh_button.clicked.connect(lambda: _populate_report(dialog))
    refresh_button.setToolTip("Recompute counts and refresh the list.")
    layout.addWidget(refresh_button)

    if _report_tree is None:
        _report_tree = QTreeWidget()
        _report_tree.setHeaderLabels(
            ["Deck", "Status", "New/day", "Unsuspended new", "Suspended new"]
        )
        _report_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        _report_tree.setSortingEnabled(True)
        _report_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    tree = _report_tree
    tree.clear()
    tree.setToolTip("Deck status list. Hover items for details.")

    item_by_name: Dict[str, QTreeWidgetItem] = {}
    for name in sorted(visible_names, key=lambda n: (n.count("::"), n)):
        info = info_by_name[name]
        parent_name = _parent_name(name)
        is_active = name in matched_names
        status_label = STATUS_LABELS[info.agg_status]
        limit_label = _format_limit(info.new_limit, info.is_filtered)
        unsuspended_label = str(info.agg_unsuspended_new)
        suspended_label = str(info.agg_suspended_new)

        row = [name, status_label, limit_label, unsuspended_label, suspended_label]
        item = QTreeWidgetItem(row)
        if info.is_container:
            color = CONTAINER_COLOR
            status_tooltip = "Container deck: no cards directly in this deck, but has child decks."
        elif info.is_empty:
            color = EMPTY_COLOR
            status_tooltip = "Empty deck: no cards and no child decks."
        elif info.is_filtered:
            color = FILTERED_COLOR
            status_tooltip = "Filtered (dynamic) deck."
        else:
            color = STATUS_COLORS[info.agg_status]
            status_tooltip = STATUS_LABELS[info.agg_status]
        item.setForeground(1, color)
        item.setToolTip(0, f"{name}")
        item.setToolTip(1, status_tooltip)
        item.setToolTip(2, f"New/day limit source: {info.limit_source}")
        item.setToolTip(
            3, f"Unsuspended new cards (including children): {info.agg_unsuspended_new}"
        )
        item.setToolTip(
            4, f"Suspended new cards (including children): {info.agg_suspended_new}"
        )
        if not is_active:
            muted = QColor(149, 165, 166)
            for col in range(5):
                item.setForeground(col, muted)
            item.setToolTip(0, f"{name}\nShown for hierarchy context.")

        if parent_name and parent_name in item_by_name:
            item_by_name[parent_name].addChild(item)
        else:
            tree.addTopLevelItem(item)

        item_by_name[name] = item

    tree.expandAll()
    layout.addWidget(tree)


def _show_report() -> None:
    global _report_dialog
    if not mw:
        return
    if _report_dialog is None:
        _report_dialog = QDialog(mw)
        _report_dialog.setModal(False)
    if _report_dialog.layout() is None:
        _report_dialog.setLayout(QVBoxLayout())
    _populate_report(_report_dialog)
    _report_dialog.resize(760, 520)
    _report_dialog.show()
    _report_dialog.raise_()
    _touch_last_opened()


def _touch_last_opened() -> None:
    config = _load_config()
    config["last_opened_at"] = int(time.time())
    _save_config(config)


def _update_option(key: str, value, dialog: QDialog, refresh: bool = True) -> None:
    config = _load_config()
    config[key] = value
    _save_config(config)
    if refresh:
        _populate_report(dialog)


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

    config = _load_config()
    days = int(config.get("notify_every_n_days", 0) or 0)
    notify_never = bool(config.get("notify_never", True))
    last_opened = int(config.get("last_opened_at", 0) or 0)
    if notify_never:
        return
    if days == 0:
        _show_report()
        return
    if last_opened > 0:
        delta_days = (time.time() - last_opened) / 86400
        if delta_days >= days:
            _show_report()


gui_hooks.profile_did_open.append(_on_profile_open)
