import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { AnalysisView } from './analysis-view';
import { JobAnalysisState } from './job-analysis.state';

@Component({
  selector: 'app-jobs',
  imports: [FormsModule, RouterLink, AnalysisView],
  templateUrl: './jobs.html',
  styleUrl: './jobs.scss',
})
export class JobsPage implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly state = inject(JobAnalysisState);

  private readonly hasProfile = signal(true);
  private readonly hasKey = signal(true);
  private readonly hasModel = signal(true);

  protected readonly needsProfile = computed(() => !this.hasProfile());
  protected readonly needsSetup = computed(() => !this.hasKey() || !this.hasModel());
  protected readonly canAnalyze = computed(
    () => this.state.posting().trim().length >= 80 && !this.state.analyzing(),
  );

  async ngOnInit(): Promise<void> {
    try {
      const [profile, settings] = await Promise.all([
        firstValueFrom(this.api.getProfile()),
        firstValueFrom(this.api.getSettings()),
      ]);
      this.hasProfile.set(profile.exists);
      this.hasKey.set(settings.has_api_key);
      this.hasModel.set(Boolean(settings.model || settings.extraction_model));
    } catch {
      // The analyze call reports any real problem; the hints above are only a convenience.
    }
  }

  protected analyze(): Promise<void> {
    return this.state.analyze();
  }
}
