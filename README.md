# Notify Empty Decks

An Anki add-on to list decks that currently have **zero new cards**, so you can decide what to study next or which deck to unsuspend from.

## Development

1. Clone this repo into your Anki add-ons folder (e.g. `.../Anki2/addons21/notify-empty-decks`).
2. Restart Anki.
3. Use the Tools menu item: **Find Empty New-Card Decks**.

## Status

The UI scaffold is in place; core deck-detection logic is still TODO.

## Configuration

Edit `config.json`:

- `menu_title`: Customize the Tools menu label.
- `show_when_profile_opens`: Reserved for future use.
