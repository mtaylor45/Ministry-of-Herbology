/** What Morning Rounds reads and writes, typed against the frozen contract.
 *
 * `contracts/openapi/openapi.yaml` is the authority: where it and this file
 * disagree, this file is the bug. Two shapes below are **not** in the contract
 * and are marked as such — Workstream G serves them additively and has asked A
 * for them (`docs/sprints/S4-workstream-g.md`, escalations 1 and 3):
 *
 *   - `confidence`, `degraded` and `degradations[]` on `Task`;
 *   - `unscheduled[]` on `MorningRounds`.
 *
 * Both are optional here, so the screen works whether or not they arrive, and
 * both absences are rendered rather than swallowed — see `tasks.ts`. The S4
 * pull request repeats the request rather than reshaping anything client-side.
 *
 * `$api/client.ts` carries a 1.2.0 `Task` and a 1.2.0 `MorningRounds` and
 * belongs to Workstream I, so this screen types its own calls (rule 2) instead
 * of editing that file.
 */

import { get, post, type Fetcher } from '../shared/http';
import type { Assessment, Confidence } from '../shared/assessment';

export type { Confidence };
export { ApiError, reason, settle, type Fetched, type Fetcher } from '../shared/http';

export type TaskStatus = 'due' | 'done' | 'satisfied' | 'skipped' | 'cancelled';
export type SatisfiedBy = 'rain' | 'sensor' | 'forecast_change' | 'manual' | null;

export interface SpecimenBrief {
  id: string;
  display_name: string;
  is_outdoor: boolean;
  thumb_url: string | null;
}

/** `Member` — who did the job. ADR 0008: one shared sign-in, and the member is
 *  picked at completion, so the record still says who. */
export interface Member {
  id: string;
  name: string;
  role: 'keeper' | 'tender' | 'observer' | string;
  notify_prefs?: Record<string, unknown>;
}

/**
 * `Task`, plus the three certainty fields G serves beyond 1.2.0.
 *
 * `title` and `plain_title` are both required and both `NOT NULL` in the frozen
 * schema. Rule 7 is not decoration here: the themed half names the plant and
 * the plain half says what to do, and a screen that shows one without the other
 * is either a puzzle or a ledger entry, never an instruction.
 */
export interface Task extends Assessment {
  id: string;
  specimen: SpecimenBrief;
  task_type: string;
  due_at: string;
  all_day?: boolean;
  status: TaskStatus;
  satisfied_by?: SatisfiedBy;
  amount_ml?: number | null;
  priority?: 'low' | 'normal' | 'urgent';
  /** Themed. Never rendered without `plain_title` beside it. */
  title: string;
  /** Plain language. What a screen reader announces and what calendars carry. */
  plain_title: string;
  detail?: string | null;
  completed_at?: string | null;
  completed_by?: Member | null;
  deep_link: string;
}

export interface FrostAlert extends Assessment {
  id: string;
  specimen: SpecimenBrief;
  night_of: string;
  forecast_low_c: number;
  threshold_c: number;
  action: 'bring_indoors' | 'cover' | 'monitor';
  advisory?: string | null;
  task_id?: string | null;
  state: 'open' | 'resolved' | 'expired';
}

/**
 * A plant the scheduler could not speak for, and why — **not in the contract**.
 *
 * ADR 0018 §2 on the frost guard: *"a list of alerts cannot say 'and these
 * three I could not judge'"*. Morning Rounds has the same hole. A plant with no
 * watering interval anywhere generates no task, and a plant with no task is
 * indistinguishable from a plant that needs nothing. G serves this list with a
 * reason per plant; rendering it is the whole point of its existing.
 */
export interface UnscheduledSpecimen {
  specimen_id: string;
  reason: string;
}

export interface Weather {
  time?: string;
  temp_min_c?: number | null;
  temp_max_c?: number | null;
  temperature_c?: number | null;
  precip_mm?: number | null;
  precip_prob_pct?: number | null;
  condition?: string | null;
}

export interface MorningRounds {
  date: string;
  greeting?: string;
  due: Task[];
  /** Waterings the rain or a sensor already covered. Satisfied is not done. */
  satisfied: Task[];
  alerts: FrostAlert[];
  weather?: Weather | null;
  /** Additive beyond 1.2.0. `undefined` means the API never said — which is not
   *  the same as `[]`, "every plant is accounted for". The screen tells those
   *  two apart; see `reportsUnscheduled` in `tasks.ts`. */
  unscheduled?: UnscheduledSpecimen[];
}

/** As much of `Specimen` as the unscheduled list needs: a name to show instead
 *  of a bare uuid. `unscheduled[]` carries `specimen_id` and nothing else. */
export interface SpecimenName {
  id: string;
  display_name: string;
}

export const reads = {
  rounds: (f: Fetcher) => get<MorningRounds>('/tending/rounds', f),
  members: (f: Fetcher) => get<Member[]>('/members', f),
  specimens: (f: Fetcher) => get<{ items: SpecimenName[]; total: number }>('/specimens', f),
};

export const writes = {
  /**
   * `POST /tending/tasks/complete-batch` — several tasks, one action, one
   * member. The one-tap path posts a batch of one deliberately: G routes both
   * through the same code so they cannot diverge, and so should this screen.
   *
   * `completed_by` is sent when a member is chosen. G defaults it server-side
   * when it is absent, which is a convenience, not an excuse — ADR 0008 asks
   * who did the job, and the picker is how the screen asks.
   */
  completeBatch: (taskIds: string[], completedBy: string | null, f: Fetcher) =>
    post<Task[]>(
      '/tending/tasks/complete-batch',
      completedBy ? { task_ids: taskIds, completed_by: completedBy } : { task_ids: taskIds },
      f,
    ),
};
