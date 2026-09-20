/** Typed fetch helpers for the API contract. Workstream I owns this file;
 *  the shapes come from contracts/openapi/openapi.yaml and change only there. */

export type Confidence = 'high' | 'medium' | 'low' | 'unknown';
export type TaskStatus = 'due' | 'done' | 'satisfied' | 'skipped' | 'cancelled';

export interface SpecimenBrief {
  id: string;
  display_name: string;
  is_outdoor: boolean;
  thumb_url: string | null;
}

export interface Task {
  id: string;
  specimen: SpecimenBrief;
  task_type: string;
  due_at: string;
  all_day: boolean;
  status: TaskStatus;
  satisfied_by: 'rain' | 'sensor' | 'forecast_change' | 'manual' | null;
  amount_ml: number | null;
  priority: 'low' | 'normal' | 'urgent';
  /** Themed. Never rendered without `plain_title` nearby (ADR 0005). */
  title: string;
  /** Plain language. What a screen reader announces, and what calendars carry. */
  plain_title: string;
  detail: string | null;
  deep_link: string;
}

export interface FrostAlert {
  id: string;
  specimen: SpecimenBrief;
  night_of: string;
  forecast_low_c: number;
  threshold_c: number;
  action: 'bring_indoors' | 'cover' | 'monitor';
  advisory: string | null;
  state: 'open' | 'resolved' | 'expired';
}

export interface MorningRounds {
  date: string;
  greeting: string;
  due: Task[];
  satisfied: Task[];
  alerts: FrostAlert[];
  weather: Record<string, unknown> | null;
}

export interface Specimen {
  id: string;
  display_name: string;
  nickname: string | null;
  species: { id: string; accepted_name: string; common_name: string | null } | null;
  location: { id: string; name: string; is_outdoor: boolean; is_covered: boolean } | null;
  is_outdoor: boolean;
  in_container: boolean;
  status: string;
}

const BASE = '/api/v1';

async function get<T>(path: string, fetcher: typeof fetch = fetch): Promise<T> {
  const response = await fetcher(`${BASE}${path}`, { headers: { accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} for ${path}`);
  }
  return (await response.json()) as T;
}

export const api = {
  morningRounds: (f?: typeof fetch) => get<MorningRounds>('/tending/rounds', f),
  specimens: (f?: typeof fetch) => get<{ items: Specimen[]; total: number }>('/specimens', f),
  specimen: (id: string, f?: typeof fetch) => get<Specimen>(`/specimens/${id}`, f),
  frostAlerts: (f?: typeof fetch) => get<FrostAlert[]>('/almanac/frost', f),
};
