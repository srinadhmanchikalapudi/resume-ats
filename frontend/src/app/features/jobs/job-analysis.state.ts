import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { AnalysisResult } from '../../core/models';

/** Keeps the pasted posting and its result alive while the user moves between pages. */
@Injectable({ providedIn: 'root' })
export class JobAnalysisState {
  private readonly api = inject(ApiService);

  readonly posting = signal('');
  readonly result = signal<AnalysisResult | null>(null);
  readonly analyzing = signal(false);
  readonly error = signal<string | null>(null);

  async analyze(): Promise<void> {
    this.analyzing.set(true);
    this.error.set(null);
    try {
      this.result.set(await firstValueFrom(this.api.analyzeJob(this.posting())));
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.analyzing.set(false);
    }
  }

  clear(): void {
    this.posting.set('');
    this.result.set(null);
    this.error.set(null);
  }
}
