import { ModelInfo } from '../core/models';

/** Case-insensitive search over id and name; every space-separated term must match. */
export function filterModels(models: ModelInfo[], query: string, limit = 50): ModelInfo[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const matches =
    terms.length === 0
      ? models
      : models.filter((model) => {
          const haystack = `${model.id} ${model.name}`.toLowerCase();
          return terms.every((term) => haystack.includes(term));
        });
  return matches.slice(0, limit);
}

/** Per-token USD price shown per million tokens, e.g. "$3.00/M". */
export function formatPrice(perToken: number | null): string {
  if (perToken === null) {
    return '';
  }
  if (perToken === 0) {
    return 'free';
  }
  return `$${(perToken * 1_000_000).toFixed(2)}/M`;
}

export function formatContext(tokens: number | null): string {
  if (tokens === null) {
    return '';
  }
  return tokens >= 1_000_000 ? `${(tokens / 1_000_000).toFixed(1)}M ctx` : `${Math.round(tokens / 1000)}k ctx`;
}
