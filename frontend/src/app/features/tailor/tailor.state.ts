import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { AnalysisResult, ResumeLength } from '../../core/models';
import { JobAnalysisState } from '../jobs/job-analysis.state';
import { EditableResume, toEditable } from './tailor-utils';

/** The tailored resume being edited. It is tied to one job analysis and discarded when that changes. */
@Injectable({ providedIn: 'root' })
export class TailorState {
  private readonly api = inject(ApiService);
  private readonly jobs = inject(JobAnalysisState);

  readonly length = signal<ResumeLength>('standard');
  readonly generating = signal(false);
  readonly error = signal<string | null>(null);

  private readonly draft = signal<EditableResume | null>(null);
  private readonly draftFor = signal<AnalysisResult | null>(null);

  /** The editable resume, but only while it still belongs to the analysis on the Job match page. */
  readonly resume = computed(() => (this.draftFor() === this.jobs.result() ? this.draft() : null));

  async generate(): Promise<void> {
    const analysis = this.jobs.result();
    if (!analysis) {
      return;
    }
    this.generating.set(true);
    this.error.set(null);
    try {
      const tailored = await firstValueFrom(this.api.tailorResume(analysis, this.length()));
      this.draft.set(toEditable(tailored));
      this.draftFor.set(analysis);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.generating.set(false);
    }
  }
}
