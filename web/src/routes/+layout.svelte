<script lang="ts">
  import '$ui/base.css';
  import Nav from '$ui/Nav.svelte';

  let { children } = $props();
</script>

<a class="skip-link" href="#main">Skip to content</a>
<Nav />
<main id="main" tabindex="-1">
  {@render children()}
</main>

<style>
  main {
    max-width: 48rem;
    margin: 0 auto;
    padding: var(--moh-space-6) var(--moh-space-4);
  }
  @media (min-width: 900px) {
    main {
      margin-left: 14rem;
    }
  }
</style>
