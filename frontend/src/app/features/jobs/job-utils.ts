import { Importance, MatchStatus, RequirementMatch } from '../../core/models';

export interface RequirementGroup {
  importance: Importance;
  label: string;
  items: RequirementMatch[];
}

const GROUP_LABELS: Record<Importance, string> = {
  required: 'Required',
  preferred: 'Preferred',
  nice: 'Nice to have',
};

/** Matches grouped by how much the posting cares, in a fixed order, skipping empty groups. */
export function groupByImportance(matches: RequirementMatch[]): RequirementGroup[] {
  return (['required', 'preferred', 'nice'] as const)
    .map((importance) => ({
      importance,
      label: GROUP_LABELS[importance],
      items: matches.filter((m) => m.requirement.importance === importance),
    }))
    .filter((group) => group.items.length > 0);
}

export const STATUS_LABELS: Record<MatchStatus, string> = {
  matched: 'Matched',
  partial: 'Partial',
  missing: 'Missing',
  unverified: 'Unverified',
};

/** Plain-language band for the match estimate. These are descriptions, not hiring predictions. */
export function scoreBand(score: number | null): string {
  if (score === null) {
    return 'No requirements to score';
  }
  if (score >= 80) {
    return 'Strong match';
  }
  if (score >= 60) {
    return 'Good match';
  }
  if (score >= 40) {
    return 'Partial match';
  }
  return 'Weak match';
}

/** Required requirements without full evidence: the gaps worth looking at first. */
export function requiredGaps(matches: RequirementMatch[]): RequirementMatch[] {
  const order: Record<MatchStatus, number> = { missing: 0, unverified: 0, partial: 1, matched: 2 };
  return matches
    .filter((m) => m.requirement.importance === 'required' && m.status !== 'matched')
    .sort((a, b) => order[a.status] - order[b.status]);
}
