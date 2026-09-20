# Where these payloads came from

Recorded responses, replayed by `RecordedFetcher` through the same parsers the
live connectors use. Tests read them instead of the network, so the suite is
deterministic and offline — rule 3 of the working agreement, and the only way
the misspelling and synonym cases stay reproducible.

**Nothing in this directory is invented.** Every name, author, family,
identifier and key below was returned by a live API call on the date given.

## `gbif/` — recorded live

Fetched from `https://api.gbif.org/v1` on **2026-09-20**, unmodified apart from
pretty-printing. GBIF's Backbone Taxonomy is CC BY 4.0.

| File | Request | What it exercises |
| --- | --- | --- |
| `match__monstera-deliciosa.json` | `/species/match?name=Monstera deliciosa&verbose=true` | the ordinary exact hit |
| `match__monstra-deliciosa.json` | `…?name=Monstra deliciosa` | a misspelling; GBIF answers `FUZZY` at 85 |
| `match__sansevieria-trifasciata.json` | `…?name=Sansevieria trifasciata` | a synonym resolved to `Dracaena trifasciata` |
| `match__lavandula-angustifolia.json` | `…?name=Lavandula angustifolia` | a hit with three `alternatives` |
| `match__citrus-limon.json` | `…?name=Citrus × limon` | a hybrid, and eleven alternatives |
| `match__hosta-sieboldiana.json` | `…?name=Hosta sieboldiana` | a second clean hit |
| `match__snake-plant.json` | `…?name=Snake plant` | a common name: `matchType: NONE` |
| `match__zzqqx-frobnicata.json` | `…?name=zzqqx frobnicata` | nonsense: `matchType: NONE` |
| `search__snake-plant.json` | `/species/search?q=snake plant&datasetKey=…` | the vernacular path |
| `search__mandrake.json` | `…?q=mandrake` | four species answer to one common name |
| `search__zzqqx-frobnicata.json` | `…?q=zzqqx frobnicata` | no results at all |
| `vernacular__2868241.json` | `/species/2868241/vernacularNames` | common names for *Monstera deliciosa* |
| `vernacular__11041822.json` | `/species/11041822/vernacularNames` | common names for *Dracaena trifasciata* |

## `powo/` — shape reconstructed, content recorded

`powo.science.kew.org` sits behind a bot challenge that answers non-browser
clients — including CI — with an HTML interstitial rather than JSON. These files
are therefore **stand-ins, and say so in a `_provenance` key**:

- the **envelope** follows POWO's documented `/api/2/search` response shape (the
  one `pykew` speaks): `totalResults`, `results[]`, and per result `accepted`,
  `author`, `family`, `genus`, `name`, `rank`, `url`, `fqId`, and `synonymOf`
  for a synonym;
- the **content** — every name, author, family and IPNI LSID — was read from
  live calls to `https://www.ipni.org/api/1/search` on **2026-09-20**. IPNI is
  Kew's own name index and the source of the LSIDs POWO uses as taxon ids.

| File | Query | IPNI record it was built from |
| --- | --- | --- |
| `search__monstera-deliciosa.json` | `Monstera deliciosa` | `87478-1`, Liebm., Araceae |
| `search__sansevieria-trifasciata.json` | `Sansevieria trifasciata` | `540541-1` → `77164235-1` *Dracaena trifasciata* |
| `search__lavandula-angustifolia.json` | `Lavandula angustifolia` | `449008-1`, Mill., Lamiaceae |
| `search__citrus-limon.json` | `Citrus × limon` | `60454758-2`, (L.) Osbeck, Rutaceae |
| `search__hosta-sieboldiana.json` | `Hosta sieboldiana` | `536637-1`, Engl., Hostaceae |
| `search__mandragora-officinarum.json` | `Mandragora officinarum` | `816733-1`, L., Solanaceae |
| `search__snake-plant.json` | `snake plant` | — empty result set |
| `search__mandrake.json` | `mandrake` | — empty result set |
| `search__monstra-deliciosa.json` | `Monstra deliciosa` | — empty result set |
| `search__zzqqx-frobnicata.json` | `zzqqx frobnicata` | — empty result set |

Where IPNI gave no answer for a query (`snake-plant`, `mandrake`,
`monstra-deliciosa`, `zzqqx-frobnicata`), the file is an **empty result set**.
That is also what POWO returns for a common name or a misspelling — its search
is not fuzzy and does not index vernaculars — so those cases test the path that
matters most here: GBIF answers alone, and the confidence drops accordingly.

Two consequences worth keeping in mind:

1. `HttpFetcher` treats a non-JSON 200 as **unreachable**, never as "no such
   plant" (`SourceUnavailable`). A challenged POWO lowers confidence; it cannot
   invent one.
2. When POWO becomes reachable from CI, these files should be re-recorded from
   the live endpoint and this section deleted. Nothing else has to change: the
   parsers already read the real shape.

## Re-recording

```
curl -sS -H 'User-Agent: MinistryOfHerbology/1.0 (+https://github.com/mtaylor45/ministry-of-herbology)' \
  'https://api.gbif.org/v1/species/match?name=Monstera%20deliciosa&strict=false&verbose=true' \
  | python -m json.tool > gbif/match__monstera-deliciosa.json
```

The filename is `<endpoint>__<slug>.json`, where the slug is
`workers.botany.mocks.fetcher.slug()` of the query: casefolded, accents and the
hybrid `×` dropped, non-alphanumerics collapsed to `-`.
