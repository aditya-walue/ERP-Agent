---
version: alpha
name: ChangAI Widget
description: Design system for the ChangAI floating chat assistant embedded in ERPNext — a small, always-available panel a business user glances at between other tasks, not a destination screen.

colors:
  primary: "#6d4fc2"
  secondary: "#4a3689"
  tertiary: "#12b981"
  neutral: "#e4e0ec"
  surface: "#fdfcff"
  on-surface: "#0f172a"
  error: "#b4344f"

typography:
  wordmark:
    fontFamily: Fraunces
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0.005em
  headline-sm:
    fontFamily: Fraunces
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: 0em
  body-md:
    fontFamily: Manrope
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.6
    letterSpacing: 0em
  body-sm:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0em
  input-text:
    fontFamily: Manrope
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0em
  button-label:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0.01em
  caption:
    fontFamily: Manrope
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.01em
  label-caps:
    fontFamily: Manrope
    fontSize: 10px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0.1em
  micro-caps:
    fontFamily: Manrope
    fontSize: 8px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0.14em

rounded:
  none: 0px
  xs: 6px
  sm: 10px
  md: 14px
  lg: 16px
  full: 9999px

spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px

components:
  shell:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
  header:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.surface}"
    typography: "{typography.wordmark}"
    padding: "{spacing.md}"
  bubble-bot:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.sm}"
  bubble-user:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.sm}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.button-label}"
    rounded: "{rounded.full}"
    padding: "{spacing.sm}"
  button-primary-hover:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.full}"
    padding: "{spacing.sm}"
  button-stop:
    backgroundColor: "{colors.error}"
    textColor: "{colors.surface}"
    typography: "{typography.button-label}"
    rounded: "{rounded.full}"
    padding: "{spacing.sm}"
  toggler:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    size: 56px
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.input-text}"
    rounded: "{rounded.full}"
    padding: "{spacing.sm}"
  input-error:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.error}"
    typography: "{typography.caption}"
  status-badge:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-surface}"
    typography: "{typography.micro-caps}"
    rounded: "{rounded.full}"
    padding: "{spacing.xs}"
---

# ChangAI Widget

## Overview

ChangAI is a floating assistant docked in the corner of an ERPNext desk session. It is never the main task — it sits alongside invoices, sales orders, and BOMs, opened for ten seconds at a time between whatever the user was actually doing. That usage pattern set every decision here: dense type, tight vertical rhythm, a single confident brand color instead of a chart's worth of them, and motion that stays a background hum rather than a performance.

The direction is **quiet violet institutional** — one deliberate hue (a mineral violet closer to amethyst than to indigo-default-blue) carried through the whole surface via tint and shade rather than diluted by a rotating cast of accent colors, paired with a single moment of warmth: a serif wordmark in the header, the one place the product gets to say its own name with some character. Everywhere else is a working Manrope grotesque, because a panel this small has no room for a second personality fighting the first.

What this gives up: no illustration, no gradient hero, no bright secondary accent competing with the violet. Emerald appears in exactly one place (a presence dot) and nowhere else — if a future screen wants a second accent color, that is a real design decision to bring back here, not a default to reach for.

## Colors

The palette is anchored on `primary` (#6d4fc2), a mineral violet — closer to the color of amethyst quartz than to the indigo-500 every AI-assisted dashboard reaches for by default. `secondary` (#4a3689) is the same hue pushed three steps into shadow, used wherever primary needs to sit on light backgrounds requiring a heavier contrast margin (button text-on-neutral, the header bar) rather than being treated as an unrelated "dark mode" color.

- **Primary — "amethyst" (#6d4fc2):** the sole driver of interactive surfaces — the user's own message bubbles, the launcher button, primary actions. If it's clickable and important, it's this color; nothing else is allowed to compete for that job.
- **Secondary — "amethyst, in shadow" (#4a3689):** primary's own hue at higher contrast. Used for the header bar and for text that sits on a light neutral chip, never introduced as an independent color decision.
- **Tertiary — "presence green" (#12b981):** the one accent, and it has exactly one job — the online/active status dot. It does not appear on buttons, links, or any other surface; an accent used twice stops being an accent.
- **Neutral — "amethyst ash" (#e4e0ec):** a grey that has never been true grey — it is primary desaturated and lightened, not Tailwind's `slate-200`. Backs the assistant's own message bubbles and secondary buttons, so even the "quiet" surfaces still carry the brand's hue at a whisper.
- **Surface — "warm paper" (#fdfcff):** the panel's base. Not pure white — a hair of warmth keeps a full-height violet-bordered panel from reading as clinical.
- **On-surface — "near ink" (#0f172a):** body text. Kept close to true black rather than tinted, deliberately, because at 12-13px in a narrow panel legibility wins over hue-matching; this is the one token allowed to be color-neutral.
- **Error — "wine" (#b4344f):** derived by rotating primary's hue toward red rather than dropping in stock Tailwind rose — it reads as "this system's version of alarm," not a component library default bleeding through.

## Typography

Two families, doing two different jobs. **Fraunces** (serif, optical-size axis) appears in exactly one place: the header wordmark and section-opening headlines. It is the one moment of warmth and craft in an otherwise utilitarian panel, which is exactly why it's rationed — if it appeared in the message stream too it would stop reading as a signature. **Manrope** (grotesque sans) carries everything else: messages, buttons, labels, captions. Fallback stacks: `Fraunces, "Manrope", "Segoe UI", serif` and `Manrope, "Plus Jakarta Sans", "Segoe UI", "Helvetica Neue", sans-serif`; both load from Google Fonts and are open-licensed.

The scale is deliberately compact and skews small — this is a 320-420px-wide panel, not a page — running from `micro-caps` (8px, for a single "THINKING" status pulse) up to `wordmark` (17px, the header only). Tracking moves the way it should: positive and wide on the all-caps labels (`label-caps` at 0.1em, `micro-caps` at 0.14em — uppercase at 8-10px needs the extra air to stay legible), flat everywhere else. Body copy runs loose (1.5-1.6 line-height) because message bubbles are read at a glance, not studied; label and caption sizes tighten up because they're short and don't need it.

## Layout

Single-column, no grid to speak of — a message stream, a composer, a header. The spacing base is 4px, and the panel stays dense on purpose: `spacing.sm` (8px) between related elements, `spacing.lg` (16px) as the outer panel padding, nothing bigger than `spacing.xl` (24px) anywhere, because generous whitespace is a page-layout habit that just wastes room in a 400px-wide floating panel. Symmetric, not asymmetric — a chat log is inherently a two-column back-and-forth (bot left, user right) and doesn't want a competing off-center layout on top of it.

## Elevation & Depth

No neutral-black shadows anywhere. Depth comes from two sources: a **colored, hue-matched shadow** on anything that floats above the page (the launcher button, the open panel) — always cast from a dark, desaturated point on the primary ramp, never flat black, so the shadow reads as "this violet object, lifted" rather than a generic Material elevation token; and **hairline borders** at low opacity for anything that just needs separation without implying it's floating (cards, the message list edge). The border color is primary at roughly 12-14% opacity over the surface color, not a separate grey — a bordered card and a violet button are visibly the same design system, not two different ones glued together.

## Shapes

Radius is hierarchical and used to communicate a specific relationship, not applied uniformly. The panel shell uses the largest radius (`rounded.lg`); cards and inputs sit one step down (`rounded.md`/`rounded.sm`); anything that behaves like a physical pill — buttons, the launcher, the input field — goes all the way to `rounded.full`, because a control you tap or click reads as more "grabbable" fully rounded, while a container reads as more "roomy" with a moderate corner.

Message bubbles are the one deliberate exception to a single named radius: both bot and user bubbles use `rounded.sm` (10px) on three corners, but the corner nearest the sender's own avatar is cut sharp (3px) instead — a tail implied by geometry instead of an actual triangle asset. Bot bubbles cut the bottom-left corner; user bubbles cut the bottom-right. This asymmetry is the panel's one shape signature; it should not be extended to other components (cards, chips) or it stops reading as "this is a spoken message" and starts reading as inconsistency.

## Components

- **button-primary / button-primary-hover:** the send button and any single primary action. Hover moves from `primary` to `secondary` — a value shift within the same hue, never a different color family.
- **button-secondary:** low-emphasis actions (retry, dismiss) — neutral background, secondary-colored text, so it reads as "still branded, just quieter," not grey-and-forgotten.
- **button-stop:** the one place `error` appears as a background — the in-flight "stop generating" control. Never reuse `error`'s red for anything that isn't stopping or reporting a failure.
- **toggler:** the closed-state floating launcher. Fixed 56px circle, `primary` background, carries the colored elevation shadow described above at all times (not just on hover) since it must read as tappable while sitting on top of arbitrary ERPNext screen content.
- **bubble-bot / bubble-user:** see Shapes for the asymmetric-corner treatment. Bot bubbles use `neutral`; user bubbles use `primary` — the only two colors ever used for message backgrounds.
- **status-badge:** the presence/online indicator. The only component allowed to use `tertiary`; do not repurpose it as a generic "success" or "new" tag elsewhere.
- **input / input-error:** the composer field. `input-error` swaps only the text color to `error` for a validation message beneath the field — the field's own background never changes to red; a red-flooded input in a chat composer reads as more alarming than a single line of red caption text needs to.

## Do's and Don'ts

- Do keep Fraunces confined to the header wordmark and section headlines — if it starts appearing in body copy or buttons, the "one warm moment" stops being one.
- Do build every grey from `neutral`, not from a framework default — this system has already collapsed what used to be three separate stock Tailwind greys (`slate-200`/`slate-400`/`slate-600`) into that single violet-tinted token; don't reintroduce a fourth.
- Do cast shadows from the primary ramp, never flat black — a black shadow under a violet panel is the fastest way to make this look like it was assembled from a component library rather than designed.
- Don't add a second accent color. `tertiary` (emerald) has one job — the presence dot. A "new" badge, a warning chip, a highlight — reach for weight, size, or `error`/`primary` before introducing a third hue.
- Don't round every corner the same amount. The bubble tail asymmetry is the system's signature shape move; flattening it to a uniform `rounded.sm` everywhere for "consistency" removes the one thing that makes a bubble read as spoken rather than boxed.
- Don't use `error` for anything but a stop action or a validation message. It should stay rare enough that seeing it is itself a signal.
