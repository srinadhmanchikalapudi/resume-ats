import { describe, expect, it } from 'vitest';
import { ModelInfo } from '../core/models';
import { filterModels, formatContext, formatPrice } from './model-filter';

function model(id: string, name = id): ModelInfo {
  return { id, name, context_length: null, prompt_price: null, completion_price: null, supports_json: null };
}

const catalogue = [
  model('anthropic/claude-sonnet-5-5', 'Anthropic: Claude Sonnet 5.5'),
  model('openai/gpt-5', 'OpenAI: GPT-5'),
  model('meta/llama-4', 'Meta: Llama 4'),
];

describe('filterModels', () => {
  it('returns everything for an empty query', () => {
    expect(filterModels(catalogue, '  ')).toHaveLength(3);
  });

  it('matches id or name case-insensitively', () => {
    expect(filterModels(catalogue, 'CLAUDE').map((m) => m.id)).toEqual(['anthropic/claude-sonnet-5-5']);
    expect(filterModels(catalogue, 'meta: llama').map((m) => m.id)).toEqual(['meta/llama-4']);
  });

  it('requires every term to match', () => {
    expect(filterModels(catalogue, 'openai claude')).toEqual([]);
  });

  it('respects the limit', () => {
    expect(filterModels(catalogue, '', 2)).toHaveLength(2);
  });
});

describe('formatting', () => {
  it('formats price per million tokens', () => {
    expect(formatPrice(0.000003)).toBe('$3.00/M');
    expect(formatPrice(0)).toBe('free');
    expect(formatPrice(null)).toBe('');
  });

  it('formats context length', () => {
    expect(formatContext(200_000)).toBe('200k ctx');
    expect(formatContext(1_000_000)).toBe('1.0M ctx');
    expect(formatContext(null)).toBe('');
  });
});
