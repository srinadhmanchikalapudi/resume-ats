import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { AnalysisResult, ApplicationCreated } from '../../core/models';

/** Keeps the pasted posting and its result alive while the user moves between pages. */
@Injectable({ providedIn: 'root' })
export class JobAnalysisState {
  private readonly api = inject(ApiService);

  readonly posting = signal('');
  readonly result = signal<AnalysisResult | null>(null);
  readonly analyzing = signal(false);
  readonly error = signal<string | null>(null);

  /** The saved application for the current analysis, once the user (or an export) has saved it. */
  readonly application = signal<ApplicationCreated | null>(null);
  readonly saving = signal(false);
  readonly saveError = signal<string | null>(null);

  async analyze(): Promise<void> {
    this.analyzing.set(true);
    this.error.set(null);
    this.application.set(null);
    this.saveError.set(null);
    try {
      this.result.set(await firstValueFrom(this.api.analyzeJob(this.posting())));
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.analyzing.set(false);
    }
  }

  /** Saves the posting and its analysis to the archive. Saving the same posting twice returns the existing record. */
  async saveApplication(): Promise<ApplicationCreated | null> {
    const existing = this.application();
    if (existing) {
      return existing;
    }
    this.saving.set(true);
    this.saveError.set(null);
    try {
      const saved = await firstValueFrom(this.api.createApplication(this.posting(), this.result()));
      this.application.set(saved);
      return saved;
    } catch (error) {
      this.saveError.set(errorMessage(error));
      return null;
    } finally {
      this.saving.set(false);
    }
  }

  clear(): void {
    this.posting.set('');
    this.result.set(null);
    this.error.set(null);
    this.application.set(null);
    this.saveError.set(null);
  }
}
