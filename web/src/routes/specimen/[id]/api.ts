/** The reads the Specimen page makes, typed against the frozen contract.
 *
 * `$api/client.ts` carries the shapes Morning Rounds needs and belongs to
 * neither J nor I, so the facets' own calls live here instead of being bolted
 * onto a file this workstream may not edit (rule 2). The types below are
 * `contracts/openapi/openapi.yaml` verbatim — where the contract and this file
 * disagree, the contract is right and this file is the bug.
 */

import type { Confidence, FrostAlert, FrostReport, Task } from '$api/client';

export type { Confidence, FrostAlert, FrostReport, Task };

export type SpecimenStatus =
  'thriving' | 'struggling' | 'dormant' | 'overwintering' | 'lost' | 'given_away' | 'archived';

export type EnrichmentState = 'pending' | 'running' | 'complete' | 'failed';

export interface SpeciesBriefRef {
  id: string;
  accepted_name: string;
  common_name: string | null;
  family: string | null;
}

export interface LocationRef {
  id: string;
  name: string;
  kind: string;
  is_outdoor: boolean;
  is_covered: boolean;
  sun_exposure: string | null;
  map_layer_id: string | null;
  specimen_count: number;
}

export interface SpecimenDetail {
  id: string;
  display_name: string;
  nickname: string | null;
  cultivar: string | null;
  species: SpeciesBriefRef | null;
  is_group: boolean;
  count: number;
  location: LocationRef | null;
  map_layer_id: string | null;
  pin_px: { x: number; y: number } | null;
  is_outdoor: boolean;
  in_container: boolean;
  container_litres: number | null;
  soil_note: string | null;
  acquired_on: string | null;
  provenance: string | null;
  status: SpecimenStatus;
  primary_photo_url: string | null;
  created_at: string | null;
}

export interface SourceRef {
  id: string;
  kind: string;
  title: string;
  url: string | null;
  license: string | null;
  retrieved_at: string | null;
}

export interface SpeciesDetail extends SpeciesBriefRef {
  common_names: string[];
  genus: string | null;
  native_range: string[];
  summary: string | null;
  light_label: string | null;
  water_k_c: number | null;
  water_interval_days: number | null;
  soil_ph_min: number | null;
  soil_ph_max: number | null;
  fertilizer_note: string | null;
  humidity_min_pct: number | null;
  min_temp_c: number | null;
  usda_zone_min: string | null;
  usda_zone_max: string | null;
  dormancy_months: number[];
  toxic_to_pets: boolean | null;
  toxic_to_children: boolean | null;
  toxicity_note: string | null;
  enrichment_state: EnrichmentState;
  sources: SourceRef[];
}

export interface CareValue {
  field: string;
  value: unknown;
  unit: string | null;
  source: SourceRef | null;
  confidence: Confidence;
  is_user_override: boolean;
  note: string | null;
}

export interface WaterBalance {
  specimen_id: string;
  deficit_mm: number;
  capacity_mm: number;
  threshold_mm: number;
  k_c: number;
  is_due: boolean;
  sensor_override_pct: number | null;
  days: {
    day: string;
    deficit_mm: number;
    et0_mm: number;
    precip_mm: number;
    irrigation_mm: number;
  }[];
}

export interface CareRule {
  id: string;
  species_id: string | null;
  specimen_id: string | null;
  task_type: string;
  strategy: 'interval' | 'water_balance' | 'frost_guard' | 'seasonal';
  base_interval_days: number | null;
  amount_ml: number | null;
  modifiers: Record<string, unknown>;
  months: number[];
  enabled: boolean;
}

export interface Photo {
  id: string;
  url: string;
  thumb_url: string | null;
  taken_at: string;
  caption: string | null;
  is_primary: boolean;
}

export interface LogEntry {
  id: string;
  kind: 'growth' | 'pest' | 'disease' | 'repot' | 'prune' | 'relocate' | 'note';
  occurred_at: string;
  body: string | null;
  photo: Photo | null;
  data: Record<string, unknown> | null;
}

/** A panel's data, or the plain reason it is missing. Never both, never neither.
 *
 *  A facet asks four or five endpoints for its panels. One of them failing must
 *  cost the reader that panel and nothing else — a blank Tending page because
 *  the frost lookahead timed out is worse than a page that says so. */
export type Fetched<T> = { value: T; error: null } | { value: null; error: string };

export const BASE = '/api/v1';

export type Fetcher = typeof fetch;

export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
    readonly statusText: string,
  ) {
    super(`${status} ${statusText} for ${path}`);
    this.name = 'ApiError';
  }
}

export async function get<T>(path: string, fetcher: Fetcher): Promise<T> {
  const response = await fetcher(`${BASE}${path}`, { headers: { accept: 'application/json' } });
  if (!response.ok) throw new ApiError(path, response.status, response.statusText);
  return (await response.json()) as T;
}

/** Run a read and keep its failure as a sentence rather than as an exception. */
export async function settle<T>(work: Promise<T>): Promise<Fetched<T>> {
  try {
    return { value: await work, error: null };
  } catch (cause) {
    return { value: null, error: reason(cause) };
  }
}

/** What went wrong, in words a person reads outdoors rather than a stack trace. */
export function reason(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 404) return 'The greenhouse has no record of this yet.';
    if (cause.status === 405 || cause.status === 501)
      return 'The API does not answer this yet — the screen is ready, the endpoint is not.';
    if (cause.status >= 500) return `The greenhouse answered with an error (${cause.status}).`;
    return `The greenhouse refused the request (${cause.status}).`;
  }
  if (cause instanceof Error) return cause.message;
  return 'Something went wrong, and it did not say what.';
}

export const reads = {
  specimen: (id: string, f: Fetcher) => get<SpecimenDetail>(`/specimens/${id}`, f),
  species: (id: string, f: Fetcher) => get<SpeciesDetail>(`/species/${id}`, f),
  careValues: (speciesId: string, f: Fetcher) =>
    get<CareValue[]>(`/species/${speciesId}/care-values`, f),
  photos: (id: string, f: Fetcher) => get<Photo[]>(`/specimens/${id}/photos`, f),
  log: (id: string, f: Fetcher) => get<LogEntry[]>(`/specimens/${id}/log`, f),
  tasks: (id: string, f: Fetcher) => get<Task[]>(`/tending/tasks?specimen_id=${id}`, f),
  careRules: (id: string, f: Fetcher) =>
    get<CareRule[]>(`/tending/care-rules?specimen_id=${id}`, f),
  waterBalance: (id: string, f: Fetcher) => get<WaterBalance>(`/almanac/water-balance/${id}`, f),
  frost: (f: Fetcher) => get<FrostReport>('/almanac/frost', f),
};

/** Save a care value the reader has corrected.
 *
 * Two routes, because the contract has two and they mean different things. A
 * specimen override (`PATCH /specimens/{id}`) corrects this plant; a care-value
 * override (`PUT /species/{id}/care-values`) corrects the species for every
 * plant of it. Correcting one plant is what a keeper almost always means, so
 * that route is preferred wherever the contract offers it.
 */
export async function saveCareValue(
  target:
    | { route: 'specimen'; id: string; overrideField: string }
    | { route: 'species'; id: string; field: string },
  value: number | string | boolean | null,
  fetcher: Fetcher,
): Promise<void> {
  const [path, method, body] =
    target.route === 'specimen'
      ? [`/specimens/${target.id}`, 'PATCH', { [target.overrideField]: value }]
      : [`/species/${target.id}/care-values`, 'PUT', { field: target.field, value }];

  const response = await fetcher(`${BASE}${path}`, {
    method,
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(path, response.status, response.statusText);
}
