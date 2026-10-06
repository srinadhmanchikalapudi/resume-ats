import { Component, inject, input, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { HealthReport, Profile } from '../../core/models';
import { SEVERITY_LABELS, percent, scoreTone } from './health-utils';

/**
 * Scores a resume's writing quality (numbers, verbs, clarity, specificity, completeness) and explains each finding.
 * It takes a function rather than a value because the resume it checks is edited in place by its page.
 */
@Component({
  selector: 'app-health-panel',
  templateUrl: './health-panel.html',
  styleUrl: './health-panel.scss',
})
export class HealthPanel {
  private readonly api = inject(ApiService);

  /** Returns the resume to check, as it is right now. */
  readonly source = input.required<() => Profile>();
  /**
   * The resume serialised, which changes whenever it is edited. Pages edit their resume in place, so without an input
   * that changes this panel would never re-render to tell the user the score is out of date.
   */
  readonly snapshot = input.required<string>();

  protected readonly report = signal<HealthReport | null>(null);
  protected readonly checking = signal(false);
  protected readonly error = signal<string | null>(null);
  private checkedSnapshot = '';

  protected readonly severityLabels = SEVERITY_LABELS;
  protected readonly scoreTone = scoreTone;
  protected readonly percent = percent;

  protected async check(): Promise<void> {
    this.checking.set(true);
    this.error.set(null);
    try {
      const profile = this.source()();
      this.checkedSnapshot = JSON.stringify(profile);
      this.report.set(await firstValueFrom(this.api.checkHealth(profile)));
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.checking.set(false);
    }
  }

  /** True once the resume has been edited since the last check, so the shown score is out of date. */
  protected changedSinceCheck(): boolean {
    return this.report() !== null && this.snapshot() !== this.checkedSnapshot;
  }
}
