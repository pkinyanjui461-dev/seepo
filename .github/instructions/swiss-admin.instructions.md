---
applyTo: "templates/accounts/*admin*.html"
description: "Use when building internal data-management/admin interfaces in SEEPO. Apply Swiss/International style with strict grids, high typography contrast, and minimal visual noise."
---

# Swiss / International Admin Instruction

## Core Philosophy
- Essentialism first: remove anything that does not help data editing.
- Content is king: model, field, and value clarity beats decoration.
- Objective layout: strict grid, predictable spacing, and no playful UI gimmicks.

## Visual Rules
- Typography:
  - Use strong sans-serif stacks (Helvetica Neue, Helvetica, Arial, sans-serif).
  - Favor uppercase section labels and high-weight headings.
  - Keep body text compact and legible for dense tables.
- Color system:
  - Base palette is black/white/gray plus one accent color.
  - Accent color is reserved for active state, primary actions, and key status.
  - Avoid gradients unless they communicate hierarchy with restraint.
- Layout:
  - Use rigid column grids and clear section boundaries.
  - Preserve generous whitespace around groups of controls.
  - Keep table headers visually dominant and easy to scan.

## Interaction Rules
- Show editable fields only unless a read-only field is needed for context.
- Keep create/update/delete controls explicit and visually separated.
- Put destructive actions in high-contrast warning styles.
- Provide immediate, specific validation errors at field level and message level.

## Data Editing Rules
- Normalize input types by field type (date, datetime, checkbox, select, number, text).
- Validate and coerce safely before save; never silently drop invalid user input.
- Display model counts and current table context in navigation.
- Keep pagination simple and explicit (Prev/Next + page summary).

## Accessibility Rules
- Ensure strong text/background contrast in light and dark themes.
- Keep form labels visible and concise.
- Avoid icon-only controls for critical actions.
- Preserve keyboard-friendly tab order and submit behavior.

## Offline and Sync Rules
- Any admin/data-edit page should define clear online/offline behavior.
- If online-only, show direct user-facing offline reason messaging.
- Keep versioned static assets and SW cache entries aligned so style/behavior updates appear reliably.

## Voice and Tone
- Direct.
- Bold.
- Confident.
- No decorative copy that distracts from data operations.
