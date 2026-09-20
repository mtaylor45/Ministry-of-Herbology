# The component library — Workstream I

Everything J, H and K need to build a screen without writing a control. Import
from `$ui`:

```svelte
<script lang="ts">
  import { Button, Card, ListRow, TaskCheckbox, StatusPill, STATUS } from '$ui';
</script>

<Card themed="Morning Rounds" plain="Due today">
  <TaskCheckbox
    themed="The basil thirsts"
    plain="Water the basil"
    meta="Kitchen sill — due today"
  />
  <Button themed="Tend to it" plain="Water now" icon="water" />
</Card>
```

See every component in both themes at once: `npm run dev`, then `/gallery`.

## What is here

| Component                                                      | For                                                                |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `Button`                                                       | primary, quiet and destructive actions; `loading` and `disabled`   |
| `Card`                                                         | a titled panel; `level` keeps page headings nesting properly       |
| `ListRow`                                                      | one row of a list, sized for a thumb; link, button or plain row    |
| `TaskCheckbox`                                                 | one-tap and batch task completion — the app's most-used control    |
| `TextField` `NumberField` `SelectField` `Toggle` `SearchInput` | field primitives                                                   |
| `Dialog`                                                       | modal sheet on a phone, panel from 700px; traps and restores focus |
| `EmptyState` `Skeleton` `StaleNotice`                          | nothing yet, loading, and out-of-date                              |
| `Icon` `StatusPill` `ThemeSwitcher` `Nav`                      | icon set, status, theme, navigation                                |

Helpers worth knowing: `selectionState`/`toggleAll`/`toggleOne` (batch selection),
`formatAsOf`/`staleSentence` (how old is this?), `requirePair`/`plainFirst`
(the pairing rule), `applyTheme`/`readThemeChoice`, `focusTrap`.

## The five rules these components keep for you

1. **Every themed string is paired with a plain one.** Components take `themed`
   and `plain`; `plain` is required and the themed half never renders alone. Pass
   a themed string without a plain one and the component throws in dev (ADR 0005).
2. **Touch targets are at least 44px** — `--moh-tap`, with list rows at
   `--moh-row`. The app is used outdoors, one-handed, in gloves.
3. **Status is never carried by colour alone.** Errors say "Error", completed
   tasks say "Done", switches say "On" or "Off", selection is announced with
   `aria-pressed`/`aria-current`.
4. **Focus is visible, and dialogs give it back.** `Dialog` traps Tab, closes on
   Escape when it may be dismissed, and returns focus to whatever opened it.
5. **Whimsy at moments only**, and everything animated honours
   `prefers-reduced-motion`.

## Changing a colour

Tokens live in `tokens.css`, in two theme blocks plus a device-preference block
that mirrors the dark one. `contrast.test.ts` checks every pair against WCAG AA
in both themes, that the two dark blocks agree, and that `theme.ts` and
`app.html` still share the storage key and theme colours. Add a token, add its
pairs. If a colour fails, change the colour — never the threshold.
