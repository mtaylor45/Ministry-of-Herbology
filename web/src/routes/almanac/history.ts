/** The conditions record: what it was, indoors against outdoors.
 *
 * The comparison is the point of this view — a study that sits ten degrees
 * warmer and far drier than the garden is why the same plant is watered on
 * different rounds in each. Which makes the honesty problem sharper than
 * usual: under ADR 0010 nothing in this house measures anything indoors yet,
 * and a screen that draws two lines when it has one set of numbers has lied
 * about the only thing the reader came here to compare.
 *
 * So the indoor series is checked before it is drawn, and when it is not really
 * indoor readings the screen says so in a sentence instead of plotting it.
 */

import type { HistoryWindow, Metric, Series } from './api';

export const METRICS: Record<Metric, { themed: string; plain: string; unit: string }> = {
  temperature_c: { themed: 'Warmth', plain: 'Temperature', unit: '°C' },
  humidity_pct: { themed: 'Humours of the air', plain: 'Humidity', unit: '%' },
  soil_moisture_pct: { themed: 'Damp in the soil', plain: 'Soil moisture', unit: '%' },
  precip_mm: { themed: 'Rainfall', plain: 'Rain', unit: 'mm' },
  et0_mm: { themed: 'Thirst of the air', plain: 'Evaporation (ET₀)', unit: 'mm' },
};

export const WINDOWS: Record<string, { themed: string; plain: string }> = {
  '1d': { themed: 'A day', plain: 'Last 24 hours' },
  '7d': { themed: 'A week', plain: 'Last 7 days' },
  '30d': { themed: 'A month', plain: 'Last 30 days' },
};

/** Metrics that only ever describe the site's weather. Asking for one of these
 *  by location is asking a question the rollups cannot answer — the indoor
 *  column comes from `reading_daily`, which Workstream F fills. */
export const OUTDOOR_ONLY: Metric[] = ['precip_mm', 'et0_mm'];

/** Metrics that only ever come from a sensor indoors. */
export const SENSOR_ONLY: Metric[] = ['soil_moisture_pct'];

export function hasAnyValue(series: Series | null | undefined): boolean {
  return Boolean(series?.values?.some((value) => value !== null && value !== undefined));
}

/**
 * Is this response actually the indoor record it was asked for?
 *
 * Two ways it is not, and both matter:
 *
 * - it came back empty, because no sensor has ever written a reading (ADR
 *   0010 — Workstream F's adapter is not wired to anything in this house);
 * - it came back from `weather_daily`, which is the *site's outdoor weather*.
 *   The mock answers a location query with site weather today, and a line
 *   labelled "the Study" that is really the garden is the worst outcome this
 *   screen has: it invents an indoor climate and invites somebody to water on
 *   it.
 *
 * `source` is served by E and is not in the contract (S3 notes, "For A"), so
 * the empty check stands on its own if the field ever goes away.
 */
export function indoorIsReal(series: Series | null | undefined): boolean {
  if (!hasAnyValue(series)) return false;
  return series?.source !== 'weather_daily';
}

/** Why the indoor line is missing, in a sentence that names the reason rather
 *  than shrugging. Returns null when there is nothing to explain. */
export function indoorGap(series: Series | null | undefined, metric: Metric): string | null {
  if (indoorIsReal(series)) return null;
  if (SENSOR_ONLY.includes(metric)) {
    return (
      'Nothing measures soil moisture in this house. ADR 0010 makes the modelled ' +
      'water balance the shipping path, so there is no sensor record to compare ' +
      'against — and no figure has been estimated to fill the gap.'
    );
  }
  if (series?.source === 'weather_daily') {
    return (
      'The API answered this indoor question with the site’s outdoor weather, so ' +
      'there is nothing here that describes indoors. It is shown as one line, not ' +
      'two, rather than drawing the garden twice and calling half of it a room.'
    );
  }
  return (
    'No indoor readings have been stored yet. The sensor adapter has nothing ' +
    'connected to it in this house, so the record indoors is genuinely empty ' +
    'rather than hidden.'
  );
}

/** Metrics worth offering for a given place. Offering soil moisture for the
 *  site, or rainfall for a bedroom, is offering a question with no answer. */
export function metricsFor(place: 'site' | 'indoor'): Metric[] {
  const all = Object.keys(METRICS) as Metric[];
  return all.filter((metric) =>
    place === 'site' ? !SENSOR_ONLY.includes(metric) : !OUTDOOR_ONLY.includes(metric),
  );
}

export interface AlignedRow {
  at: number;
  outdoor: number | null;
  indoor: number | null;
  low: number | null;
  high: number | null;
}

/**
 * The two series on one timeline.
 *
 * Buckets are daily on both sides, but the two need not cover the same days —
 * a sensor fitted last Tuesday has nothing to say about last Monday. The union
 * of the timestamps keeps both honest: a gap stays a gap instead of sliding a
 * value onto the wrong day.
 */
export function align(outdoor: Series | null, indoor: Series | null): AlignedRow[] {
  const times = new Set<number>();
  for (const series of [outdoor, indoor]) for (const at of series?.times ?? []) times.add(at);

  const at = (series: Series | null, moment: number, column: 'values' | 'min' | 'max') => {
    if (!series) return null;
    const index = series.times.indexOf(moment);
    if (index === -1) return null;
    return series[column]?.[index] ?? null;
  };

  return [...times]
    .sort((a, b) => a - b)
    .map((moment) => ({
      at: moment,
      outdoor: at(outdoor, moment, 'values'),
      indoor: at(indoor, moment, 'values'),
      low: at(outdoor, moment, 'min'),
      high: at(outdoor, moment, 'max'),
    }));
}

/** uPlot wants columns: `[xs, ...ys]`, x in unix seconds. */
export function columns(rows: AlignedRow[], withIndoor: boolean): (number | null)[][] {
  const xs = rows.map((row) => row.at);
  const data: (number | null)[][] = [xs, rows.map((row) => row.outdoor)];
  if (withIndoor) data.push(rows.map((row) => row.indoor));
  return data;
}

/** The plain summary a reader gets without reading the chart: the range, and
 *  the difference between inside and out where there is one. */
export function summary(rows: AlignedRow[], metric: Metric, withIndoor: boolean): string {
  const unit = METRICS[metric].unit;
  const outdoor = rows.map((row) => row.outdoor).filter(isNumber);
  if (!outdoor.length) return 'Nothing has been recorded for this period.';

  const low = Math.round(Math.min(...outdoor) * 10) / 10;
  const high = Math.round(Math.max(...outdoor) * 10) / 10;
  const parts = [`Outdoors ranged from ${low} ${unit} to ${high} ${unit}`];

  if (withIndoor) {
    const indoor = rows.map((row) => row.indoor).filter(isNumber);
    if (indoor.length) {
      const inLow = Math.round(Math.min(...indoor) * 10) / 10;
      const inHigh = Math.round(Math.max(...indoor) * 10) / 10;
      parts.push(`indoors from ${inLow} ${unit} to ${inHigh} ${unit}`);
    }
  }
  return `${parts.join(', ')}.`;
}

/** The date a bucket is about, for the table beside the chart. */
export function bucketLabel(at: number, locale?: string): string {
  const date = new Date(at * 1000);
  if (Number.isNaN(date.getTime())) return String(at);
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(date);
}

function isNumber(value: number | null): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** A window or metric asked for in the URL, or the sensible default. The three
 *  views are linkable, so the query string is input from outside and is treated
 *  as such: anything unrecognised falls back rather than reaching the API. */
export function parseWindow(value: string | null): HistoryWindow {
  return value === '1d' || value === '7d' || value === '30d' ? value : '7d';
}

export function parseMetric(value: string | null): Metric {
  return value !== null && value in METRICS ? (value as Metric) : 'temperature_c';
}
