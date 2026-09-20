/** WCAG AA contrast, checked against the tokens themselves.
 *
 * Definition of done says the UI meets WCAG AA. A token is the one place a
 * contrast regression can enter for every screen at once, so it is the one
 * place worth testing exhaustively. Workstream I.
 *
 * S1 added the surfaces and colours the component library needs (fields,
 * selected rows, destructive actions) and the pairs that go with them. The rule
 * has not moved: if a colour fails here, the colour changes, not the threshold.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { THEME_COLORS, THEME_STORAGE_KEY, THEMES } from './theme';

const css = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8');
const appHtml = readFileSync(fileURLToPath(new URL('../../app.html', import.meta.url)), 'utf8');

/** Read one theme's token block. */
function tokens(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`no block for ${selector}`);
  const block = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start));
  const found: Record<string, string> = {};
  for (const line of block.split('\n')) {
    const match = /^\s*(--moh-[\w-]+):\s*([^;]+);/.exec(line);
    if (match) found[match[1]] = match[2].trim();
  }
  return found;
}

function channel(value: number): number {
  const v = value / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const clean = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** A solid colour we can measure. `rgb(… / .55)` scrims are not one. */
function isOpaqueColour(value: string): boolean {
  return /^#[0-9a-f]{6}$/i.test(value);
}

const PARCHMENT = tokens("[data-theme='parchment']");
const GREENHOUSE = tokens("[data-theme='greenhouse']");
const DEVICE_DARK = tokens(":root:not([data-theme='parchment'])");

const THEME_TOKENS: [string, Record<string, string>][] = [
  ['parchment', PARCHMENT],
  ['greenhouse', GREENHOUSE],
];

/** Every surface a component in this library puts text on. */
const SURFACES = [
  '--moh-surface',
  '--moh-surface-raised',
  '--moh-surface-sunken',
  '--moh-field',
  '--moh-selected',
];

/** Body text: AA is 4.5:1. */
const BODY_PAIRS: [string, string][] = [
  ...SURFACES.flatMap((surface): [string, string][] => [
    ['--moh-ink', surface],
    ['--moh-ink-muted', surface],
  ]),
  // Ink on a filled control: buttons, the checkbox tick, the accent bar.
  ['--moh-accent-ink', '--moh-accent'],
  ['--moh-accent-ink', '--moh-accent-hover'],
  ['--moh-danger-ink', '--moh-danger'],
  ['--moh-danger-ink', '--moh-danger-hover'],
  // Status and error text, wherever a card or row puts it.
  ...[
    '--moh-parched',
    '--moh-sated',
    '--moh-frost',
    '--moh-thriving',
    '--moh-ailing',
    '--moh-danger',
  ].flatMap((tone): [string, string][] =>
    ['--moh-surface', '--moh-surface-raised', '--moh-surface-sunken', '--moh-selected'].map(
      (surface): [string, string] => [tone, surface],
    ),
  ),
];

/** Non-text: borders, focus rings and the filled parts of controls need 3:1. */
const NON_TEXT_PAIRS: [string, string][] = SURFACES.flatMap((surface): [string, string][] => [
  ['--moh-border', surface],
  ['--moh-accent', surface],
]);

describe.each(THEME_TOKENS)('%s theme', (name, theme) => {
  it.each(BODY_PAIRS)('%s on %s meets AA for body text', (ink, surface) => {
    expect(theme[ink], `${name} is missing ${ink}`).toBeDefined();
    expect(theme[surface], `${name} is missing ${surface}`).toBeDefined();
    expect(ratio(theme[ink], theme[surface])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(NON_TEXT_PAIRS)('%s on %s meets AA for non-text', (fg, bg) => {
    expect(ratio(theme[fg], theme[bg])).toBeGreaterThanOrEqual(3);
  });

  it('defines every colour the light theme defines', () => {
    // Type, spacing and motion tokens are theme-independent and live in the
    // shared block; every colour has to exist in both themes.
    const missing = Object.keys(PARCHMENT).filter(
      (key) => !(key in theme) && /^(#|rgb)/i.test(PARCHMENT[key]),
    );
    expect(missing).toEqual([]);
  });
});

describe('the device-preference block', () => {
  // The dark block under `prefers-color-scheme` is what someone who has never
  // opened the theme switcher sees. It is a copy of the greenhouse theme, and a
  // copy is exactly the kind of thing that drifts.
  it('matches the greenhouse theme token for token', () => {
    expect(DEVICE_DARK).toEqual(GREENHOUSE);
  });
});

describe('theme.ts and the tokens agree', () => {
  it('knows the same themes the stylesheet defines', () => {
    for (const theme of THEMES) {
      expect(css).toContain(`[data-theme='${theme}']`);
    }
  });

  it('carries the same theme-colour as each theme surface', () => {
    expect(THEME_COLORS.parchment).toBe(PARCHMENT['--moh-surface']);
    expect(THEME_COLORS.greenhouse).toBe(GREENHOUSE['--moh-surface']);
  });

  it('shares its storage key with the pre-paint script in app.html', () => {
    // app.html applies the theme before the first paint; if the key or the
    // theme names drift apart, the page flashes the wrong theme on load.
    expect(appHtml).toContain(THEME_STORAGE_KEY);
    for (const theme of THEMES) expect(appHtml).toContain(theme);
    expect(appHtml).toContain(THEME_COLORS.greenhouse);
  });
});

describe('the token set itself', () => {
  it('measures every colour it claims to check', () => {
    for (const [name, theme] of THEME_TOKENS) {
      for (const pair of [...BODY_PAIRS, ...NON_TEXT_PAIRS].flat()) {
        expect(isOpaqueColour(theme[pair]), `${name} ${pair} is not a solid colour`).toBe(true);
      }
    }
  });

  it('keeps a touch target no smaller than 44px', () => {
    expect(PARCHMENT['--moh-tap']).toBe('44px');
    expect(parseInt(PARCHMENT['--moh-row'], 10)).toBeGreaterThanOrEqual(44);
  });
});
