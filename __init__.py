from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass
from html import escape
from typing import Dict, List, Optional, Tuple

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)
from aqt.utils import showInfo

ADDON_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_DIR, "config.json")
ADDON_VERSION = "0.3.0"

STATUS_LIMITS = "limits"
STATUS_AVAIL = "availability"
STATUS_NORMAL = "normal"

CONTAINER_MODE_AGGREGATE = "aggregate_children"
CONTAINER_MODE_HIDE = "hide_container_rows"
CONTAINER_MODE_DIRECT = "direct_decks_only"

CONTAINER_MODE_CHOICES = [
    (CONTAINER_MODE_AGGREGATE, "Summarize children"),
    (CONTAINER_MODE_HIDE, "Hide container icons"),
    (CONTAINER_MODE_DIRECT, "Direct decks only"),
]

BADGE_STYLE = """
<style>
.notify-empty-decks-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15em;
  height: 1.15em;
  margin-left: 0.45em;
  border-radius: 999px;
  color: #fff;
  font-size: 0.72em;
  font-weight: 700;
  line-height: 1;
  vertical-align: middle;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  cursor: help;
}

.notify-empty-decks-badge-limits {
  background: #c0392b;
}

.notify-empty-decks-badge-availability {
  background: #f39c12;
}
</style>
"""

DECK_LINK_RE = re.compile(
    r'(<a class="deck [^"]*"\s*href=# onclick="return pycmd\(\'open:(\d+)\'\)">.*?</a>)',
    re.DOTALL,
)

DEFAULT_CONFIG = {
    "use_regex_patterns": False,
    "include_patterns": [],
    "exclude_patterns": [],
    "container_deck_mode": CONTAINER_MODE_AGGREGATE,
}

_menu_action: Optional[QAction] = None
_settings_dialog: Optional[QDialog] = None


@dataclass
class DeckInfo:
    did: int
    name: str
    is_filtered: bool
    total_cards: int
    new_limit: Optional[int]
    limit_source: str
    unsuspended_new: int
    suspended_new: int
    self_status: str
    is_container: bool = False
    monitored: bool = False
    agg_status: Optional[str] = None
    agg_unsuspended_new: int = 0
    agg_suspended_new: int = 0
    agg_has_monitored: bool = False


def _load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)
    except Exception:
        pass

    config["use_regex_patterns"] = bool(config.get("use_regex_patterns", False))
    config["include_patterns"] = _normalize_pattern_list(config.get("include_patterns", []))
    config["exclude_patterns"] = _normalize_pattern_list(config.get("exclude_patterns", []))
    container_mode = str(config.get("container_deck_mode", CONTAINER_MODE_AGGREGATE))
    if container_mode not in {choice[0] for choice in CONTAINER_MODE_CHOICES}:
        container_mode = CONTAINER_MODE_AGGREGATE
    config["container_deck_mode"] = container_mode
    return config


def _save_config(config: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, sort_keys=False)
    except Exception:
        pass


def _normalize_pattern_list(value: object) -> List[str]:
    if isinstance(value, str):
        items = value.splitlines()
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        return []

    patterns: List[str] = []
    for item in items:
        pattern = item.strip()
        if pattern and not pattern.startswith("#"):
            patterns.append(pattern)
    return patterns


def _validate_patterns(patterns: List[str], use_regex: bool, label: str) -> Optional[str]:
    if not use_regex:
        return None
    for pattern in patterns:
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as err:
            return f"Invalid {label} regex `{pattern}`: {err}"
    return None


def _matches_any_pattern(name: str, patterns: List[str], use_regex: bool) -> bool:
    if not patterns:
        return False

    if use_regex:
        for pattern in patterns:
            try:
                if re.search(pattern, name, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    lowered_name = name.lower()
    for pattern in patterns:
        if fnmatch.fnmatchcase(lowered_name, pattern.lower()):
            return True
    return False


def _should_monitor_deck(info: DeckInfo, config: dict) -> bool:
    if info.is_filtered:
        return False

    use_regex = bool(config.get("use_regex_patterns", False))
    include_patterns = config.get("include_patterns", [])
    exclude_patterns = config.get("exclude_patterns", [])

    included = True
    if include_patterns:
        included = _matches_any_pattern(info.name, include_patterns, use_regex)
    if not included:
        return False
    if exclude_patterns and _matches_any_pattern(info.name, exclude_patterns, use_regex):
        return False
    return True


def _is_problematic(info: DeckInfo) -> bool:
    return info.agg_status in (STATUS_LIMITS, STATUS_AVAIL)


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
        count = mw.col.db.scalar("select count() from cards where did=?", did)
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

        info_by_name[name] = DeckInfo(
            did=did,
            name=name,
            is_filtered=is_filtered,
            total_cards=_count_total_cards(did),
            new_limit=new_limit,
            limit_source=limit_source,
            unsuspended_new=unsuspended_new,
            suspended_new=suspended_new,
            self_status=_compute_self_status(new_limit, unsuspended_new),
        )
        deck_names.append(name)

    parents = set()
    for name in deck_names:
        parent = _parent_name(name)
        while parent:
            parents.add(parent)
            parent = _parent_name(parent)
    for name, info in info_by_name.items():
        info.is_container = info.total_cards == 0 and name in parents

    return info_by_name, deck_names


def _apply_monitoring(info_by_name: Dict[str, DeckInfo], deck_names: List[str], config: dict) -> None:
    container_mode = config.get("container_deck_mode", CONTAINER_MODE_AGGREGATE)
    agg_unsuspended: Dict[str, int] = {}
    agg_suspended: Dict[str, int] = {}
    agg_has_monitored: Dict[str, bool] = {}
    agg_has_limits: Dict[str, bool] = {}

    for name, info in info_by_name.items():
        info.monitored = _should_monitor_deck(info, config)
        agg_unsuspended[name] = info.unsuspended_new if info.monitored else 0
        agg_suspended[name] = info.suspended_new if info.monitored else 0
        agg_has_monitored[name] = info.monitored
        agg_has_limits[name] = info.monitored and info.self_status == STATUS_LIMITS

    if container_mode == CONTAINER_MODE_DIRECT:
        for name, info in info_by_name.items():
            info.agg_has_monitored = agg_has_monitored.get(name, False)
            info.agg_unsuspended_new = agg_unsuspended.get(name, 0)
            info.agg_suspended_new = agg_suspended.get(name, 0)
            info.agg_status = info.self_status if info.agg_has_monitored else None
        return

    for name in sorted(deck_names, key=lambda item: item.count("::"), reverse=True):
        parent = _parent_name(name)
        if not parent or parent not in info_by_name:
            continue
        agg_unsuspended[parent] = agg_unsuspended.get(parent, 0) + agg_unsuspended.get(name, 0)
        agg_suspended[parent] = agg_suspended.get(parent, 0) + agg_suspended.get(name, 0)
        agg_has_monitored[parent] = agg_has_monitored.get(parent, False) or agg_has_monitored.get(
            name, False
        )
        agg_has_limits[parent] = agg_has_limits.get(parent, False) or agg_has_limits.get(
            name, False
        )

    for name, info in info_by_name.items():
        info.agg_has_monitored = agg_has_monitored.get(name, False)
        info.agg_unsuspended_new = agg_unsuspended.get(name, 0)
        info.agg_suspended_new = agg_suspended.get(name, 0)

        if not info.agg_has_monitored:
            info.agg_status = None
        elif agg_has_limits.get(name, False):
            info.agg_status = STATUS_LIMITS
        elif info.agg_unsuspended_new <= 0:
            info.agg_status = STATUS_AVAIL
        else:
            info.agg_status = STATUS_NORMAL


def _should_show_badge(info: DeckInfo, config: dict) -> bool:
    if not info.monitored or not _is_problematic(info):
        return False
    container_mode = config.get("container_deck_mode", CONTAINER_MODE_AGGREGATE)
    if info.is_container and container_mode in {CONTAINER_MODE_HIDE, CONTAINER_MODE_DIRECT}:
        return False
    return True


def _badge_tooltip(info: DeckInfo, config: dict) -> str:
    container_mode = config.get("container_deck_mode", CONTAINER_MODE_AGGREGATE)
    if container_mode == CONTAINER_MODE_DIRECT:
        if info.agg_status == STATUS_LIMITS:
            return (
                "This deck is blocked by a 0/day new-card limit. "
                f"Unsuspended new: {info.agg_unsuspended_new}. "
                f"Suspended new: {info.agg_suspended_new}."
            )
        return (
            "This deck has 0 unsuspended new cards available. "
            f"Suspended new: {info.agg_suspended_new}."
        )

    if info.is_container:
        limits_prefix = "Included child decks under this container are blocked by a 0/day new-card limit. "
        availability_prefix = (
            "Included child decks under this container have 0 unsuspended new cards available. "
        )
    else:
        limits_prefix = "This deck or an included child deck is blocked by a 0/day new-card limit. "
        availability_prefix = "This deck or an included child deck has 0 unsuspended new cards available. "
    if info.agg_status == STATUS_LIMITS:
        return limits_prefix + (
            f"Unsuspended new: {info.agg_unsuspended_new}. "
            f"Suspended new: {info.agg_suspended_new}."
        )

    return availability_prefix + f"Suspended new: {info.agg_suspended_new}."


def _render_badge_html(info: DeckInfo, config: dict) -> str:
    if info.agg_status == STATUS_LIMITS:
        badge_class = "notify-empty-decks-badge notify-empty-decks-badge-limits"
        label = "0/day new-card limit"
    else:
        badge_class = "notify-empty-decks-badge notify-empty-decks-badge-availability"
        label = "No unsuspended new cards available"

    tooltip = escape(_badge_tooltip(info, config), quote=True)
    aria_label = escape(label, quote=True)
    return f'<span class="{badge_class}" title="{tooltip}" aria-label="{aria_label}">!</span>'


def _inject_badges(tree_html: str, badges_by_did: Dict[int, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        badge = badges_by_did.get(int(match.group(2)))
        if not badge:
            return match.group(1)
        return f"{match.group(1)}{badge}"

    return DECK_LINK_RE.sub(repl, tree_html)


def _decorate_deck_browser(deck_browser, content) -> None:
    if not mw or not mw.col:
        return

    config = _load_config()
    info_by_name, deck_names = _build_deck_info()
    if not info_by_name:
        return

    _apply_monitoring(info_by_name, deck_names, config)

    badges_by_did = {
        info.did: _render_badge_html(info, config)
        for info in info_by_name.values()
        if _should_show_badge(info, config)
    }
    if not badges_by_did:
        return

    content.tree = BADGE_STYLE + _inject_badges(content.tree, badges_by_did)


def _refresh_deck_browser() -> None:
    if not mw:
        return

    deck_browser = getattr(mw, "deckBrowser", None)
    if deck_browser and getattr(mw, "state", None) == "deckBrowser":
        deck_browser.refresh()


def _update_pattern_mode_help(dialog: QDialog) -> None:
    use_regex = dialog.use_regex_checkbox.isChecked()
    if use_regex:
        dialog.mode_help.setText(
            "Regex mode uses case-insensitive Python regexes against the full deck name."
        )
        dialog.include_edit.setPlaceholderText("^Languages($|::)\n^Music::")
        dialog.exclude_edit.setPlaceholderText("::Archive$\n::Suspended$")
    else:
        dialog.mode_help.setText(
            "Wildcard mode is case-insensitive. Use `*` for any text and `?` for one character."
        )
        dialog.include_edit.setPlaceholderText("Languages*\nMusic::*")
        dialog.exclude_edit.setPlaceholderText("*Archive*\n*::Suspended")


def _update_container_mode_help(dialog: QDialog) -> None:
    mode = dialog.container_mode_combo.currentData()
    if mode == CONTAINER_MODE_AGGREGATE:
        dialog.container_mode_help.setText(
            "Container rows can show badges that summarize included descendant decks."
        )
    elif mode == CONTAINER_MODE_HIDE:
        dialog.container_mode_help.setText(
            "Container rows stay quiet, but included descendant decks can still show badges."
        )
    else:
        dialog.container_mode_help.setText(
            "Only a deck's own direct cards are considered. Descendant decks do not affect parents."
        )


def _save_settings(dialog: QDialog) -> None:
    config = _load_config()
    use_regex = dialog.use_regex_checkbox.isChecked()
    include_patterns = _normalize_pattern_list(dialog.include_edit.toPlainText())
    exclude_patterns = _normalize_pattern_list(dialog.exclude_edit.toPlainText())

    error = _validate_patterns(include_patterns, use_regex, "include")
    if error:
        showInfo(error)
        return

    error = _validate_patterns(exclude_patterns, use_regex, "exclude")
    if error:
        showInfo(error)
        return

    config["use_regex_patterns"] = use_regex
    config["include_patterns"] = include_patterns
    config["exclude_patterns"] = exclude_patterns
    config["container_deck_mode"] = dialog.container_mode_combo.currentData()
    _save_config(config)
    _refresh_deck_browser()
    dialog.close()


def _build_settings_dialog() -> QDialog:
    dialog = QDialog(mw)
    dialog.setModal(False)
    layout = QVBoxLayout(dialog)

    intro = QLabel(
        "Show a warning badge beside deck rows when included decks are blocked by a 0/day "
        "limit or have no unsuspended new cards left."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    note = QLabel("Filtered decks are always ignored. Enter one include/exclude pattern per line.")
    note.setWordWrap(True)
    layout.addWidget(note)

    form = QFormLayout()

    dialog.use_regex_checkbox = QCheckBox("Use regular expressions")
    form.addRow("Pattern mode", dialog.use_regex_checkbox)

    dialog.container_mode_combo = QComboBox()
    for value, label in CONTAINER_MODE_CHOICES:
        dialog.container_mode_combo.addItem(label, value)
    form.addRow("Container decks", dialog.container_mode_combo)

    dialog.include_edit = QPlainTextEdit()
    dialog.include_edit.setTabChangesFocus(True)
    dialog.include_edit.setFixedHeight(110)
    form.addRow("Include", dialog.include_edit)

    dialog.exclude_edit = QPlainTextEdit()
    dialog.exclude_edit.setTabChangesFocus(True)
    dialog.exclude_edit.setFixedHeight(110)
    form.addRow("Exclude", dialog.exclude_edit)

    dialog.mode_help = QLabel()
    dialog.mode_help.setWordWrap(True)
    form.addRow("", dialog.mode_help)

    dialog.container_mode_help = QLabel()
    dialog.container_mode_help.setWordWrap(True)
    form.addRow("", dialog.container_mode_help)

    layout.addLayout(form)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
    )
    buttons.accepted.connect(lambda: _save_settings(dialog))
    buttons.rejected.connect(dialog.close)
    layout.addWidget(buttons)

    dialog.use_regex_checkbox.toggled.connect(lambda _: _update_pattern_mode_help(dialog))
    dialog.container_mode_combo.currentIndexChanged.connect(
        lambda _: _update_container_mode_help(dialog)
    )
    return dialog


def _show_settings() -> None:
    global _settings_dialog
    if not mw:
        return

    if _settings_dialog is None:
        _settings_dialog = _build_settings_dialog()

    config = _load_config()
    _settings_dialog.setWindowTitle(f"Notify Empty Decks Settings (v{ADDON_VERSION})")
    _settings_dialog.use_regex_checkbox.setChecked(bool(config.get("use_regex_patterns", False)))
    index = _settings_dialog.container_mode_combo.findData(config.get("container_deck_mode"))
    if index >= 0:
        _settings_dialog.container_mode_combo.setCurrentIndex(index)
    _settings_dialog.include_edit.setPlainText("\n".join(config.get("include_patterns", [])))
    _settings_dialog.exclude_edit.setPlainText("\n".join(config.get("exclude_patterns", [])))
    _update_pattern_mode_help(_settings_dialog)
    _update_container_mode_help(_settings_dialog)
    _settings_dialog.resize(560, 420)
    _settings_dialog.show()
    _settings_dialog.raise_()
    _settings_dialog.activateWindow()


def _add_menu_action() -> None:
    global _menu_action
    if not mw or _menu_action is not None:
        return

    _menu_action = QAction("Notify Empty Decks Settings", mw)
    _menu_action.triggered.connect(_show_settings)
    mw.form.menuTools.addAction(_menu_action)


def _on_profile_open() -> None:
    _add_menu_action()


gui_hooks.deck_browser_will_render_content.append(_decorate_deck_browser)
gui_hooks.profile_did_open.append(_on_profile_open)
