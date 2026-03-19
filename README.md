# Notify Empty Decks

Anki add-on for people with many too many decks who want to keep track of which of their decks still are showing new cards every day.

AnkiWeb: https://ankiweb.net/shared/info/1630214543

## Who This Is For

This is mainly useful if:

- You have a large deck tree.
- You keep some decks or cards suspended until others are finished.
- You introduce new cards slowly across many decks.
- Some decks can quietly stop showing new cards and you do not notice right away.

If that sounds familiar, this add-on helps you catch "silent" deck exhaustion quickly.

## The Problem It Solves

If you have dozens of decks, you usually do not click into each deck just to check whether it is still showing new cards. You study what is in front of you and move on.

That means a deck can silently stall: it stops showing new cards because its new limit is `0/day`, or because there are `0` unsuspended new cards left, and you only notice much later.

The alternative is checking decks one-by-one via the Decks screen, Options, or Browse, which is slow in large collections.

This add-on surfaces the problem right in the deck list, so you notice it where you already work.

## What You See

On the main Decks screen, included decks get a warning badge when they are in one of these states:

- `0/day (limits)`
- `0 available (unsuspended)`

Hover a badge to see which condition triggered it.

Open `Tools -> Notify Empty Decks Settings` to control which decks are monitored.

- Filtered decks are always ignored.
- Hover text explains each icon directly, so there is no legend to memorize.
- Include and exclude rules are matched against the full deck name.
- Wildcard mode supports `*` and `?`.
- Regex mode uses case-insensitive Python regular expressions.
- Parent/container rows can use explicit `any` or `all` descendant logic, hide their own icons, or disable parent aggregation entirely.
- Optional Fractional Scheduler integration can treat decks as healthy when they still have unsuspended new cards and are scheduled to receive `>0` new cards again in a future cycle.

## Typical Workflow

1. Study as usual.
2. Notice a badge beside a deck that has stalled.
3. Hover the badge to see whether the blocker is limits or availability.
4. Unsuspend the next deck in your pipeline when needed.

## Configuration Examples

Wildcard mode:

- Include `Languages*` to monitor a whole subtree.
- Exclude `*::Archive` to skip archive decks.

Regex mode:

- Include `^Languages($|::)` to monitor `Languages` and all children.
- Exclude `::Suspended$` to ignore decks whose names end with `::Suspended`.

Parent/container row modes:

- `Any blocked descendant`: a parent/container row gets a badge if any included descendant deck is blocked.
- `All included descendants blocked`: a parent/container row only gets a badge if every included descendant deck is blocked.
- `Hide container icons`: only descendant deck rows show badges.
- `Direct decks only`: each row only reflects its own direct cards.

Fractional Scheduler override:

- When enabled, a deck with unsuspended new cards is treated as healthy if the Fractional Scheduler API reports that its repeating schedule will yield `>0` new cards again at some point.
- This is optional and defaults off.

## Install (From Source)

1. Clone this repository.
2. Copy or symlink it to your Anki addons folder as `notify-empty-decks`:
   - macOS example: `~/Library/Application Support/Anki2/addons21/notify-empty-decks`
3. Restart Anki.

## Notes

- Works in Anki's Qt6/PyQt6 environment (Anki 25.x).
- Settings are stored in `config.json`.
