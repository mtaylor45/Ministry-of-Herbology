/** WCAG AA contrast, checked against the tokens themselves.
 *
 * Definition of done says the UI meets WCAG AA. A token is the one place a
 * contrast regression can enter for every screen at once, so it is the one
 * place worth testing exhaustively. Workstream I.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const css = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8');

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

const PARCHMENT = tokens(":root[data-theme='parchment']");
const GREENHOUSE = tokens(":root[data-theme='greenhouse']");

const THEMES: [string, Record<string, string>][] = [
  ['parchment', PARCHMENT],
  ['greenhouse', GREENHOUSE],
];

/** Body text: AA is 4.5:1. */
const BODY_PAIRS: [string, string][] = [
  ['--moh-ink', '--moh-surface'],
  ['--moh-ink', '--moh-surface-raised'],
  ['--moh-ink', '--moh-surface-sunken'],
  ['--moh-ink-muted', '--moh-surface'],
  ['--moh-ink-muted', '--moh-surface-raised'],
  ['--moh-accent-ink', '--moh-accent'],
  ['--moh-parched', '--moh-surface-raised'],
  ['--moh-sated', '--moh-surface-raised'],
  ['--moh-frost', '--moh-surface-raised'],
  ['--moh-thriving', '--moh-surface-raised'],
  ['--moh-ailing', '--moh-surface-raised'],
];

/** Non-text: borders and focus rings need 3:1 against what they sit on. */
const NON_TEXT_PAIRS: [string, string][] = [
  ['--moh-border', '--moh-surface'],
  ['--moh-border', '--moh-surface-raised'],
  ['--moh-accent', '--moh-surface'],
  ['--moh-accent', '--moh-surface-raised'],
];

describe.each(THEMES)('%s theme', (name, theme) => {
  it.each(BODY_PAIRS)('%s on %s meets AA for body text', (ink, surface) => {
    expect(theme[ink], `${name} is missing ${ink}`).toBeDefined();
    expect(theme[surface], `${name} is missing ${surface}`).toBeDefined();
    expect(ratio(theme[ink], theme[surface])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(NON_TEXT_PAIRS)('%s on %s meets AA for non-text', (fg, bg) => {
    expect(ratio(theme[fg], theme[bg])).toBeGreaterThanOrEqual(3);
  });

  it('defines every token the light theme defines', () => {
    const missing = Object.keys(PARCHMENT).filter(
      (key) =>
        !(key in theme) &&
        key.startsWith('--moh-') &&
        !key.includes('font') &&
        !key.includes('space') &&
        !key.includes('text') &&
        !key.includes('radius') &&
        !key.includes('shadow') &&
        key !== '--moh-tap',
    );
    expect(missing).toEqual([]);
  });
});
