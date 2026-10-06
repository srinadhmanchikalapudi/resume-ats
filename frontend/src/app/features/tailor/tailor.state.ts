import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { AnalysisResult, ExportResult, ResumeLength } from '../../core/models';
import { JobAnalysisState } from '../jobs/job-analysis.state';
import { EditableResume, toEditable, toProfile } from './tailor-utils';

/** The tailored resume being edited. It is tied to one job analysis and discarded when that changes. */
@Injectable({ providedIn: 'root' })
export class TailorState {
  private readonly api = inject(ApiService);
  private readonly jobs = inject(JobAnalysisState);

  readonly length = signal<ResumeLength>('standard');
  readonly skillsFirst = signal(true);
  readonly generating = signal(false);
  readonly error = signal<string | null>(null);

  readonly exporting = signal(false);
  readonly exportError = signal<string | null>(null);
  readonly exported = signal<ExportResult | null>(null);
  /** The resume content at the moment of the last export, to tell the user when edits made since are not in the files. */
  private readonly exportedSnapshot = signal<string>('');

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
      this.exported.set(null);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.generating.set(false);
    }
  }

  /** Writes the current resume as DOCX and PDF into its own folder and returns the checks on both. */
  async export(): Promise<void> {
    const resume = this.resume();
    const job = this.jobs.result()?.job;
    if (!resume || !job) {
      return;
    }
    this.exporting.set(true);
    this.exportError.set(null);
    try {
      // An exported resume always belongs to a saved application, so it can be found again later.
      const application = await this.jobs.saveApplication();
      if (!application) {
        this.exportError.set(this.jobs.saveError() ?? 'Could not save the application.');
        return;
      }
      const profile = toProfile(resume);
      this.exported.set(
        await firstValueFrom(
          this.api.exportResume(profile, job.title, job.company, this.skillsFirst(), application.id),
        ),
      );
      this.exportedSnapshot.set(this.snapshot());
    } catch (error) {
      this.exportError.set(errorMessage(error));
    } finally {
      this.exporting.set(false);
    }
  }

  /** True when the resume was edited after the last export, so the saved files are out of date. */
  hasChangedSinceExport(): boolean {
    return this.exported() !== null && this.snapshot() !== this.exportedSnapshot();
  }

  private snapshot(): string {
    const resume = this.resume();
    return resume ? JSON.stringify([toProfile(resume), this.skillsFirst()]) : '';
  }
}
