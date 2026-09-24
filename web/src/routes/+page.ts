import type { PageLoad } from './$types';
import { reads, settle } from './rounds/api';

/**
 * Morning Rounds' reads.
 *
 * The round itself is the screen: if it fails there is nothing to show and the
 * page says so. The member picker is a furnishing, and it must not cost the
 * reader their round when the round is the one thing they came outside with.
 *
 * The register is read **only** when the round names a plant it could not
 * schedule, because `unscheduled[]` carries a bare `specimen_id` and a uuid is
 * not a name. That is a second round trip on the days it happens and no
 * request at all on the days it does not, which is most of them — and it is
 * asked of A in the pull request, because the API could carry the name.
 *
 * `depends` is what a completion invalidates, so ticking a task off re-reads
 * the round rather than editing a list in the browser and hoping it matches.
 */
export const load: PageLoad = async ({ fetch, depends }) => {
  depends('moh:rounds');
  const [rounds, members] = await Promise.all([
    settle(reads.rounds(fetch)),
    settle(reads.members(fetch)),
  ]);
  const specimens = rounds.value?.unscheduled?.length ? await settle(reads.specimens(fetch)) : null;
  return { rounds, members, specimens };
};
