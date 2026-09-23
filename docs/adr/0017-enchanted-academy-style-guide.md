# 17. The Enchanted Academy style guide is the project's visual reference

Date: 2026-09-23

## Status

Accepted, with three questions for the maintainer left open in *Open questions*
below. Those three do not block the adoption; they decide how far it goes.

## Context

Until now the visual language lived in two places: ADR 0005 (theme without
franchise assets) as a rule, and `web/src/lib/ui/tokens.css` as an implementation
Workstream I derived from it. There was no document a new workstream could read to
know what the app is *supposed to look like* — so every screen negotiated its own
answer, and the mockup produced on 21 September had to be assembled by reading
components rather than a guide.

The maintainer supplied a full print-and-web style guide, *Enchanted Academy*, on
2026-09-23. It is now `docs/design/style-guide.md`, verbatim in substance.

It arrives after S0–S2 shipped a working design system, so this ADR is mostly about
reconciliation: what the guide changes, what it cannot change, and what it asks for
that the app must decline.

## Decision

**`docs/design/style-guide.md` is the project's reference style guide.** It governs
creative direction — palette, typography, ornament, illustration, motion, print and
packaging — for every surface: the PWA, the Journal plates, printed labels and any
future print artefact.

It is owned by **A** and changed only by ADR, like `contracts/`. It is added to
`A_ONLY` in `scripts/check_ownership.py` so the check enforces that.

It does **not** override three things, in this order:

1. **Accessibility.** Rule 5's definition of done and section 25 of the guide itself
   both require WCAG AA. Where a colour pairing in the guide fails AA, the colour
   changes, not the threshold. Three pairings fail; see below.
2. **The frozen contract.** No token, ornament or layout in the guide justifies a
   change to `contracts/`.
3. **Rule 7.** See *Seals and crests*.

Below that, the guide wins over existing implementation — including over token
values I chose in S0.

### What the palette becomes

The existing themes keep their names and their jobs, re-pigmented onto the guide's
palette. `parchment` stays the **light, outdoor, daylight** theme and `greenhouse`
becomes the guide's candlelit dark theme, built on Midnight Ink and Forest Green.

The guide's §13 makes deep midnight the *primary page*. Morning Rounds is used
outdoors in direct sun with one hand — a midnight-default app is the wrong default
for the one screen that matters most in daylight. So: both themes carry the full
guide palette, the device preference picks between them, and neither is treated as
the "real" one. The 60/25/10/5 distribution holds **within** each theme.

| `--moh-*` token | parchment (light) | greenhouse (dark) | Guide name |
| --- | --- | --- | --- |
| `--moh-surface` | `#E8DCC2` | `#111722` | Aged Parchment / Midnight Ink |
| `--moh-surface-raised` | `#F4EDDA` | `#19382F` | Warm Ivory / Forest Green |
| `--moh-surface-sunken` | `#DCCFB0` | `#0B0F17` | darkened parchment / deeper ink |
| `--moh-selected` | `#DFE3D2` | `#202C45` | sage-tinted / Midnight Blue |
| `--moh-border` | `#877241` | `#B89A5A` | aged brass / Antique Gold |
| `--moh-ink` | `#111722` | `#F4EDDA` | Midnight Ink / Warm Ivory |
| `--moh-accent` | `#19382F` | `#B89A5A` | Forest Green / Antique Gold |
| `--moh-danger` | `#5A242D` | `#C4636B` | Burgundy / lightened burgundy |
| `--moh-frost` | `#202C45` | `#9DBBE6` | Midnight Blue |
| `--moh-sage` (new) | `#57634E` | `#8FA481` | Muted Sage, adjusted |

The status ramp (`parched`, `sated`, `frost`, `thriving`, `ailing`) stays five
distinct colours. §2 says avoid rainbow palettes, and §25 says never convey
information by colour alone: the second rule is why the first is safe here. Every
`StatusPill` already carries words — "Water today", "Rain covered it" — so the
colours are reinforcement, not the signal, and they re-pigment toward the guide's
greens, blues and burgundy rather than disappearing.

### The three pairings that fail AA

Measured with the same WCAG formula `web/src/lib/ui/contrast.test.ts` uses:

| Pairing | Ratio | Verdict |
| --- | --- | --- |
| Antique Gold `#B89A5A` on Aged Parchment | **1.98** | fails everything |
| Antique Gold `#B89A5A` on Warm Ivory | **2.30** | fails everything |
| Muted Sage `#66755C` on Aged Parchment | **3.62** | fails AA body text |
| Muted Sage `#66755C` on Midnight Ink | **3.65** | fails AA body text |

§6 asks for gold rules and borders and §3 for gold section headings. On a dark
surface that is fine — gold reaches 6.68 on Midnight Ink, 5.18 on Midnight Blue and
4.74 on Forest Green, all passing. **On the light surfaces it is unusable for
anything that carries meaning.** So the light theme gets two derived brasses, both
still aged rather than yellow:

| Derived token | Value | On parchment | On ivory | Use |
| --- | --- | --- | --- | --- |
| `--moh-gold-line` | `#877241` | 3.42 | 3.98 | borders, rules, focus rings (≥3:1) |
| `--moh-gold-ink` | `#6E5C36` | 4.76 | 5.53 | gold *text*, section headings (≥4.5:1) |
| `--moh-sage-ink` | `#57634E` | 4.68 | 5.45 | sage text on light |
| `--moh-sage` (dark) | `#8FA481` | 6.67 on ink | 5.17 on midnight | sage text on dark |

`#877241` is what `--moh-border` already is. The brass line the guide asks for was,
by coincidence, already in the tokens at the right darkness.

Full-strength `#B89A5A` remains available on light surfaces for **decoration that
carries no meaning** — a corner flourish, a divider, the inner line of a double
border — because §25's rule is about information, not ornament. A gold hairline may
never be the *only* indicator of focus, selection or state on a light surface.

### Typography

The guide names three faces. The app currently ships **zero** downloaded fonts: the
display stack starts at IM Fell English (one of the guide's own suggestions) and
falls back through system serifs, and there is no utility sans at all — metadata is
set in the body serif.

- **Display and body** keep the system-first stacks, with IM Fell English and EB
  Garamond named first. A self-hosted, subset Cormorant Garamond may be added later
  if the maintainer accepts the payload; it is not adopted here. This is a PWA that
  must work offline in a garden with no signal, and a webfont that fails to load is
  worse than a system serif that never had to.
- **The utility sans is adopted** as a new `--moh-font-ui`, as a system stack
  (`system-ui`, `-apple-system`, `Segoe UI`, …) rather than Inter or Source Sans 3
  over the network. §3 wants it for metadata, dates, form labels and system
  messages, and those are exactly the strings currently fighting the serif.
- Metadata gets §3's treatment: small, uppercase, wide tracking.

### Motion

The guide's `--transition-magic: 500ms cubic-bezier(.22, 1, .36, 1)` is adopted as a
token, and the curve replaces the current easing everywhere. **The 400–700 ms
duration is adopted only for atmospheric motion** — Journal page turns, plate
reveals, hero illumination, star and candle variation. Interactive feedback (a
checkbox taking a tap, a sheet opening, a row committing) stays at the existing 140
ms / 240 ms. Half a second of ceremony between tapping "watered" and seeing it is
ceremony charged to someone standing in the rain.

§18's "nothing should bounce aggressively" and §25's reduced-motion rules are
already how `tokens.css` behaves; the existing `prefers-reduced-motion` block
satisfies them and stays.

### Shape and shadow

`--moh-radius` moves 6px → 4px and `--moh-radius-lg` 12px → 6px, inside §13's 2–6px
band. Pill shapes are out. Shadows adopt §12's two values. The 44 px minimum tap
target and the 56 px list row **do not move** — §13's "small radius" is about shape,
not size, and §24 says decoration is what gets removed on small screens, not
usability.

### Seals and crests

Rule 7 in `CLAUDE.md` says: no crests, house names, film typefaces, character names
or other franchise IP. §§22–23 of the guide describe an original seal and crest
system and are explicit about avoiding recognisable heraldry — the intent matches,
but the literal texts collide.

The reading adopted here: **rule 7 forbids franchise crests, not the concept of a
mark.** The guide's own prohibitions (no recognisable fictional symbols, no obvious
franchise references, §27) are strictly narrower than rule 7 and are kept. Pending
the maintainer's answer in *Open questions*, no crest is drawn and no seal ships.
The wax-seal motif of §22 is permitted **only** as a decorative flourish carrying no
institutional identity — a divider ornament, a chapter marker — and never a shield,
never house colours, never a motto in a dead language chosen to imply one.

### Illustration and the Journal

§§9 and 30 describe exactly what Workstream K already builds: engraved,
hand-coloured field-guide plates. §30's master prompt becomes K's art-direction
prompt for the **fallback** path only. The ordering in ADR 0007 does not change: a
sourced public-domain plate first, generation only when none exists, and the
generated plate labelled as generated. A plate is an illustration, not evidence —
rule 6 is untouched by this ADR, and no illustration may imply a care fact that no
citation supports.

## Consequences

**Workstream I** re-pigments `tokens.css` onto the table above, adds
`--moh-font-ui`, `--moh-gold-line`, `--moh-gold-ink`, `--moh-sage`, the two shadow
tokens and the motion curve, and extends `contrast.test.ts` to cover every new pair
— including the two that must be asserted as *decoration only*. This is the largest
single change to the design system since S0 and is S4 work, not S3: it lands after
E's Almanac endpoints, and it is sequenced before J builds `/register`, `/grounds`,
`/almanac` and `/office` so those screens are built once.

**Workstream K** adopts §30 for the fallback plate prompt and §9 for the style
guide it already maintains.

**Workstream J** builds the four unbuilt routes against the new tokens, not the old
ones.

**Nothing in `contracts/` changes.** No migration, no OpenAPI edit, no fixture
change. The `x-workstream` tags, `care_value_uncited_is_unknown` and the
`plain_title` pairing are all untouched: a theme cannot make an uncited value look
cited, and §7's plain-language pairing survives intact because it is a database
constraint, not a style choice.

The mockup at `https://claude.ai/artifact/S8o83sphAMe61NkSqmZW7c` now shows the
*previous* palette. It is a record of the 21 September state and is not retrofitted.

## Open questions for the maintainer

1. **An original seal — yes or no?** The guide devotes two sections to one; rule 7's
   text forbids crests outright. If yes, rule 7's wording is amended by a follow-up
   ADR to "no franchise crests or house iconography", and one mark is drawn from
   original geometry (a lantern, an oak leaf, a compass) for the app icon, the
   splash screen and printed labels. If no, rule 7 stands unchanged and §§22–23
   apply to print only.
2. **Downloaded display font?** Self-hosting a subset Cormorant Garamond costs
   roughly 30–60 KB and gives the guide's exact display voice; the system stack
   costs nothing and is already installed on most devices. Offline-first argues for
   the system stack.
3. **Which theme is the default for a first-time visitor?** The guide implies
   midnight. The app's most-used screen is used outdoors in daylight. Current
   behaviour — follow the device preference, remember the choice — is the
   recommendation, and it means neither theme is privileged.

## References

- `docs/design/style-guide.md` — the guide itself
- ADR 0005 — theme without franchise assets
- ADR 0007 — free sources only (plate sourcing order)
- `web/src/lib/ui/contrast.test.ts` — where the AA thresholds are enforced
