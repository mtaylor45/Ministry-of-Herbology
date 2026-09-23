<script lang="ts">
  /** How much to trust the number beside this, and every reason it might be
   *  wrong — in the engine's own words, in full, on the screen.
   *
   *  Not a tooltip, not an icon, not a colour. Under ADR 0010 the weather
   *  engines are the only authority on whether an outdoor plant is watered or
   *  carried indoors, and the way they fail is by losing an input and going on
   *  answering in the same confident voice. A caveat the reader has to hover to
   *  find is a caveat that is not there on a phone in the rain.
   *
   *  `detail` is rendered verbatim: Workstream E writes those sentences to be
   *  shown as they stand (`workers/weather/quality.py`), and paraphrasing them
   *  here is how six wordings of one caveat come to exist. */
  import StatusPill from '$ui/StatusPill.svelte';
  import Icon from '$ui/Icon.svelte';
  import type { Assessment } from './api';
  import {
    capSentence,
    caveats,
    measurementConfidence,
    reportsItsOwnConfidence,
  } from './assessment';

  let {
    payload,
    what,
    /** Say so when the endpoint reports no confidence at all. See the seam in
     *  `assessment.ts`: silence has to look like silence, not like a clean bill
     *  of health. */
    noticeWhenSilent = true,
  }: {
    payload: Assessment | null | undefined;
    /** Plain name of the thing being assessed: "This forecast". */
    what: string;
    noticeWhenSilent?: boolean;
  } = $props();

  const reports = $derived(reportsItsOwnConfidence(payload));
  const reasons = $derived(caveats(payload));
</script>

{#if reports}
  <div class="assessment" class:degraded={reasons.length > 0}>
    <p class="level">
      <span class="what">{what}</span>
      <StatusPill status={measurementConfidence(payload?.confidence)} />
    </p>

    {#if reasons.length}
      <h3 class="why">Why it may be wrong</h3>
      <ul>
        {#each reasons as reason (reason.code)}
          <li>
            <span class="glyph" aria-hidden="true"><Icon name="warning" size={18} /></span>
            <span class="says">
              <span class="detail">{reason.detail}</span>
              <span class="cap">{capSentence(reason)}</span>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{:else if noticeWhenSilent}
  <p class="silent">
    <span class="glyph" aria-hidden="true"><Icon name="warning" size={18} /></span>
    <span>
      {what} does not yet report how sure it is. The engine behind it tracks that — a locally computed
      evaporation figure, a stale ingest, a forecast standing in for an observation all lower its confidence
      — but the forecast and history endpoints do not carry those fields yet, so nothing on this screen
      should be read as a clean bill of health. Requested of Workstream A in this sprint's pull request.
    </span>
  </p>
{/if}

<style>
  .assessment {
    padding: var(--moh-space-3);
    border: 1px solid var(--moh-border);
    border-radius: var(--moh-radius);
    background: var(--moh-surface-sunken);
  }
  /* The border is a hint; the words inside are the message. */
  .assessment.degraded {
    border-inline-start: 4px solid var(--moh-parched);
  }
  .level {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--moh-space-2);
    margin: 0;
  }
  .what {
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .why {
    margin: var(--moh-space-3) 0 var(--moh-space-2);
    font-family: var(--moh-font-body);
    font-size: var(--moh-text-sm);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--moh-ink-muted);
  }
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: var(--moh-space-3);
  }
  li {
    display: flex;
    gap: var(--moh-space-2);
    align-items: flex-start;
  }
  .glyph {
    flex: none;
    color: var(--moh-parched);
    margin-top: 2px;
  }
  .says {
    display: flex;
    flex-direction: column;
    gap: var(--moh-space-1);
  }
  .detail {
    font-size: var(--moh-text-base);
  }
  .cap {
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .silent {
    display: flex;
    gap: var(--moh-space-2);
    align-items: flex-start;
    margin: 0;
    padding: var(--moh-space-3);
    border: 1px dashed var(--moh-border);
    border-radius: var(--moh-radius);
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
</style>
