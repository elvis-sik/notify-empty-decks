# Notify Empty Decks

`Notify Empty Decks` is an Anki add-on for finding decks that show no new cards, and explaining why.

It separates the two common cases:

- `0/day (limits)`: the deck's effective new limit is zero.
- `0 available (unsuspended)`: the limit allows new cards, but no unsuspended new cards are currently available.

This makes it easier to decide when to unsuspend the next deck in your sequence.

## What It Does

From `Tools -> Find Empty New-Card Decks`, the add-on opens a report window with:

- Deck tree with parent/child hierarchy.
- Status column (`0/day (limits)`, `0 available (unsuspended)`, `Has new cards`).
- `New/day`, `Unsuspended new`, and `Suspended new` columns.
- Color coding for status and deck type (filtered, container, empty).
- Clickable headers for column sorting.
- Live filters for deck kinds and status categories.

## Hierarchy + Name Filter Behavior

When filtering by name, matching decks remain visible with parent context preserved.

- Matching rows are "active".
- Parent rows that are shown only to preserve structure are muted gray.

This keeps nested decks readable while still narrowing the list.

## Status Rules

- Parent deck status is aggregated from descendants using priority:
1. `limits`
2. `availability`
3. `normal`
- Counts shown in the table are aggregated counts (deck + descendants).

## Deck Types

- `Container deck`: has no cards directly, but has child decks.
- `Empty deck`: has no cards and no child decks.
- `Filtered deck`: dynamic Anki deck (`dyn`).

## Auto-Open / Notification Behavior

The report can open automatically on profile load:

- `notify_never = true`: never auto-open.
- `notify_every_n_days = 0`: open every profile open.
- `notify_every_n_days > 0`: open only if last open was at least N days ago.

## Configuration

Settings are stored in `config.json` and also driven by the report UI.

- `menu_title`: Tools menu label.
- `show_when_profile_opens`: open report when profile opens.
- `notify_every_n_days`: days between auto-open checks (`0` means every time).
- `notify_never`: disable auto-open behavior.
- `last_opened_at`: internal timestamp used by auto-open logic.
- `name_filter`: substring filter for deck names.
- `filter_filtered_decks`: include filtered decks.
- `filter_container_decks`: include container decks.
- `filter_empty_decks`: include empty decks.
- `filter_limits_zero`: include `0/day (limits)` rows.
- `filter_available_zero`: include `0 available (unsuspended)` rows.
- `filter_has_new`: include `Has new cards` rows.

## Install (From Source)

1. Clone this repository.
2. Copy or symlink it to your Anki addons folder as `notify-empty-decks`:
   - macOS example: `~/Library/Application Support/Anki2/addons21/notify-empty-decks`
3. Restart Anki.

## Compatibility

- Built for Anki 25.x (Qt6/PyQt6 environment).
