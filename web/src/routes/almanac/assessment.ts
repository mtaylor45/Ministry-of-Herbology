/** Showing how much the weather engine's answers are worth.
 *
 * Under ADR 0010 nothing in the house measures the soil, and the engines
 * beneath the Almanac are the only authority on whether a plant is dry or
 * about to freeze. Their worst failure is not being wrong — it is losing an
 * input and going on answering in the same confident voice, because an app that
 * has gone quiet looks exactly like a garden that needs nothing.
 *
 * Workstream E's half of that is `workers/weather/quality.py`: every answer
 * carries `confidence`, `degraded` and a list of `degradations`, each a named
 * reason with a finished sentence in it. This module is J's half — the caveat
 * goes **next to the number**, in the sentence E wrote, not behind a tooltip and
 * not in a colour.
 */

import type { Assessment, Confidence, Degradation } from './api';
import type { Status } from '$ui/status';

/** Best to worst — ADR 0004 allows exactly these four. */
export const CONFIDENCE_ORDER: Confidence[] = ['high', 'medium', 'low', 'unknown'];

export function rank(confidence: Confidence | undefined): number {
  const at = CONFIDENCE_ORDER.indexOf(confidence as Confidence);
  return at === -1 ? CONFIDENCE_ORDER.length - 1 : at;
}

/**
 * How much a *measurement or model* is worth, as a pill.
 *
 * Deliberately not `confidenceStatus` from the Specimen page: that vocabulary
 * ("Unattested — no source for this") is about whether a plant fact was cited,
 * and a forecast whose ET₀ went missing is not an uncited claim, it is a
 * measured one with a hole in it. Same four levels, different sentence.
 */
export function measurementConfidence(confidence: Confidence | undefined): Status {
  switch (confidence) {
    case 'high':
      return { themed: 'Read clearly', plain: 'High confidence', tone: 'thriving' };
    case 'medium':
      return { themed: 'Read through cloud', plain: 'Medium confidence', tone: 'sated' };
    case 'low':
      return { themed: 'Read poorly', plain: 'Low confidence — check it', tone: 'parched' };
    case 'unknown':
      return { themed: 'Unreadable', plain: 'Confidence unknown', tone: 'ailing' };
    default:
      return {
        themed: 'Not stated',
        plain: 'This reading does not say how sure it is',
        tone: 'parched',
      };
  }
}

/** The ceiling one degradation puts on an answer, said plainly. */
export function capSentence(degradation: Degradation): string {
  const level = measurementConfidence(degradation.caps_at).plain.replace(/ —.*$/, '');
  return `Caps this answer at: ${level.toLowerCase()}.`;
}

/**
 * Does this payload report its own confidence at all?
 *
 * **The seam.** ADR 0018 requires the assessment block on `WaterBalance` and
 * `FrostAlert`. `/almanac/forecast` and `/almanac/history` — the two endpoints
 * these screens read — are not covered by it and carry nothing. A screen that
 * shows nothing in that case
 * is a screen claiming the forecast is clean, which is the exact failure the
 * engine's confidence arithmetic was built to prevent — so when the block is
 * absent the Almanac says so once, plainly, instead of showing a reassuring
 * blank. When E adds the fields, every caveat below appears with no change
 * here beyond deleting the notice.
 */
export function reportsItsOwnConfidence(payload: Assessment | null | undefined): boolean {
  if (!payload) return false;
  return payload.confidence !== undefined || payload.degraded !== undefined;
}

/** The caveats to show, worst ceiling first. Empty is empty: a clean answer
 *  gets no decoration, so a caveat line means something on the day it appears. */
export function caveats(payload: Assessment | null | undefined): Degradation[] {
  const found = payload?.degradations ?? [];
  return [...found].sort((a, b) => rank(b.caps_at) - rank(a.caps_at));
}

export function isDegraded(payload: Assessment | null | undefined): boolean {
  return Boolean(payload?.degraded) || caveats(payload).length > 0;
}

/** One line summarising a degraded panel, for the screen-reader summary and for
 *  the collapsed state. The detail sentences are never folded into it — they
 *  are E's wording and they are shown in full. */
export function caveatSummary(payload: Assessment | null | undefined): string {
  const found = caveats(payload);
  if (!found.length) return '';
  const count = `${found.length} reason${found.length === 1 ? '' : 's'}`;
  return `${count} this may be wrong`;
}

/** The weakest confidence of several panels — what a screen built of them is
 *  worth as a whole, since a chain is worth its weakest link. */
export function weakest(...payloads: (Assessment | null | undefined)[]): Confidence | undefined {
  const stated = payloads.filter(reportsItsOwnConfidence).map((p) => p?.confidence);
  if (!stated.length) return undefined;
  return CONFIDENCE_ORDER[Math.max(...stated.map((c) => rank(c)))];
}
