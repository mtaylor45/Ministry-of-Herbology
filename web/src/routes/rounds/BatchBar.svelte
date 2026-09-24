<script lang="ts">
  /** Select the round, say who did it, tick it all off.
   *
   *  Three controls in a fixed order — select all, who, do it — so the tab
   *  order matches the sentence. The bar sticks to the top of the list rather
   *  than the bottom of the screen: the section bar is already fixed down
   *  there, and a phone with two bars fighting for the same forty-four pixels
   *  is a phone that mis-taps.
   *
   *  The count is a word, never a colour: "3 of 9 selected" is the state, and
   *  the button says what it will do with them.
   */
  import { Button, SelectField, TaskCheckbox, selectionSummary } from '$ui';
  import type { CheckState } from '$ui';
  import type { Member } from './api';
  import { batchButtonPlain, memberOptions } from './tasks';

  let {
    total,
    selected,
    checkState,
    members,
    memberId = $bindable(''),
    busy = false,
    onselectall,
    oncomplete,
  }: {
    total: number;
    selected: number;
    checkState: CheckState;
    members: Member[];
    memberId?: string;
    busy?: boolean;
    onselectall?: () => void;
    oncomplete?: () => void;
  } = $props();

  const summary = $derived(selectionSummary(selected, total));
</script>

<div class="bar">
  <div class="pick">
    <TaskCheckbox
      {checkState}
      themed="The whole round"
      plain="Select every task due"
      meta={summary}
      disabled={busy || total === 0}
      donePlain="All selected"
      onchange={() => onselectall?.()}
    />
  </div>

  <div class="who">
    {#if members.length}
      <SelectField
        bind:value={memberId}
        options={memberOptions(members)}
        themed="Done by"
        plain="Who did these"
        hint="Recorded against this person. The app remembers your last choice on this device."
        disabled={busy}
      />
    {:else}
      <p class="nobody">
        The household has no members on record, so nothing can be attributed. These tasks can still
        be marked done; the ledger will simply not say who did them.
      </p>
    {/if}
  </div>

  <!-- Plain-only, deliberately, and it is the one label on this screen that
       does not carry its themed half. `Label` paints the plain half in
       `--moh-ink-muted`, which on a filled primary button is 1.26:1 against
       `--moh-accent` — measured in the browser, and a WCAG AA failure at any
       size. A themed word nobody can read beside an unreadable plain one is
       rule 7 broken twice, so the themed half waits for Workstream I's fix
       (raised in the pull request, with the gallery's own two instances). -->
  <Button
    plain={batchButtonPlain(selected)}
    icon="check"
    full
    loading={busy}
    disabled={selected === 0}
    busyPlain="Marking them done…"
    onclick={() => oncomplete?.()}
  />
</div>

<style>
  .bar {
    position: sticky;
    top: 0;
    z-index: 5;
    display: grid;
    gap: var(--moh-space-3);
    margin-bottom: var(--moh-space-3);
    padding: var(--moh-space-3);
    background: var(--moh-surface-sunken);
    border: 1px solid var(--moh-border);
    border-radius: var(--moh-radius);
  }
  .nobody {
    margin: 0;
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  /* From a tablet up there is room for the picker beside the selection. */
  @media (min-width: 600px) {
    .bar {
      grid-template-columns: 1fr auto;
      align-items: end;
    }
    .pick {
      grid-column: 1 / -1;
    }
  }
</style>
