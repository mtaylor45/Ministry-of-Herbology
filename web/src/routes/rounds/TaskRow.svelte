<script lang="ts">
  /** One job on the round: what it is, how sure the scheduler is about it, and
   *  the two ways to tick it off.
   *
   *  The checkbox selects for a batch; the button beside it completes this one
   *  task on its own. Both exist because both are how this screen is used —
   *  six plants watered in a row on a Saturday, one watered on the way out of
   *  the door on a Tuesday.
   *
   *  The caveat is inside the row, under the instruction, never behind a tap.
   *  A task worked out from an uncited interval or a degraded water balance has
   *  to look different from one measured for the species, and under ADR 0010
   *  there is no soil probe anywhere in this house to catch it if it does not.
   */
  import { Button, TaskCheckbox } from '$ui';
  import Caveats from '../shared/Caveats.svelte';
  import type { Task } from './api';
  import { instructionNote, taskConfidence, taskMeta } from './tasks';

  let {
    task,
    now,
    selected = false,
    busy = false,
    disabled = false,
    onselect,
    oncomplete,
  }: {
    task: Task;
    now: Date;
    selected?: boolean;
    /** This row's own completion is in flight. */
    busy?: boolean;
    disabled?: boolean;
    onselect?: (checked: boolean) => void;
    oncomplete?: () => void;
  } = $props();

  const note = $derived(instructionNote(task));
</script>

<div class="task">
  <TaskCheckbox
    themed={task.title}
    plain={task.plain_title}
    meta={taskMeta(task, now)}
    checked={selected}
    disabled={disabled || busy}
    name="task"
    value={task.id}
    onchange={(checked) => onselect?.(checked)}
  />

  <!-- The caveat sits between the instruction and the button that acts on it,
       which is the only place a reader in a hurry cannot miss it. -->
  <Caveats
    payload={task}
    what="This instruction"
    status={taskConfidence(task.confidence)}
    labelAs="text"
    noticeWhenSilent={false}
  />
  {#if note}
    <p class="note">{note}</p>
  {/if}

  <div class="acts">
    <a class="open" href={task.deep_link}>
      Open {task.specimen.display_name}
      <span class="visually-hidden">— its tending facet, where its care values are edited</span>
    </a>
    <!-- The visible label is short enough to read on a phone; the accessible
         name says which plant, because eight buttons all called "Mark done"
         are eight identical buttons to anybody listening to the page. -->
    <Button
      variant="quiet"
      icon="check"
      themed="Done and dusted"
      plain="Mark done"
      aria-label={`Done and dusted — mark done: ${task.plain_title}`}
      loading={busy}
      disabled={disabled && !busy}
      busyPlain="Marking it done…"
      onclick={() => oncomplete?.()}
    />
  </div>
</div>

<style>
  .task {
    display: grid;
    gap: var(--moh-space-2);
    padding: var(--moh-space-3);
    background: var(--moh-surface-raised);
    border: 1px solid var(--moh-border);
    border-radius: var(--moh-radius);
  }
  .note {
    margin: 0;
    padding: var(--moh-space-3);
    border-inline-start: 4px solid var(--moh-parched);
    background: var(--moh-surface-sunken);
    border-radius: var(--moh-radius);
    font-size: var(--moh-text-sm);
  }
  .acts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--moh-space-2);
  }
  .open {
    display: inline-flex;
    align-items: center;
    min-height: var(--moh-tap);
    color: var(--moh-ink-muted);
    font-size: var(--moh-text-sm);
  }
</style>
