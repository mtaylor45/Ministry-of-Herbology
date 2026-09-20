<script lang="ts">
  import { hasThemed, requirePair, type PlainDisplay } from './pairing';

  /** A themed string and its plain meaning. The themed half never travels alone.
   *  Every component in this library renders its labels through here. */
  let {
    themed,
    plain,
    display = 'beside',
    where = 'Label',
  }: {
    themed?: string;
    plain?: string;
    /** `beside` on one line, `below` stacked, `screen-reader` plain read aloud only. */
    display?: PlainDisplay;
    /** Component name, so a pairing failure names the offender. */
    where?: string;
  } = $props();

  const safePlain = $derived(requirePair(themed, plain, where));
</script>

{#if hasThemed(themed)}
  <span class="label" data-display={display}>
    <span class="themed">{themed}</span>
    {#if display === 'screen-reader'}
      <span class="visually-hidden"> — {safePlain}</span>
    {:else}
      <span class="plain">{safePlain}</span>
    {/if}
  </span>
{:else}
  <span class="label" data-display="plain-only">{safePlain}</span>
{/if}

<style>
  .label {
    display: inline-flex;
    gap: var(--moh-space-2);
    align-items: baseline;
    min-width: 0;
  }
  .label[data-display='below'] {
    flex-direction: column;
    gap: 0;
    align-items: flex-start;
  }
  .themed {
    font-family: var(--moh-font-display);
  }
  .plain {
    color: var(--moh-ink-muted);
    font-size: var(--moh-text-sm);
  }
  .label[data-display='beside'] .plain::before {
    content: '— ';
  }
</style>
