<script lang="ts">
  import Button from '../Button.svelte';
  import Card from '../Card.svelte';
  import Dialog from '../Dialog.svelte';
  import EmptyState from '../EmptyState.svelte';
  import Icon from '../Icon.svelte';
  import ListRow from '../ListRow.svelte';
  import NumberField from '../NumberField.svelte';
  import SearchInput from '../SearchInput.svelte';
  import SelectField from '../SelectField.svelte';
  import Skeleton from '../Skeleton.svelte';
  import StaleNotice from '../StaleNotice.svelte';
  import StatusPill from '../StatusPill.svelte';
  import TaskCheckbox from '../TaskCheckbox.svelte';
  import TextField from '../TextField.svelte';
  import ThemeSwitcher from '../ThemeSwitcher.svelte';
  import Toggle from '../Toggle.svelte';
  import { ICON_NAMES, ICONS } from '../icons';
  import { selectionState, selectionSummary, toggleAll, toggleOne } from '../selection';
  import { STATUS } from '../status';
  import { SAMPLE_TASKS, SAMPLE_SPECIMENS, SAMPLE_LOCATIONS } from './samples';

  /** Every component in the library, once, with no API behind it. */
  let { theme }: { theme: string } = $props();

  let nickname = $state('Sunday');
  let potSize = $state<number | null>(180);
  let location = $state('greenhouse-bench');
  let query = $state('');
  let notify = $state(true);
  let dialogOpen = $state(false);
  let selected = $state(new Set<string>([SAMPLE_TASKS[0].id]));

  const state = $derived(selectionState(selected.size, SAMPLE_TASKS.length));
</script>

<h3 class="pane-title">{theme}</h3>

<section aria-labelledby="{theme}-buttons" class="group">
  <h4 id="{theme}-buttons">Buttons</h4>
  <div class="row">
    <Button themed="Tend to it" plain="Water now" icon="water" />
    <Button variant="quiet" plain="Not today" />
    <Button variant="destructive" themed="Uproot" plain="Remove specimen" icon="trash" />
  </div>
  <div class="row">
    <Button plain="Saving" loading />
    <Button plain="Unavailable" disabled />
    <Button variant="quiet" plain="Disabled and quiet" disabled />
  </div>
  <Button plain="Add a specimen" icon="plus" full />
</section>

<section aria-labelledby="{theme}-status" class="group">
  <h4 id="{theme}-status">Status</h4>
  <div class="row">
    <StatusPill status={STATUS.parched} />
    <StatusPill status={STATUS.satedByRain} />
    <StatusPill status={STATUS.frostComing} />
    <StatusPill status={STATUS.thriving} />
    <StatusPill status={STATUS.struggling} />
  </div>
</section>

<section aria-labelledby="{theme}-tasks" class="group">
  <h4 id="{theme}-tasks">Task completion — one tap and batch</h4>
  <Card themed="Morning Rounds" plain="Due today" level={4}>
    <TaskCheckbox
      plain="Select all"
      themed="The whole round"
      checkState={state}
      meta={selectionSummary(selected.size, SAMPLE_TASKS.length)}
      onchange={() => (selected = toggleAll(SAMPLE_TASKS.map((task) => task.id), state))}
    />
    <hr />
    {#each SAMPLE_TASKS as task (task.id)}
      <TaskCheckbox
        themed={task.themed}
        plain={task.plain}
        meta={task.meta}
        checked={selected.has(task.id)}
        onchange={() => (selected = toggleOne(selected, task.id))}
      />
    {/each}
    {#snippet footer()}
      <Button plain="Mark {selected.size} done" themed="Enter in the ledger" icon="check" />
    {/snippet}
  </Card>
</section>

<section aria-labelledby="{theme}-rows" class="group">
  <h4 id="{theme}-rows">Cards and list rows</h4>
  <Card themed="The Register" plain="Inventory" level={4}>
    <div class="stack">
      {#each SAMPLE_SPECIMENS as specimen (specimen.id)}
        <ListRow
          themed={specimen.themed}
          plain={specimen.plain}
          meta={specimen.meta}
          icon={specimen.icon}
          href="#gallery"
        />
      {/each}
      <ListRow plain="Selected row" meta="Tapped for a batch action" icon="leaf" selected />
      <ListRow plain="Unavailable row" meta="Nothing to open yet" icon="leaf" disabled onclick={() => {}} />
    </div>
  </Card>
</section>

<section aria-labelledby="{theme}-fields" class="group">
  <h4 id="{theme}-fields">Fields</h4>
  <div class="stack">
    <SearchInput bind:value={query} themed="Consult the Register" plain="Search specimens" placeholder="Basil, north bed, toxic…" />
    <TextField bind:value={nickname} themed="What you call it" plain="Nickname" hint="Only you see this." />
    <NumberField bind:value={potSize} plain="Pot diameter" suffix="mm" min={0} step={10} />
    <SelectField bind:value={location} themed="Where it stands" plain="Location" options={SAMPLE_LOCATIONS} />
    <TextField plain="Field note" rows={2} placeholder="Leaf tips browning on the south side…" />
    <TextField plain="Species" error="No match in the accepted names. Try the botanical name." required />
    <Toggle bind:checked={notify} themed="Send word by owl" plain="Notify me about this plant" hint="Uses your hub notifications." />
  </div>
</section>

<section aria-labelledby="{theme}-states" class="group">
  <h4 id="{theme}-states">Empty, loading and stale</h4>
  <div class="stack">
    <EmptyState
      themed="The bed lies fallow"
      plain="No specimens here yet"
      body="Nothing has been planted in this zone. Add one and it will appear in the Register."
    >
      {#snippet action()}
        <Button plain="Add a specimen" icon="plus" />
      {/snippet}
    </EmptyState>
    <Card plain="Loading" level={4}>
      <Skeleton lines={3} plain="Loading the Register…" />
    </Card>
    <StaleNotice
      themed="The owl has not returned"
      plain="The Almanac forecast"
      asOf={new Date(Date.now() - 3 * 60 * 60 * 1000)}
      reason="The weather service could not be reached on this network."
      onretry={() => {}}
    />
    <StaleNotice plain="Soil moisture" asOf={null} reason="No sensor has reported yet." />
  </div>
</section>

<section aria-labelledby="{theme}-dialog" class="group">
  <h4 id="{theme}-dialog">Dialog and sheet</h4>
  <Button variant="quiet" plain="Open the sheet" onclick={() => (dialogOpen = true)} />
  <Dialog
    bind:open={dialogOpen}
    themed="Uproot this specimen?"
    plain="Remove this plant"
    description="Its logs and photos go with it. This cannot be undone."
  >
    <p>Focus is held inside this sheet, Escape closes it, and it goes back where it came from.</p>
    <TextField plain="Type the nickname to confirm" />
    {#snippet footer()}
      <Button variant="quiet" plain="Keep it" onclick={() => (dialogOpen = false)} />
      <Button variant="destructive" plain="Remove it" onclick={() => (dialogOpen = false)} />
    {/snippet}
  </Dialog>
</section>

<section aria-labelledby="{theme}-icons" class="group">
  <h4 id="{theme}-icons">Icons</h4>
  <ul class="icons">
    {#each ICON_NAMES as name (name)}
      <li><Icon {name} size={22} /><span>{ICONS[name].plain}</span></li>
    {/each}
  </ul>
</section>

<section aria-labelledby="{theme}-theme" class="group">
  <h4 id="{theme}-theme">Theme switcher</h4>
  <p class="note">This one writes to the whole document, not to this panel.</p>
  <ThemeSwitcher />
</section>

<style>
  .pane-title {
    margin: 0 0 var(--moh-space-4);
    font-size: var(--moh-text-lg);
    color: var(--moh-ink-muted);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  .group {
    margin-bottom: var(--moh-space-8);
  }
  h4 {
    font-size: var(--moh-text-base);
    margin-bottom: var(--moh-space-2);
    padding-bottom: var(--moh-space-1);
    border-bottom: 1px solid var(--moh-border);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--moh-space-2);
    margin-bottom: var(--moh-space-2);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--moh-space-3);
  }
  hr {
    border: none;
    border-top: 1px solid var(--moh-border);
    margin: var(--moh-space-2) 0;
  }
  .icons {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
    gap: var(--moh-space-2);
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .icons li {
    display: flex;
    align-items: center;
    gap: var(--moh-space-2);
    font-size: var(--moh-text-sm);
    color: var(--moh-ink-muted);
  }
  .note {
    margin: 0 0 var(--moh-space-2);
    color: var(--moh-ink-muted);
    font-size: var(--moh-text-sm);
  }
</style>
