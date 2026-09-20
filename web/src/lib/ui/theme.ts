/** Theme choice: parchment, greenhouse, or whatever the device prefers.
 *
 * Both themes are first-class. The choice is stored under one key that
 * `web/src/app.html` also reads, before first paint, so the app never flashes
 * the wrong theme at someone standing in a dark greenhouse at 6am.
 */

import type { Paired } from './pairing';

export const THEMES = ['parchment', 'greenhouse'] as const;
export type ThemeName = (typeof THEMES)[number];
export type ThemeChoice = ThemeName | 'system';

/** Read by app.html too — change both or neither. */
export const THEME_STORAGE_KEY = 'moh-theme';

/** Kept equal to `--moh-surface` in tokens.css; contrast.test.ts asserts it. */
export const THEME_COLORS: Record<ThemeName, string> = {
  parchment: '#f4ecd8',
  greenhouse: '#141a15'
};

export const THEME_OPTIONS: (Paired & { choice: ThemeChoice })[] = [
  { choice: 'parchment', themed: 'Parchment', plain: 'Light' },
  { choice: 'greenhouse', themed: 'Night greenhouse', plain: 'Dark' },
  { choice: 'system', themed: 'As the day decides', plain: 'Match my device' }
];

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === 'system' || (typeof value === 'string' && (THEMES as readonly string[]).includes(value));
}

/** The theme a choice actually resolves to right now. */
export function resolveTheme(choice: ThemeChoice, prefersDark: boolean): ThemeName {
  if (choice === 'system') return prefersDark ? 'greenhouse' : 'parchment';
  return choice;
}

/** What we stored last time, or `system` if it is missing or nonsense. */
export function readThemeChoice(storage?: Pick<Storage, 'getItem'> | null): ThemeChoice {
  try {
    const stored = storage?.getItem(THEME_STORAGE_KEY);
    return isThemeChoice(stored) ? stored : 'system';
  } catch {
    return 'system'; // private mode, blocked storage — a theme is not worth a crash
  }
}

/** The document bits `applyTheme` touches. Real DOM satisfies it; so do stubs. */
export interface ThemeTarget {
  root: { dataset: Record<string, string>; style?: { colorScheme?: string } };
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null;
  prefersDark: boolean;
  /** The `<meta name="theme-color">` element, when there is one. */
  meta?: { setAttribute(name: string, value: string): void } | null;
}

/** Put the choice on the document and remember it. Returns what it resolved to. */
export function applyTheme(choice: ThemeChoice, target: ThemeTarget): ThemeName {
  const theme = resolveTheme(choice, target.prefersDark);
  target.root.dataset.theme = theme;
  if (target.root.style) target.root.style.colorScheme = theme === 'greenhouse' ? 'dark' : 'light';
  target.meta?.setAttribute('content', THEME_COLORS[theme]);
  try {
    target.storage?.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // ignore: the theme still applies for this session
  }
  return theme;
}

/** Browser-side convenience used by ThemeSwitcher. */
export function applyThemeToDocument(choice: ThemeChoice): ThemeName | null {
  if (typeof document === 'undefined') return null;
  return applyTheme(choice, {
    root: document.documentElement as unknown as ThemeTarget['root'],
    storage: typeof localStorage === 'undefined' ? null : localStorage,
    prefersDark:
      typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches,
    meta: document.querySelector('meta[name="theme-color"]')
  });
}
