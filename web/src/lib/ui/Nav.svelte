<script lang="ts">
  import { page } from '$app/stores';

  /** Bottom bar on mobile, sidebar from 900px up. Five sections, per the plan. */
  const SECTIONS = [
    { href: '/', themed: 'Morning Rounds', plain: 'Today' },
    { href: '/register', themed: 'The Register', plain: 'Inventory' },
    { href: '/grounds', themed: 'The Grounds', plain: 'Maps' },
    { href: '/almanac', themed: 'The Almanac', plain: 'Weather' },
    { href: '/office', themed: 'Ministry Office', plain: 'Settings' }
  ];

  const isCurrent = (href: string, pathname: string) =>
    href === '/' ? pathname === '/' : pathname.startsWith(href);
</script>

<nav aria-label="Sections">
  <ul>
    {#each SECTIONS as section (section.href)}
      <li>
        <a
          href={section.href}
          aria-current={isCurrent(section.href, $page.url.pathname) ? 'page' : undefined}
        >
          <span class="themed">{section.themed}</span>
          <span class="plain">{section.plain}</span>
        </a>
      </li>
    {/each}
  </ul>
</nav>

<style>
  nav {
    position: fixed;
    inset: auto 0 0 0;
    background: var(--moh-surface-raised);
    border-top: 1px solid var(--moh-border);
    padding-bottom: env(safe-area-inset-bottom);
    z-index: 10;
  }
  ul {
    display: flex;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li { flex: 1; }
  a {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: var(--moh-tap);
    padding: var(--moh-space-2) var(--moh-space-1);
    color: var(--moh-ink-muted);
    text-decoration: none;
    text-align: center;
  }
  a[aria-current='page'] {
    color: var(--moh-accent);
    box-shadow: inset 0 2px 0 var(--moh-accent);
  }
  .themed {
    font-family: var(--moh-font-display);
    font-size: var(--moh-text-xs);
  }
  .plain { font-size: var(--moh-text-xs); opacity: 0.75; }

  @media (min-width: 900px) {
    nav {
      inset: 0 auto 0 0;
      width: 14rem;
      border-top: none;
      border-right: 1px solid var(--moh-border);
    }
    ul { flex-direction: column; padding-top: var(--moh-space-8); }
    a { flex-direction: row; justify-content: flex-start; gap: var(--moh-space-2); padding-inline: var(--moh-space-4); }
    a[aria-current='page'] { box-shadow: inset 3px 0 0 var(--moh-accent); }
    .themed { font-size: var(--moh-text-base); }
  }
</style>
