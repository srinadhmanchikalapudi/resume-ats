import { HealthSeverity } from '../../core/models';

export const SEVERITY_LABELS: Record<HealthSeverity, string> = {
  high: 'Fix first',
  medium: 'Worth fixing',
  low: 'Minor',
  info: 'Note',
};

/** Colour band for a 0-100 score, used for the bars. */
export function scoreTone(score: number): 'good' | 'fair' | 'poor' {
  if (score >= 80) {
    return 'good';
  }
  return score >= 55 ? 'fair' : 'poor';
}

/** A 0-1 rate as a whole percentage, for the stats line. */
export function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}
