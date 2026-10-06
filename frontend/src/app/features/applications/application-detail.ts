import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { FileActions } from '../../core/file-actions.service';
import { ApplicationDetail, ApplicationPatch, ApplicationStatus, VersionOut } from '../../core/models';
import { AnalysisView } from '../jobs/analysis-view';
import { toPlainText } from '../tailor/tailor-utils';
import {
  STATUS_OPTIONS,
  daysUntil,
  formatDay,
  formatTimestamp,
  statusLabel,
  versionFile,
  whenLabel,
} from './application-utils';

type TextField = 'company' | 'title' | 'location' | 'job_url';
type DateField = 'applied_on' | 'interview_on';

@Component({
  selector: 'app-application-detail',
  imports: [FormsModule, RouterLink, AnalysisView],
  templateUrl: './application-detail.html',
  styleUrl: './application-detail.scss',
})
export class ApplicationDetailPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  protected readonly files = inject(FileActions);

  protected readonly detail = signal<ApplicationDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notesState = signal<'idle' | 'saving' | 'saved'>('idle');
  protected readonly actionError = signal<string | null>(null);

  protected readonly previewId = signal<number | null>(null);
  protected readonly previewText = signal('');

  protected readonly confirmDelete = signal(false);
  protected readonly deleteFiles = signal(false);

  protected readonly statusOptions = STATUS_OPTIONS;
  protected readonly formatDay = formatDay;
  protected readonly formatTimestamp = formatTimestamp;
  protected readonly statusLabel = statusLabel;
  protected readonly interviewLabel = computed(() => {
    const days = daysUntil(this.detail()?.interview_on ?? null);
    return days === null ? '' : whenLabel(days);
  });

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe((params) => {
      void this.load(Number(params.get('id')));
    });
  }

  private async load(id: number): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    this.previewId.set(null);
    try {
      this.detail.set(await firstValueFrom(this.api.getApplication(id)));
    } catch (error) {
      this.detail.set(null);
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  // --- editing ------------------------------------------------------------------------------

  private async save(patch: ApplicationPatch): Promise<boolean> {
    const current = this.detail();
    if (!current) {
      return false;
    }
    this.actionError.set(null);
    try {
      this.detail.set(await firstValueFrom(this.api.patchApplication(current.id, patch)));
      return true;
    } catch (error) {
      this.actionError.set(errorMessage(error));
      return false;
    }
  }

  protected onText(field: TextField, event: Event): void {
    void this.save({ [field]: (event.target as HTMLInputElement).value.trim() });
  }

  protected onDate(field: DateField, event: Event): void {
    void this.save({ [field]: (event.target as HTMLInputElement).value });
  }

  protected onStatus(event: Event): void {
    void this.save({ status: (event.target as HTMLSelectElement).value as ApplicationStatus });
  }

  protected async onNotes(event: Event): Promise<void> {
    const value = (event.target as HTMLTextAreaElement).value;
    if (value === this.detail()?.notes) {
      return;
    }
    this.notesState.set('saving');
    this.notesState.set((await this.save({ notes: value })) ? 'saved' : 'idle');
  }

  // --- resume versions ----------------------------------------------------------------------

  protected async setSubmitted(version: VersionOut, submitted: boolean): Promise<void> {
    const current = this.detail();
    if (!current) {
      return;
    }
    this.actionError.set(null);
    try {
      this.detail.set(await firstValueFrom(this.api.setSubmitted(current.id, version.id, submitted)));
    } catch (error) {
      this.actionError.set(errorMessage(error));
    }
  }

  protected async togglePreview(version: VersionOut): Promise<void> {
    const current = this.detail();
    if (!current) {
      return;
    }
    if (this.previewId() === version.id) {
      this.previewId.set(null);
      return;
    }
    this.actionError.set(null);
    try {
      const full = await firstValueFrom(this.api.getVersion(current.id, version.id));
      this.previewText.set(toPlainText(full.profile, full.skills_first));
      this.previewId.set(version.id);
    } catch (error) {
      this.actionError.set(errorMessage(error));
    }
  }

  protected async openVersionFile(version: VersionOut, kind: 'docx' | 'pdf'): Promise<void> {
    await this.run(() => this.files.open(versionFile(version, kind)), 'Could not open the file');
  }

  protected openFolder(path: string): Promise<void> {
    return this.run(() => this.files.openFolder(path), 'Could not open the folder');
  }

  protected openJob(url: string): Promise<void> {
    return this.run(() => this.files.openLink(url), 'Could not open the link');
  }

  private async run(action: () => Promise<void>, failure: string): Promise<void> {
    this.actionError.set(null);
    try {
      await action();
    } catch (error) {
      this.actionError.set(`${failure}: ${errorMessage(error)}`);
    }
  }

  // --- deleting -----------------------------------------------------------------------------

  protected async remove(): Promise<void> {
    const current = this.detail();
    if (!current) {
      return;
    }
    this.actionError.set(null);
    try {
      await firstValueFrom(this.api.deleteApplication(current.id, this.deleteFiles()));
      await this.router.navigate(['/applications']);
    } catch (error) {
      this.actionError.set(errorMessage(error));
    }
  }
}
