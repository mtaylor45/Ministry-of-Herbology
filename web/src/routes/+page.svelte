<script lang="ts">
  /** Morning Rounds — the home screen, and the one people use daily.
   *
   *  It answers one question: what needs doing to the plants today. Everything
   *  on it is arranged around being read one-handed, outdoors, at 375px, by
   *  somebody already holding a watering can.
   *
   *  Four sections, and the order is the argument:
   *
   *   1. **Needs tending.** Ticked one at a time or in a batch, attributed to a
   *      household member (ADR 0008). Each task carries the scheduler's own
   *      certainty next to the instruction.
   *   2. **Already seen to.** Waterings the rain or a sensor settled. Satisfied
   *      is not done, and a task that vanishes because it rained is a task the
   *      reader cannot tell from one that was never scheduled.
   *   3. **Not on the round.** The plants the scheduler could not speak for.
   *   4. **The frost watch.** Tonight's warnings, which are the one thing here
   *      that cannot wait until tomorrow.
   */
  import { invalidate } from '$app/navigation';
  import {
    Card,
    EmptyState,
    StaleNotice,
    StatusPill,
    STATUS,
    nextSelectAll,
    selectionState,
    toggleAll,
    toggleOne,
  } from '$ui';
  import Caveats from './shared/Caveats.svelte';
  import { formatDate } from './shared/labels';
  import BatchBar from './rounds/BatchBar.svelte';
  import TaskRow from './rounds/TaskRow.svelte';
  import Unscheduled from './rounds/Unscheduled.svelte';
  import { reason, writes, type Task } from './rounds/api';
  import {
    CERTAINTY_SILENCE,
    SATISFIED_EXPLANATION,
    UNSCHEDULED_SILENCE,
    completableIds,
    completionAnnouncement,
    completionFailure,
    initialMember,
    memberName,
    readRememberedMember,
    rememberMember,
    reportsUnscheduled,
    satisfiedStatus,
    taskConfidence,
    taskMeta,
    tasksReportCertainty,
    unscheduledRows,
  } from './rounds/tasks';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const rounds = $derived(data.rounds.value);
  const due = $derived<Task[]>(rounds?.due ?? []);
  const satisfied = $derived<Task[]>(rounds?.satisfied ?? []);
  const alerts = $derived((rounds?.alerts ?? []).filter((alert) => alert.state === 'open'));
  const members = $derived(data.members.value ?? []);

  /** Fixed once per render pass: every "overdue by" on the screen is measured
   *  from the same instant, so two rows cannot disagree about what day it is. */
  const now = $derived(new Date(rounds?.date ? `${rounds.date}T12:00:00Z` : Date.now()));

  const unscheduled = $derived(
    unscheduledRows(rounds?.unscheduled ?? [], data.specimens.value?.items ?? null),
  );

  let selected = $state(new Set<string>());
  let memberId = $state('');
  let busyBatch = $state(false);
  let busyTask = $state<string | null>(null);
  let announcement = $state('');
  let failure = $state('');

  // ADR 0008: the picker defaults to the last member used on this device. It is
  // read after mount because it is a browser preference, not server state.
  $effect(() => {
    if (!memberId && members.length) memberId = initialMember(members, readRememberedMember());
  });

  const checkState = $derived(selectionState(countSelected(), due.length));

  function countSelected(): number {
    return due.filter((task) => selected.has(task.id)).length;
  }

  function selectAll() {
    const state = selectionState(countSelected(), due.length);
    selected = nextSelectAll(state)
      ? toggleAll(
          due.map((task) => task.id),
          state,
        )
      : new Set<string>();
  }

  async function complete(ids: string[], { batch }: { batch: boolean }) {
    if (!ids.length) return;
    failure = '';
    announcement = '';
    if (batch) busyBatch = true;
    else busyTask = ids[0];
    try {
      const done = await writes.completeBatch(ids, memberId || null, fetch);
      if (memberId) rememberMember(memberId);
      announcement = completionAnnouncement(done.length, memberName(members, memberId));
      selected = new Set<string>();
      await invalidate('moh:rounds');
    } catch (cause) {
      // The selection is kept deliberately: a reader who has just ticked six
      // rows should not have to find them again to try a second time.
      failure = completionFailure(reason(cause));
    } finally {
      busyBatch = false;
      busyTask = null;
    }
  }
</script>

<svelte:head><title>Morning Rounds — The Ministry of Herbology</title></svelte:head>

<h1>
  <span class="themed">Morning Rounds</span>
  <span class="plain">What needs doing today{rounds ? ` — ${formatDate(rounds.date)}` : ''}</span>
</h1>

{#if data.rounds.error}
  <StaleNotice plain="Today's round" asOf={null} reason={data.rounds.error} />
  <p class="nothing">
    Nothing on this screen is a statement about your plants right now — the round could not be read
    at all. Nothing has been watered, and nothing has been ruled out.
  </p>
{:else}
  {#if rounds?.greeting}
    <p class="greeting">{rounds.greeting}</p>
  {/if}

  <div class="stack">
    <!-- One live region for the whole screen: both ways of completing a task
         report through it, so "3 tasks marked done" is announced once however
         it was done. -->
    <p class="announce" role="status" aria-live="polite">{announcement}</p>
    {#if failure}
      <p class="failure" role="alert">{failure}</p>
    {/if}

    <Card themed="What is owed" plain="Needs tending — due today" level={2}>
      {#if due.length}
        {#if !tasksReportCertainty(due)}
          <p class="silence">{CERTAINTY_SILENCE}</p>
        {/if}

        <BatchBar
          total={due.length}
          selected={countSelected()}
          {checkState}
          {members}
          bind:memberId
          busy={busyBatch}
          onselectall={selectAll}
          oncomplete={() => complete(completableIds(due, selected), { batch: true })}
        />

        <ul class="tasks">
          {#each due as task (task.id)}
            <li>
              <TaskRow
                {task}
                {now}
                selected={selected.has(task.id)}
                busy={busyTask === task.id}
                disabled={busyBatch || (busyTask !== null && busyTask !== task.id)}
                onselect={() => (selected = toggleOne(selected, task.id))}
                oncomplete={() => complete([task.id], { batch: false })}
              />
            </li>
          {/each}
        </ul>
      {:else}
        <EmptyState
          icon="check"
          themed="The grounds are content"
          plain="Nothing is due today"
          body="Nothing is outstanding, which means the round is done rather than that the house is unaccounted for: waterings something else settled, and plants nothing is scheduled for, each get a section of their own whenever there are any."
        />
      {/if}
    </Card>

    {#if satisfied.length}
      <Card themed="Already seen to" plain="Settled without you — not done, not owed" level={2}>
        <p class="lede">{SATISFIED_EXPLANATION}</p>
        <ul class="settled">
          {#each satisfied as task (task.id)}
            <li>
              <div class="head">
                <span class="title">
                  <span class="themed">{task.title}</span>
                  <span class="plain">{task.plain_title}</span>
                </span>
                <StatusPill status={satisfiedStatus(task)} />
              </div>
              <p class="meta">{taskMeta(task, now)}</p>
              <Caveats
                payload={task}
                what="This reckoning"
                status={taskConfidence(task.confidence)}
                labelAs="text"
                noticeWhenSilent={false}
              />
              <a class="open" href={task.deep_link}>Open {task.specimen.display_name}</a>
            </li>
          {/each}
        </ul>
      </Card>
    {/if}

    {#if unscheduled.length}
      <Unscheduled rows={unscheduled} />
    {:else if !reportsUnscheduled(rounds)}
      <Card themed="Not on the round" plain="Plants nothing is scheduled for" level={2}>
        <p class="silence">{UNSCHEDULED_SILENCE}</p>
      </Card>
    {/if}

    {#if alerts.length}
      <Card
        themed="The frost watch"
        plain="Frost warnings tonight and after"
        level={2}
        tone="danger"
      >
        <ul class="alerts">
          {#each alerts as alert (alert.id)}
            <li>
              <div class="head">
                <a class="title" href={`/specimen/${alert.specimen.id}/tending`}>
                  <span class="themed">{alert.specimen.display_name}</span>
                  <span class="plain">
                    {alert.action === 'bring_indoors'
                      ? 'Bring it indoors before sunset'
                      : alert.action === 'cover'
                        ? 'Cover it where it stands'
                        : 'Watch it — no action needed yet'}
                  </span>
                </a>
                <StatusPill status={STATUS.frostComing} />
              </div>
              <p class="meta">
                The night of {formatDate(alert.night_of)} is forecast to fall to {alert.forecast_low_c}
                °C. This plant is warned below {alert.threshold_c} °C.
                {#if alert.advisory}<br />Advisory: {alert.advisory}{/if}
              </p>
              <Caveats
                payload={alert}
                what="This warning"
                labelAs="text"
                noticeWhenSilent={false}
              />
            </li>
          {/each}
        </ul>
      </Card>
    {/if}

    {#if data.members.error}
      <p class="aside">
        The household roster could not be read ({data.members.error}) — tasks can still be marked
        done, but there is nobody to attribute them to until it can.
      </p>
    {/if}
    {#if data.specimens.error && unscheduled.length}
      <p class="aside">
        The register could not be read ({data.specimens.error}), so the plants above are named by
        their register entry rather than by name.
      </p>
    {/if}
  </div>
{/if}

<style>
  h1 {
    display: flex;
    flex-direction: column;
    gap: var(--moh-space-1);
    margin-bottom: var(--moh-space-3);
  }
  h1 .themed {
    font-family: var(--moh-font-display);
  }
  .plain {
    color: var(--moh-ink-muted);
    font-size: var(--moh-text-sm);
  }
  .greeting {
    margin: 0 0 var(--moh-space-4);
    font-style: italic;
    color: var(--moh-ink-muted);
  }
  .stack {
    display: grid;
    gap: var(--moh-space-6);
  }
  .announce:empty {
    display: none;
  }
  .announce {
    margin: 0;
    padding: var(--moh-space-3);
    border-inline-start: 4px solid var(--moh-thriving);
    background: var(--moh-surface-sunken);
    border-radius: var(--moh-radius);
  }
  .failure {
    margin: 0;
    padding: var(--moh-space-3);
    border: 2px solid var(--moh-ailing);
    border-radius: var(--moh-radius);
    background: var(--moh-surface-sunken);
  }
  .nothing,
  .lede,
  .silence {
    margin: 0 0 var(--moh-space-3);
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .silence {
    padding: var(--moh-space-3);
    border: 1px dashed var(--moh-border);
    border-radius: var(--moh-radius);
  }
  .tasks,
  .settled,
  .alerts {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--moh-space-3);
  }
  .settled li,
  .alerts li {
    display: grid;
    gap: var(--moh-space-2);
    padding: var(--moh-space-3);
    background: var(--moh-surface-raised);
    border: 1px solid var(--moh-border);
    border-radius: var(--moh-radius);
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--moh-space-2);
  }
  .title {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .title .themed {
    font-family: var(--moh-font-display);
    font-size: var(--moh-text-lg);
  }
  .meta {
    margin: 0;
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .open {
    display: inline-flex;
    align-items: center;
    min-height: var(--moh-tap);
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .aside {
    margin: var(--moh-space-4) 0 0;
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  /* The whole page sits above the fixed section bar on a phone. */
  ul:last-child {
    margin-bottom: 0;
  }
</style>
