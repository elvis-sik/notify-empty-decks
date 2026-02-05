# Notify Empty Decks - Design

## Goal
Help identify decks with no new cards so you can decide what to study next or which decks to unsuspend from.

## User Story
- Example: `Música` → `Audio Cards` and `Silent Cards` → `Sheet`.
- You have G cleff cards unsuspended and F cleff cards suspended.
- You want to know when the G cleff cards are done so you can unsuspend F cleff.
- There are many decks, so manual checking is too tedious.

## Status Categories
The design should surface two different "empty" cases:

1. **Zero due to limits (0/day)**
   - Decks whose effective new cards/day is 0.
   - This may be caused by `Preset`, `This deck`, or `Today only` settings.
   - Intention: "You will see 0 new cards regardless of availability."

2. **Zero due to availability**
   - Decks with a positive new-cards/day limit but currently no *unsuspended* new cards.
   - Intention: "You could see new cards, but none are available right now."

## Aggregation Rules (Parents)
- Parent decks aggregate from children using **ANY** semantics:
  - If any child deck is in a given status category, the parent should reflect that category.
  - If children span multiple categories, choose a priority order (see below).

## Proposed Visual Encoding
- Use icons + color to avoid ambiguity.
- Suggested mapping:
  - **Limits block (0/day):** Red circle with slash (or red badge). Suggested color: `#C0392B`.
  - **Availability block (no unsuspended new cards):** Amber dot/badge. Suggested color: `#F39C12`.
  - **Normal / has new cards:** Green dot. Suggested color: `#27AE60`.
- Text fallback should be available in tooltips or list rows:
  - "0 new cards/day (limits)"
  - "0 available new cards (all suspended or none exist)"

## Parent Priority (When Mixed)
- If any child is **limits block** → parent shows limits block.
- Else if any child is **availability block** → parent shows availability block.
- Else parent is normal.

## Notification Channel Options
These are compatible with Anki add-ons and can be configured:

1. **Tools menu action (manual)**
   - Current default. Least intrusive.
   - Good for checking when you want to plan study time.

2. **Popup on profile open (optional)**
   - Quick summary modal with counts and top-level deck list.
   - Add a preference to enable/disable.

3. **Status bar summary**
   - Always visible; shows counts per category.
   - Clicking opens the full report.

4. **Daily notification (scheduled)**
   - On first open per day, show a summary.
   - Optional and configurable.

## Open Questions
- Should the report list only "empty" decks, or show all decks with status badges?
- Should we include counts per deck (new limit, available new, total suspended new)?
- When a parent is in a mixed state, do you want a combined badge or strictly the priority rules?

## Next Step Proposal
- Implement a summary dialog listing decks by category, grouped by top-level deck, with badges.
- Add an option to enable profile-open popup with a brief summary and a "View details" button.
