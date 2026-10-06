import { describe, expect, it } from 'vitest';
import { Importance, MatchStatus, RequirementMatch } from '../../core/models';
import { groupByImportance, requiredGaps, scoreBand } from './job-utils';

function match(id: string, importance: Importance, status: MatchStatus): RequirementMatch {
  return {
    requirement: { id, text: id, category: 'skill', importance, keywords: [] },
    status,
    evidence: [],
    note: '',
  };
}

describe('groupByImportance', () => {
  it('orders groups required, preferred, nice and drops empty ones', () => {
    const groups = groupByImportance([
      match('a', 'nice', 'missing'),
      match('b', 'required', 'matched'),
      match('c', 'required', 'missing'),
    ]);
    expect(groups.map((g) => g.label)).toEqual(['Required', 'Nice to have']);
    expect(groups[0].items.map((m) => m.requirement.id)).toEqual(['b', 'c']);
  });
});

describe('scoreBand', () => {
  it.each([
    [95, 'Strong match'],
    [80, 'Strong match'],
    [65, 'Good match'],
    [45, 'Partial match'],
    [10, 'Weak match'],
    [null, 'No requirements to score'],
  ])('describes %s as "%s"', (score, label) => {
    expect(scoreBand(score)).toBe(label);
  });
});

describe('requiredGaps', () => {
  it('lists unmet required items with missing and unverified before partial', () => {
    const gaps = requiredGaps([
      match('partial', 'required', 'partial'),
      match('ok', 'required', 'matched'),
      match('pref', 'preferred', 'missing'),
      match('none', 'required', 'missing'),
      match('claimed', 'required', 'unverified'),
    ]);
    expect(gaps.map((m) => m.requirement.id)).toEqual(['none', 'claimed', 'partial']);
  });
});
