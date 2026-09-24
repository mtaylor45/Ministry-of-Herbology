/** The arithmetic and the wording of Morning Rounds, as pure functions.
 *
 * The screen itself is markup; everything that decides what a reader is told
 * lives here, where it can be tested without a browser. Three rules shape most
 * of what follows, and all three are about not letting the screen claim more
 * than the API said:
 *
 *   1. **Satisfied is not done.** A watering the rain settled stays on the
 *      round as settled. It is not a completed job and it is not an absent one.
 *   2. **A silence is rendered.** A plant the scheduler could not schedule, and
 *      an API that does not say whether there were any, both get a sentence.
 *   3. **A guess never arrives looking like a measurement.** Under ADR 0010
 *      nothing in this house measures the soil, so a task built on an uncited
 *      interval or a degraded water balance says so next to the instruction.
 */

import { STATUS, type Status, type SelectOption } from '$ui';
import { reportsItsOwnConfidence } from '../shared/assessment';
import { taskTypeLabel } from '../shared/labels';
import type {
  Confidence,
  Member,
  MorningRounds,
  SpecimenName,
  Task,
  UnscheduledSpecimen,
} from './api';

/** Whole days between two instants, floored — "overdue by 1 day" needs a full
 *  day to have passed, not a minute past midnight. */
export function daysBetween(from: string, to: Date): number {
  const due = new Date(from);
  if (Number.isNaN(due.getTime())) return 0;
  const startOfDue = Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate());
  const startOfNow = Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), to.getUTCDate());
  return Math.round((startOfNow - startOfDue) / 86_400_000);
}

/** When this was owed, in plain words. Morning Rounds shows what is due today
 *  and everything still owed from before, and those two are not the same thing
 *  to a reader deciding what to carry outside. */
export function dueSentence(task: Task, now: Date): string {
  const late = daysBetween(task.due_at, now);
  if (late <= 0) return 'due today';
  if (late === 1) return 'a day overdue';
  return `${late} days overdue`;
}

/** The plain second line of a task row: the job, when it was owed, how much. */
export function taskMeta(task: Task, now: Date): string {
  const parts = [taskTypeLabel(task.task_type), dueSentence(task, now)];
  if (task.amount_ml) parts.push(`${task.amount_ml} ml`);
  return parts.join(' · ');
}

/** What settled a watering, as a pill. Three of the four have a `$ui` status
 *  already; `forecast_change` and `manual` are this screen's, paired the same
 *  way. Never "done": the job was not done, it stopped being needed. */
export function satisfiedStatus(task: Task): Status {
  switch (task.satisfied_by) {
    case 'rain':
      return STATUS.satedByRain;
    case 'sensor':
      return STATUS.satedBySensor;
    case 'forecast_change':
      return {
        themed: 'The heavens changed their mind',
        plain: 'The forecast changed — no longer needed',
        tone: 'sated',
      };
    case 'manual':
      return {
        themed: 'Set aside by hand',
        plain: 'Marked as not needed by a person',
        tone: 'sated',
      };
    default:
      return {
        themed: 'Settled, cause unrecorded',
        plain: 'Settled — the API did not say what settled it',
        tone: 'sated',
      };
  }
}

/**
 * How much a task's instruction is worth, as a pill.
 *
 * Deliberately not the Almanac's vocabulary. "Read through cloud" is the right
 * phrase for a forecast whose ingest is a day stale; it is the wrong phrase for
 * a watering scheduled off an interval nobody ever cited, which is not a
 * reading at all. Same four levels (ADR 0004), different sentence — the same
 * split the Specimen page already makes between a measured value and an
 * attested one.
 *
 * `null` is its own answer and is not `high`: a completed task cannot say how
 * sure it was, because the frozen `task` table has no column its confidence
 * could have been kept in (G's escalation 2).
 */
export function taskConfidence(confidence: Confidence | null | undefined): Status {
  switch (confidence) {
    case 'high':
      return { themed: 'Set down with certainty', plain: 'High confidence', tone: 'thriving' };
    case 'medium':
      return { themed: 'Set down with care', plain: 'Medium confidence', tone: 'sated' };
    case 'low':
      return { themed: 'A rough reckoning', plain: 'Low confidence — check it', tone: 'parched' };
    case 'unknown':
      return {
        themed: 'A guess, and said to be one',
        plain: 'Confidence unknown — nothing attests this',
        tone: 'ailing',
      };
    default:
      return {
        themed: 'Not stated',
        plain: 'This task does not say how sure it is',
        tone: 'parched',
      };
  }
}

/** Why a settled task is still on the screen. Said once per section, not once
 *  per row: it is an explanation of the section's existence. */
export const SATISFIED_EXPLANATION =
  'Nothing to do here. These waterings were owed today and something else covered them — ' +
  'they stay on the round so the day reads as a complete record rather than as a short one.';

/** Does this payload say anything at all about plants it could not schedule?
 *
 *  `unscheduled: []` means "every plant is accounted for". A missing field
 *  means the API never said, and an API that never said is exactly the silence
 *  the list exists to break — so the screen says so instead of showing nothing,
 *  the same way the Almanac does for a forecast that states no confidence. */
export function reportsUnscheduled(rounds: MorningRounds | null | undefined): boolean {
  return Array.isArray(rounds?.unscheduled);
}

export const UNSCHEDULED_SILENCE =
  'This build of the API does not report the plants it could not schedule, so this screen cannot ' +
  'tell you whether any were left off. A plant with no watering interval generates no task, and a ' +
  'plant with no task looks exactly like a plant that needs nothing. Added by Workstream G and ' +
  'asked of Workstream A; until the contract carries it, read the rounds below as "what was ' +
  'scheduled", not as "every plant in the house".';

/** Do these tasks carry their own certainty?
 *
 *  Asked of the whole list rather than of each row: one notice at the top of a
 *  section is a warning, and nine of them is wallpaper. A single task that
 *  reports is enough to show the API knows the fields. */
export function tasksReportCertainty(tasks: readonly Task[]): boolean {
  return tasks.some((task) => reportsItsOwnConfidence(task));
}

export const CERTAINTY_SILENCE =
  'These tasks do not say how sure the scheduler is about them. A watering worked out from an ' +
  'uncited interval and one measured for the species look identical here. Workstream G serves ' +
  'that certainty today and the contract does not carry it yet — asked of Workstream A.';

/** The caveat to print under an instruction when there is no structured one.
 *
 *  `detail` is in the frozen contract and `degradations[]` is not, so G writes
 *  the same caveat into both: the plain sentence on `detail` for a client that
 *  reads neither of the new fields, and the structured reasons for one that
 *  does. Printing both would show the reader one caveat twice. The structured
 *  version wins where it exists, because it carries the ceiling each reason
 *  puts on the answer; `detail` is what is left when it does not — which is the
 *  case for every completed task, whose confidence the frozen `task` table has
 *  no column to have kept.
 */
export function instructionNote(task: Task): string | null {
  if (task.degradations?.length) return null;
  return task.detail?.trim() || null;
}

/** A plant left off the rounds, given a name where the register has one.
 *
 *  `unscheduled[]` carries a bare `specimen_id`, so a name costs a second read
 *  of the register. When that read fails the reason is still shown — a uuid
 *  with a reason beside it is worth more than a plant quietly missing. */
export interface UnscheduledRow {
  specimenId: string;
  name: string;
  /** False when the name is a stand-in, so the row can say so plainly. */
  named: boolean;
  reason: string;
  href: string;
}

export function unscheduledRows(
  unscheduled: readonly UnscheduledSpecimen[],
  specimens: readonly SpecimenName[] | null,
): UnscheduledRow[] {
  const names = new Map((specimens ?? []).map((s) => [s.id, s.display_name]));
  return unscheduled.map((entry) => {
    const name = names.get(entry.specimen_id);
    return {
      specimenId: entry.specimen_id,
      name: name ?? 'A plant the register could not name just now',
      named: Boolean(name),
      reason: entry.reason,
      href: `/specimen/${entry.specimen_id}/tending`,
    };
  });
}

// --------------------------------------------------------------- completion

/** How the household member is remembered between visits.
 *
 *  ADR 0008: the picker defaults to the last member used **on that device**,
 *  which is a per-device preference and not a server-side identity. So it lives
 *  in `localStorage` and nowhere else. */
export const MEMBER_STORAGE_KEY = 'moh:last-member';

export function readRememberedMember(): string | null {
  try {
    return globalThis.localStorage?.getItem(MEMBER_STORAGE_KEY) ?? null;
  } catch {
    // Private browsing, or storage switched off. A forgotten default is a
    // nuisance; a screen that will not load because of one is a defect.
    return null;
  }
}

export function rememberMember(id: string): void {
  try {
    globalThis.localStorage?.setItem(MEMBER_STORAGE_KEY, id);
  } catch {
    /* see above */
  }
}

/** Who the picker starts on: the remembered member if they are still in the
 *  household, otherwise the first one, otherwise nobody. */
export function initialMember(members: readonly Member[], remembered: string | null): string {
  if (remembered && members.some((member) => member.id === remembered)) return remembered;
  return members[0]?.id ?? '';
}

export function memberOptions(members: readonly Member[]): SelectOption[] {
  return members.map((member) => ({ value: member.id, plain: member.name }));
}

export function memberName(members: readonly Member[], id: string): string | null {
  return members.find((member) => member.id === id)?.name ?? null;
}

/** What the live region announces after a batch is marked done.
 *
 *  Plain language only — this is read aloud, and a themed phrase read aloud on
 *  its own is the pairing rule broken where it matters most. The member is
 *  named because attribution is the point of asking (ADR 0008). */
export function completionAnnouncement(count: number, who: string | null): string {
  const jobs = count === 1 ? '1 task' : `${count} tasks`;
  return who
    ? `${jobs} marked done, recorded against ${who}.`
    : `${jobs} marked done. No household member was recorded.`;
}

/** What the batch button offers to do, in plain words, so the label says how
 *  many rather than leaving the reader to count their own ticks. */
export function batchButtonPlain(count: number): string {
  if (count === 0) return 'Mark done — nothing selected yet';
  return count === 1 ? 'Mark 1 task done' : `Mark ${count} tasks done`;
}

/** The sentence shown when a batch did not go through. The selection is kept,
 *  so the sentence says so: a reader who has just ticked six rows should not
 *  have to find them again. */
export function completionFailure(problem: string): string {
  return `Nothing was marked done. ${problem} Your selection has been kept — try again.`;
}

/** Ids worth sending: everything selected that is still on the due list.
 *
 *  A tick left over from a task that has since been settled by rain, or
 *  completed on somebody else's phone, is dropped rather than sent. G skips
 *  unknown ids instead of refusing the batch, which is the right server
 *  behaviour and not a reason for the client to send nonsense. */
export function completableIds(due: readonly Task[], selected: ReadonlySet<string>): string[] {
  return due.filter((task) => selected.has(task.id)).map((task) => task.id);
}
