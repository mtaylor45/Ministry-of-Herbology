<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import Label from './Label.svelte';
  import type { IconName } from './icons';

  /** Nothing here yet — and what to do about it. An empty state without an
   *  action is a dead end, so `action` is where the next step goes. */
  let {
    icon = 'seedling',
    themed,
    plain,
    body,
    action,
  }: {
    icon?: IconName;
    themed?: string;
    plain: string;
    /** A plain sentence saying why it is empty. */
    body?: string;
    action?: Snippet;
  } = $props();
</script>

<div class="empty">
  <span class="glyph" aria-hidden="true"><Icon name={icon} size={40} strokeWidth={1.2} /></span>
  <p class="title"><Label {themed} {plain} display="below" where="EmptyState" /></p>
  {#if body}<p class="body">{body}</p>{/if}
  {#if action}<div class="action">{@render action()}</div>{/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--moh-space-3);
    padding: var(--moh-space-8) var(--moh-space-4);
    text-align: center;
    border: 1px dashed var(--moh-border);
    border-radius: var(--moh-radius-lg);
    background: var(--moh-surface-sunken);
  }
  .glyph {
    color: var(--moh-ink-muted);
  }
  .title {
    margin: 0;
    font-size: var(--moh-text-lg);
  }
  .body {
    margin: 0;
    max-width: 34ch;
    color: var(--moh-ink-muted);
  }
</style>
