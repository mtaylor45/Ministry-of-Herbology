import type { PageLoad } from './$types';
import { reads, settle } from './rounds/api';

/**
 * Morning Rounds' three reads.
 *
 * The round itself is the screen: if it fails there is nothing to show and the
 * page says so. The other two are furnishings — the member picker and the names
 * for the plants nothing is scheduled for — and neither may cost the reader
 * their round when it is the one thing they came outside with.
 *
 * `depends` is what a completion invalidates, so ticking a task off re-reads
 * the round rather than editing a list in the browser and hoping it matches.
 */
export const load: PageLoad = async ({ fetch, depends }) => {
  depends('moh:rounds');
  const [rounds, members, specimens] = await Promise.all([
    settle(reads.rounds(fetch)),
    settle(reads.members(fetch)),
    settle(reads.specimens(fetch)),
  ]);
  return { rounds, members, specimens };
};
