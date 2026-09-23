# 17. The Enchanted Academy style guide is the project's visual reference

Date: 2026-09-23

## Status

Accepted. The three questions this ADR originally left open were answered by the
maintainer on 2026-09-23 and are recorded in *The three questions, answered* below.
Rule 7 in `CLAUDE.md` is amended by this ADR as a consequence of the first answer.

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

- **The display face is self-hosted Cormorant Garamond**, subset to the Latin
  characters the app actually sets, `woff2`, served from `web/static/fonts/` by the
  app's own origin. Never a Google Fonts URL: this is a self-hosted app that must
  work in a garden with no signal, and a third-party font CDN is both an offline
  failure and a request to someone else's server on every load.
- Every `@font-face` carries `font-display: swap` and keeps the full system serif
  stack behind it, so a font that fails to arrive costs a different shape, never a
  blank heading. The service worker precaches the files; the app is usable before
  they land.
- **Body text keeps the system-first serif stack.** The display face is a few dozen
  headings; body text is every screen, and the system serif is already installed,
  already hinted for the device, and costs nothing. EB Garamond is named first in
  the stack for anyone who has it.
- **The utility sans is adopted** as a new `--moh-font-ui`, as a system stack
  (`system-ui`, `-apple-system`, `Segoe UI`, …) rather than Inter or Source Sans 3
  over the network. §3 wants it for metadata, dates, form labels and system
  messages, and those are exactly the strings currently fighting the serif.
- Metadata gets §3's treatment: small, uppercase, wide tracking.
- **Licensing is checked at vendoring time, not assumed.** Cormorant Garamond, EB
  Garamond and IM Fell English are each distributed under the SIL Open Font
  Licence; whoever vendors the files confirms that against the release they
  actually download, and commits the licence text beside the fonts. A font whose
  licence cannot be confirmed does not ship.

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
mark.** The maintainer has confirmed it: one original seal is permitted, it may be
*reminiscent* of the wizarding-academia genre, and it must use no copyrighted or
trademarked design. Rule 7's wording is amended to say so.

The genre is not the property of any rights holder — an oak leaf, a lantern, a
circular inscription and a wax seal are centuries older than any film. Specific
marks are. So the boundary this project works to:

**Permitted** — original geometry built from the guide's §22 motifs: a lantern, an
oak or laurel leaf, a compass, a moon phase, a quill, a key, a seed head, a
botanical specimen; a circular inscription in the app's own words; a wax-seal
silhouette; period-appropriate engraving and heraldic *symmetry*.

**Never** — any existing school, house or institutional crest or its arrangement;
any franchise's emblem, sigil, monogram or logotype; the name or initials of a
fictional institution or its founders; house names, house animals, house colours as
a set, or a four-part shield that stands in for them; a motto lifted from, or
composed to evoke, a specific fictional one; any film or game typeface; any mark
close enough that someone would recognise *which* story it came from.

The test is simple and it is the one to apply when drawing: a reader should think
"an old botanical institution", never "that's from —". If a motif only reads as
magical *because* it quotes something, it fails.

The seal is one mark, used sparingly per §22 — app icon, splash screen, printed
labels, the Journal's colophon — and it carries authority and authenticity rather
than decoration. It is drawn as original vector work, not generated, so its
provenance is known.

### Illustration and the Journal

§§9 and 30 describe exactly what Workstream K already builds: engraved,
hand-coloured field-guide plates. §30's master prompt becomes K's art-direction
prompt for the **fallback** path only. The ordering in ADR 0007 does not change: a
sourced public-domain plate first, generation only when none exists, and the
generated plate labelled as generated. A plate is an illustration, not evidence —
rule 6 is untouched by this ADR, and no illustration may imply a care fact that no
citation supports.

## Consequences

**Workstream I** carries most of this, as S4 work rather than S3 — it lands after
E's Almanac endpoints and is sequenced before J builds `/register`, `/grounds`,
`/almanac` and `/office`, so those screens are built once:

- re-pigment `tokens.css` onto the table above; add `--moh-font-ui`,
  `--moh-gold-line`, `--moh-gold-ink`, `--moh-sage`, the two shadow tokens and the
  motion curve;
- extend `contrast.test.ts` to every new pair, including the two that must be
  asserted as *decoration only* — a gold hairline may never be the sole indicator of
  focus or state on a light surface, and the test is where that is enforced;
- vendor the subset Cormorant Garamond `woff2` into `web/static/fonts/` with its
  licence text, wire the `@font-face` with `font-display: swap`, and add the files
  to the service worker's precache;
- make `parchment` the default: delete the `@media (prefers-color-scheme: dark)`
  block, and adjust the `contrast.test.ts` assertion that currently requires that
  block to match `greenhouse` token for token — that test exists and will fail
  otherwise;
- draw the seal as original vector work within the boundary in *Seals and crests*,
  and use it for the app icon and splash screen.

This is the largest single change to the design system since S0. The seal in
particular is a judgement call about someone else's intellectual property: when a
motif is arguable, it does not ship, and A reviews the mark before it lands.

**Workstream K** adopts §30 for the fallback plate prompt and §9 for the style
guide it already maintains, and may use the seal in the Journal's colophon.

**Workstream J** builds the four unbuilt routes against the new tokens, not the old
ones.

**Nothing in `contracts/` changes.** No migration, no OpenAPI edit, no fixture
change. The `x-workstream` tags, `care_value_uncited_is_unknown` and the
`plain_title` pairing are all untouched: a theme cannot make an uncited value look
cited, and §7's plain-language pairing survives intact because it is a database
constraint, not a style choice.

The mockup at `https://claude.ai/artifact/S8o83sphAMe61NkSqmZW7c` now shows the
*previous* palette. It is a record of the 21 September state and is not retrofitted.

## The three questions, answered

Answered by the maintainer, 2026-09-23.

1. **An original seal is permitted.** It may be reminiscent of wizarding-academia
   design, and must use no copyrighted or trademarked design. Rule 7 in `CLAUDE.md`
   is amended by this ADR from a blanket "no crests" to "no franchise crests, house
   iconography or other franchise IP; one original Ministry seal is permitted". The
   permitted/never boundary is in *Seals and crests* above and is the operative
   text — a designer reads that section, not this line.
2. **A self-hosted display font is approved.** Cormorant Garamond, subset, `woff2`,
   served from the app's own origin with the system stack behind it. Details in
   *Typography* above.
3. **Light is the default theme.** A first-time visitor gets `parchment`,
   whatever their device's `prefers-color-scheme` says. This is a change in
   behaviour, not only in wording: the current `@media (prefers-color-scheme: dark)`
   block in `tokens.css` silently hands a dark-mode phone the dark theme, and that
   block goes. Dark remains one tap away in the theme switcher and the choice is
   remembered. Stated plainly because it has a cost: someone who keeps their phone
   in dark mode for comfort now gets a light app until they change it. If that turns
   out to be the wrong trade, restoring device-following is a one-block change and a
   superseding ADR.

## References

- `docs/design/style-guide.md` — the guide itself
- ADR 0005 — theme without franchise assets
- ADR 0007 — free sources only (plate sourcing order)
- `web/src/lib/ui/contrast.test.ts` — where the AA thresholds are enforced
