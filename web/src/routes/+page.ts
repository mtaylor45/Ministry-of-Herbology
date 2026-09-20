import { api, type MorningRounds } from '$api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  try {
    const rounds: MorningRounds = await api.morningRounds(fetch);
    return { rounds, error: null };
  } catch (cause) {
    return { rounds: null, error: cause instanceof Error ? cause.message : 'unknown' };
  }
};
