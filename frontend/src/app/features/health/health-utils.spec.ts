import { describe, expect, it } from 'vitest';
import { SEVERITY_LABELS, percent, scoreTone } from './health-utils';

describe('scoreTone', () => {
  it.each([
    [100, 'good'],
    [80, 'good'],
    [79, 'fair'],
    [55, 'fair'],
    [54, 'poor'],
    [0, 'poor'],
  ])('rates %i as %s', (score, tone) => {
    expect(scoreTone(score)).toBe(tone);
  });
});

describe('percent', () => {
  it('rounds a rate to a whole percentage', () => {
    expect(percent(0.05)).toBe('5%');
    expect(percent(0.4)).toBe('40%');
    expect(percent(1)).toBe('100%');
  });
});

describe('SEVERITY_LABELS', () => {
  it('has plain-language names for every severity', () => {
    expect(Object.keys(SEVERITY_LABELS).sort()).toEqual(['high', 'info', 'low', 'medium']);
    expect(SEVERITY_LABELS.high).toBe('Fix first');
  });
});
