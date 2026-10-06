import { Component, computed, input } from '@angular/core';
import { AnalysisResult } from '../../core/models';
import { STATUS_LABELS, groupByImportance, requiredGaps, scoreBand } from './job-utils';

/**
 * The full read-out of a job analysis: score, gaps, every requirement with its evidence, and the keyword check.
 * Used on the Job match page and inside each saved application. Anything placed inside the tag (for example a
 * "Tailor resume" button) is shown under the score summary.
 */
@Component({
  selector: 'app-analysis-view',
  templateUrl: './analysis-view.html',
  styleUrl: './analysis-view.scss',
})
export class AnalysisView {
  readonly result = input.required<AnalysisResult>();

  protected readonly groups = computed(() => groupByImportance(this.result().matches));
  protected readonly gaps = computed(() => requiredGaps(this.result().matches));
  protected readonly band = computed(() => scoreBand(this.result().scores.overall));
  protected readonly statusLabels = STATUS_LABELS;
}
