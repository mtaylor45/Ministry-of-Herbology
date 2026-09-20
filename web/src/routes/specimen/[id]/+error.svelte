<script lang="ts">
  /** A plant that is not in the Register, said plainly rather than as a number. */
  import { page } from '$app/stores';
  import { EmptyState, ListRow } from '$ui';
</script>

<svelte:head><title>Not in the Register — The Ministry of Herbology</title></svelte:head>

<EmptyState
  icon="search"
  themed="No such entry in the Register"
  plain="This plant is not in the Register"
  body={$page.error?.message ?? 'The greenhouse has no record under that number.'}
/>

<ul class="ways-back">
  <li>
    <ListRow
      themed="The Register"
      plain="Open the Register"
      meta="Every plant on the grounds"
      href="/register"
      icon="leaf"
    />
  </li>
  <li>
    <ListRow
      themed="Morning Rounds"
      plain="Back to today"
      meta="What needs tending now"
      href="/"
      icon="water"
    />
  </li>
</ul>

<style>
  .ways-back {
    list-style: none;
    margin: var(--moh-space-6) 0 0;
    padding: 0;
    display: grid;
    gap: var(--moh-space-2);
  }
</style>
