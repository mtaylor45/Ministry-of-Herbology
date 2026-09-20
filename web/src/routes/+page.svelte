<script lang="ts">
  import StatusPill from '$ui/StatusPill.svelte';
  import { STATUS } from '$ui/status';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
</script>

<svelte:head><title>Morning Rounds — The Ministry of Herbology</title></svelte:head>

<h1>Morning Rounds <span class="plain">Today</span></h1>

{#if data.error}
  <p class="error">The greenhouse could not be reached. ({data.error})</p>
{:else}
  <p class="greeting">{data.rounds?.greeting}</p>

  <section aria-labelledby="due-heading">
    <h2 id="due-heading">Needs tending <span class="plain">Due today</span></h2>
    {#if data.rounds?.due.length}
      <ul class="tasks">
        {#each data.rounds.due as task (task.id)}
          <li>
            <a href={task.deep_link}>
              <span class="themed">{task.title}</span>
              <span class="plain">{task.plain_title}</span>
            </a>
            <StatusPill status={STATUS.parched} />
          </li>
        {/each}
      </ul>
    {:else}
      <p>Nothing is due. The grounds are content.</p>
    {/if}
  </section>

  {#if data.rounds?.satisfied.length}
    <section aria-labelledby="satisfied-heading">
      <h2 id="satisfied-heading">Already seen to <span class="plain">Covered by rain</span></h2>
      <ul class="tasks">
        {#each data.rounds.satisfied as task (task.id)}
          <li>
            <span class="themed">{task.title}</span>
            <StatusPill status={STATUS.satedByRain} />
          </li>
        {/each}
      </ul>
    </section>
  {/if}
{/if}

<style>
  .plain {
    color: var(--moh-ink-muted);
    font-family: var(--moh-font-body);
    font-size: var(--moh-text-sm);
  }
  .greeting {
    font-style: italic;
    color: var(--moh-ink-muted);
  }
  .error {
    color: var(--moh-ailing);
  }
  .tasks {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: var(--moh-space-3);
  }
  .tasks li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--moh-space-2);
    min-height: var(--moh-tap);
    padding: var(--moh-space-3);
    background: var(--moh-surface-raised);
    border: 1px solid var(--moh-border);
    border-radius: var(--moh-radius);
  }
  .tasks a {
    display: flex;
    flex-direction: column;
    text-decoration: none;
    color: inherit;
  }
  .themed {
    font-family: var(--moh-font-display);
    font-size: var(--moh-text-lg);
  }
</style>
