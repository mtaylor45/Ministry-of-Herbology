<script lang="ts">
  import Label from './Label.svelte';
  import { describedBy } from './ids';
  import type { CheckState } from './selection';

  /** The most-used control in the app: completing a task, one tap or a batch
   *  at a time.
   *
   *  The whole row is the target and it is never smaller than 44px, because it
   *  is tapped outdoors, one-handed, in gloves. State is carried by the tick's
   *  shape and by a word, not by colour. `state="mixed"` is the select-all
   *  control for a partly selected list. */
  let {
    checked = $bindable(false),
    checkState,
    themed,
    plain,
    meta,
    disabled = false,
    name,
    value,
    donePlain = 'Done',
    onchange,
  }: {
    checked?: boolean;
    /** Overrides `checked`; `mixed` is the batch select-all state. */
    checkState?: CheckState;
    themed?: string;
    plain: string;
    /** Plain secondary line: "Water — due today". */
    meta?: string;
    disabled?: boolean;
    name?: string;
    value?: string;
    /** The word shown once it is complete. Never colour alone. */
    donePlain?: string;
    onchange?: (checked: boolean) => void;
  } = $props();

  const id = $props.id();
  const metaId = $derived(meta ? `${id}-meta` : undefined);
  const describe = $derived(describedBy(metaId));
  const current = $derived<CheckState>(checkState ?? (checked ? 'checked' : 'unchecked'));

  let input: HTMLInputElement | undefined = $state();

  // `indeterminate` is a property, not an attribute; the server renders
  // data-state="mixed" and aria-checked="mixed" so the state is not lost.
  $effect(() => {
    if (input) input.indeterminate = current === 'mixed';
  });

  function handle(event: Event) {
    const next = (event.currentTarget as HTMLInputElement).checked;
    checked = next;
    onchange?.(next);
  }
</script>

<label class="task" data-state={current} class:disabled>
  <input
    bind:this={input}
    {id}
    class="input"
    type="checkbox"
    {name}
    {value}
    {disabled}
    checked={current === 'checked'}
    aria-checked={current === 'mixed' ? 'mixed' : undefined}
    aria-describedby={describe}
    onchange={handle}
  />
  <span class="box" aria-hidden="true">
    {#if current === 'mixed'}
      <svg viewBox="0 0 24 24" class="tick" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M6 12h12" stroke-linecap="round" />
      </svg>
    {:else}
      <!-- A quill stroke rather than a machine tick; it draws itself on completion. -->
      <svg viewBox="0 0 24 24" class="tick" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M4 13l5 5L20 6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    {/if}
  </span>
  <span class="text">
    <Label {themed} {plain} display="below" where="TaskCheckbox" />
    {#if meta}<span class="meta" id={metaId}>{meta}</span>{/if}
  </span>
  {#if current === 'checked'}<span class="done">{donePlain}</span>{/if}
</label>

<style>
  .task {
    display: flex;
    align-items: center;
    gap: var(--moh-space-3);
    /* the entire row is the tap target */
    min-height: var(--moh-tap);
    padding: var(--moh-space-2) var(--moh-space-3);
    border-radius: var(--moh-radius);
    cursor: pointer;
  }
  .task.disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .task[data-state='checked'] {
    background: var(--moh-selected);
  }

  .input {
    position: absolute;
    width: var(--moh-tap);
    height: var(--moh-tap);
    margin: 0;
    opacity: 0;
    cursor: inherit;
  }

  .box {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 28px;
    height: 28px;
    border: 2px solid var(--moh-border);
    border-radius: var(--moh-radius);
    background: var(--moh-field);
    color: var(--moh-accent-ink);
  }
  .task[data-state='checked'] .box,
  .task[data-state='mixed'] .box {
    background: var(--moh-accent);
    border-color: var(--moh-accent);
  }

  /* The focus ring belongs to the visible box, not to the hidden input. */
  .input:focus-visible + .box {
    outline: 3px solid var(--moh-accent);
    outline-offset: 2px;
  }

  .tick {
    width: 20px;
    height: 20px;
    stroke-dasharray: 30;
    stroke-dashoffset: 30;
  }
  .task[data-state='checked'] .tick,
  .task[data-state='mixed'] .tick {
    stroke-dashoffset: 0;
    /* whimsy at a moment: the tick is written, not switched on */
    transition: stroke-dashoffset 260ms ease-out;
  }

  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }
  .meta {
    color: var(--moh-ink-muted);
    font-size: var(--moh-text-sm);
  }
  .done {
    flex: none;
    font-size: var(--moh-text-sm);
    color: var(--moh-thriving);
  }
  .task[data-state='checked'] .text {
    text-decoration: line-through;
    text-decoration-color: var(--moh-ink-muted);
  }
</style>
