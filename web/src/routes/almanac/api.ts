/** What the Almanac reads, typed against the frozen contract.
 *
 * `contracts/openapi/openapi.yaml` is the authority: where it and this file
 * disagree, this file is the bug. Three fields below are *not* in the contract
 * and are marked as such — Workstream E serves them additively and has asked A
 * to add them (`docs/sprints/S3-workstream-e.md`, "For A"). They are optional
 * here, so the screen works whether or not they arrive, and the S3 pull request
 * repeats the request rather than reshaping anything client-side.
 */

import type { Confidence } from '$api/client';
import { get, type Fetcher } from '../shared/http';

export type { Confidence };
export { ApiError, reason, settle, type Fetched, type Fetcher } from '../shared/http';

/** One named reason an answer is worth less than a clean measurement.
 *
 *  `detail` is a finished sentence, written by the engine to be shown to a
 *  reader as it stands. It is never summarised, truncated or reworded here:
 *  the wording is E's half of the contract with whoever is holding the phone. */
export interface Degradation {
  code: string;
  detail: string;
  caps_at: Confidence;
}

/** How sure an engine is, and why it is not surer.
 *
 *  Not in the contract yet. `/almanac/water-balance` and `/almanac/frost`
 *  already carry it; `/almanac/forecast` and `/almanac/history` do not carry it
 *  at all, which is the gap this screen raises with A rather than papering
 *  over — see `reportsItsOwnConfidence` in `assessment.ts`. */
export interface Assessment {
  confidence?: Confidence;
  degraded?: boolean;
  degradations?: Degradation[];
}

/** `ForecastPoint`. Daily rows carry min/max; hourly rows carry `temperature_c`. */
export interface ForecastPoint extends Assessment {
  time: string;
  temperature_c?: number | null;
  temp_min_c?: number | null;
  temp_max_c?: number | null;
  precip_mm?: number | null;
  precip_prob_pct?: number | null;
  et0_mm?: number | null;
  wind_kph?: number | null;
  condition?: string | null;
  sunrise?: string | null;
  sunset?: string | null;
}

/** `Series` — column-oriented, handed straight to uPlot. */
export interface Series extends Assessment {
  metric: string;
  unit?: string;
  /** Unix seconds. */
  times: number[];
  values: (number | null)[];
  min?: (number | null)[];
  max?: (number | null)[];
  label?: string;
  /**
   * Which rollup answered: `weather_daily` is the site's own weather record,
   * `reading_daily` is sensor readings from indoors. Served by E, not in the
   * contract. The Almanac needs it to tell an indoor series apart from an
   * outdoor one that was returned in its place — see `history.ts`.
   */
  source?: string;
}

/** As much of `Location` as the Almanac needs: somewhere to read a site id, and
 *  the indoor/outdoor split the history comparison is built on. */
export interface AlmanacLocation {
  id: string;
  name: string;
  kind: string;
  is_outdoor: boolean;
  site_id?: string;
}

export type Horizon = 'hourly' | 'daily';
export type HistoryWindow = '1d' | '7d' | '30d';
export type Metric =
  'temperature_c' | 'humidity_pct' | 'soil_moisture_pct' | 'precip_mm' | 'et0_mm';

export interface HistoryQuery {
  window: HistoryWindow;
  metric: Metric;
  siteId?: string;
  locationId?: string;
  specimenId?: string;
}

function query(pairs: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(pairs)) if (value) search.set(key, value);
  return search.toString();
}

export const reads = {
  locations: (f: Fetcher) => get<AlmanacLocation[]>('/locations', f),

  forecast: (siteId: string, horizon: Horizon, f: Fetcher) =>
    get<ForecastPoint[]>(`/almanac/forecast?${query({ site_id: siteId, horizon })}`, f),

  history: (q: HistoryQuery, f: Fetcher) =>
    get<Series>(
      `/almanac/history?${query({
        window: q.window,
        metric: q.metric,
        site_id: q.siteId,
        location_id: q.locationId,
        specimen_id: q.specimenId,
      })}`,
      f,
    ),
};

/** Which site the Almanac is about.
 *
 * `GET /almanac/forecast` requires a `site_id` and the contract has no endpoint
 * that lists sites, so the only place a client can learn one is the `site_id`
 * carried on a location. That is a derivation, not a design: the S3 pull
 * request asks A for `GET /sites` (or a site on the Office settings payload).
 * Until then this is where the workaround lives, in one function, named.
 */
export function siteIdFrom(locations: AlmanacLocation[]): string | null {
  return locations.find((location) => Boolean(location.site_id))?.site_id ?? null;
}

/** The indoor location whose readings are worth putting beside the weather.
 *
 * "Indoor" is a property of the location, and the one with a sensor in it is
 * not knowable from `/locations` — Workstream F's readings are not wired up
 * (ADR 0010). The first indoor room is a stand-in the reader can change once
 * there is anything to choose between; `history.ts` says on screen which room
 * the line is, so it is never mistaken for the house as a whole.
 */
export function indoorLocations(locations: AlmanacLocation[]): AlmanacLocation[] {
  return locations.filter((location) => !location.is_outdoor);
}
