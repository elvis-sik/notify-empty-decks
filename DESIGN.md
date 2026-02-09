# Notify Empty Decks - Design

## Goal
Help users quickly understand why a deck currently shows no new cards, so they can decide when to unsuspend the next deck in their study pipeline.

## Example Workflow
A user studies music-reading decks in sequence:

- `Music Reading::Treble`
- `Music Reading::Bass`

They keep `Treble` unsuspended and `Bass` suspended until `Treble` runs out of new cards. With many decks, manually checking each one is slow and error-prone. This add-on provides a single report that shows deck status and the reason.

## Core Status Model
The report distinguishes two different "zero new cards" states:

1. **Zero due to limits (`0/day (limits)`)**
   - Effective new-cards/day is `0`.
   - Usually caused by deck or preset limits.
   - Meaning: no new cards will be shown even if cards exist.

2. **Zero due to availability (`0 available (unsuspended)`)**
   - Deck limit is positive, but unsuspended new-card count is `0`.
   - Meaning: the deck could show new cards, but none are currently available.

3. **Normal (`Has new cards`)**
   - Unsuspended new cards are available.

## Hierarchy and Aggregation
- Decks are shown as a tree.
- Parent deck status is derived from children using priority:
1. `limits`
2. `availability`
3. `normal`
- Aggregated counts (unsuspended and suspended new cards) include descendants.

## Filtering Behavior
- UI filters can include/exclude deck categories and status categories.
- Name filtering preserves hierarchy context:
  - Matching rows are active.
  - Ancestor rows required to keep structure are shown in muted gray.

## Visual Encoding
- Status colors:
  - Limits: `#C0392B`
  - Availability: `#F39C12`
  - Normal: `#27AE60`
- Deck-type overrides:
  - Filtered decks: blue
  - Container decks: black
  - Empty decks: gray

## Deck Type Definitions
- **Container deck**: no direct cards, but has child decks.
- **Empty deck**: no cards and no child decks.
- **Filtered deck**: dynamic deck (`dyn` flag).

## Report UI
Columns:

- Deck
- Status
- New/day
- Unsuspended new
- Suspended new

Behavior:

- Clickable column headers for sorting.
- Hover tooltips explain status and count meaning.
- Refresh button recomputes all values.

## Notification and Launch
- Manual launch from `Tools -> Find Empty New-Card Decks`.
- Optional profile-open behavior via config:
  - `notify_never = true`: disable automatic opening.
  - `notify_every_n_days = 0`: open every profile load.
  - `notify_every_n_days > 0`: open only after N days since last open.
