# Notify Empty Decks

An Anki add-on to list decks that currently have **zero new cards**, so you can decide what to study next or which deck to unsuspend from.

## Development

1. Clone this repo into your Anki add-ons folder (e.g. `.../Anki2/addons21/notify-empty-decks`).
2. Restart Anki.
3. Use the Tools menu item: **Find Empty New-Card Decks**.

## Status

Prototype UI and deck-detection logic are in place; refine as needed for your workflow.

## Configuration

Edit `config.json`:

- `menu_title`: Customize the Tools menu label.
- `show_when_profile_opens`: Show the report dialog after a profile opens.
- `notify_every_n_days`: Open the report automatically if it hasn’t been opened in N days (0 = every time).
- `notify_never`: Disable notifications entirely (defaults to true).
- `name_filter`: Optional substring filter used by the dialog.
- `filter_filtered_decks`: Include filtered decks in the report.
- `filter_container_decks`: Include container decks in the report.
- `filter_empty_decks`: Include empty decks (no cards, no children).
- `filter_limits_zero`: Include decks with 0/day limits.
- `filter_available_zero`: Include decks with 0 available unsuspended new cards.
- `filter_has_new`: Include decks that still have new cards.

## Features

- Non-blocking report window with a refresh button.
- Column widths are resizable and persist across refreshes.
- Tooltips explain deck types, filters, and counts.
- Color-coded deck status (limits, availability, normal), with overrides for filtered, container, and empty decks.
- Container deck = no cards directly in the deck, but has child decks. Empty deck = no cards and no children.
- Separate counts for unsuspended and suspended new cards.
- Filter options in the dialog to narrow which deck categories are shown.
- Name filter (note: breaks nesting).

## Manual Verification

- Create a deck with 0 new/day and confirm it shows as limits block.
- Suspend all new cards in a deck with a positive limit and confirm it shows as availability block.
- Verify parent decks reflect child status using the ANY rule.
