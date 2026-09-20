/** The Register entry's own reads: the photographs and the growth log.
 *
 *  Both are Workstream C's, and both answer `[]` until their S2 work lands, so
 *  the facet is built to show an empty log honestly rather than to hide the
 *  panel until there is something in it.
 */

import type { PageLoad } from './$types';
import { reads, settle, type LogEntry, type Photo } from '../api';

export const load: PageLoad = async ({ params, fetch, depends }) => {
  depends('moh:specimen');
  const [photos, log] = await Promise.all([
    settle<Photo[]>(reads.photos(params.id, fetch)),
    settle<LogEntry[]>(reads.log(params.id, fetch)),
  ]);
  return { photos, log };
};
