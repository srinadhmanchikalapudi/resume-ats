import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { ApplicationSort, ApplicationStatus, ApplicationSummary } from '../../core/models';
import {
  STATUS_OPTIONS,
  daysUntil,
  formatDay,
  statusLabel,
  upcomingInterviews,
  whenLabel,
} from './application-utils';

const SEARCH_DELAY_MS = 250;

@Component({
  selector: 'app-applications',
  imports: [FormsModule, RouterLink],
  templateUrl: './applications.html',
  styleUrl: './applications.scss',
})
export class ApplicationsPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private searchTimer?: ReturnType<typeof setTimeout>;

  protected readonly query = signal('');
  protected readonly status = signal<ApplicationStatus | ''>('');
  protected readonly sort = signal<ApplicationSort>('updated');

  /** What matches the current search and filter. */
  protected readonly items = signal<ApplicationSummary[]>([]);
  /** Everything, used for the status counts and the upcoming-interviews strip regardless of the filter. */
  private readonly everything = signal<ApplicationSummary[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly upcoming = computed(() => upcomingInterviews(this.everything()));
  protected readonly filtering = computed(() => this.query().trim() !== '' || this.status() !== '');
  protected readonly counts = computed(() => {
    const all = this.everything();
    return STATUS_OPTIONS.map((option) => ({
      ...option,
      count: all.filter((a) => a.status === option.value).length,
    })).filter((option) => option.count > 0);
  });
  protected readonly total = computed(() => this.everything().length);

  protected readonly statusLabel = statusLabel;
  protected readonly formatDay = formatDay;

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  ngOnDestroy(): void {
    clearTimeout(this.searchTimer);
  }

  protected onQuery(value: string): void {
    this.query.set(value);
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => void this.load(), SEARCH_DELAY_MS);
  }

  protected setStatus(value: ApplicationStatus | ''): void {
    this.status.set(this.status() === value ? '' : value);
    void this.load();
  }

  protected setSort(value: ApplicationSort): void {
    this.sort.set(value);
    void this.load();
  }

  protected clearFilters(): void {
    this.query.set('');
    this.status.set('');
    void this.load();
  }

  protected interviewLabel(application: ApplicationSummary): string {
    const days = daysUntil(application.interview_on);
    return days === null ? '' : whenLabel(days);
  }

  private async load(): Promise<void> {
    this.error.set(null);
    try {
      const filtered = await firstValueFrom(this.api.listApplications(this.query(), this.status(), this.sort()));
      this.items.set(filtered);
      this.everything.set(
        this.filtering() ? await firstValueFrom(this.api.listApplications('', '', 'updated')) : filtered,
      );
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
}
