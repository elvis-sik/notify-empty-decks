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
- `show_all_decks`: Include decks that still have new cards (defaults to false).

## Manual Verification

- Create a deck with 0 new/day and confirm it shows as limits block.
- Suspend all new cards in a deck with a positive limit and confirm it shows as availability block.
- Verify parent decks reflect child status using the ANY rule.
