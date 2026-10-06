import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import {
  AnalysisResult,
  ApplicationCreated,
  ApplicationDetail,
  ApplicationPatch,
  ApplicationSort,
  ApplicationStatus,
  ApplicationSummary,
  ConnectionResult,
  ExportResult,
  Health,
  HealthReport,
  ImportResult,
  ModelInfo,
  Profile,
  ProfileOut,
  ResumeLength,
  Settings,
  SettingsOut,
  TailoredResume,
  VersionDetail,
} from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health() {
    return this.http.get<Health>('/health');
  }

  getSettings() {
    return this.http.get<SettingsOut>('/settings');
  }

  saveSettings(settings: Settings) {
    return this.http.put<SettingsOut>('/settings', settings);
  }

  saveApiKey(apiKey: string) {
    return this.http.put<void>('/settings/api-key', { api_key: apiKey });
  }

  deleteApiKey() {
    return this.http.delete<void>('/settings/api-key');
  }

  getModels() {
    return this.http.get<ModelInfo[]>('/models');
  }

  testConnection() {
    return this.http.post<ConnectionResult>('/settings/test', {});
  }

  getProfile() {
    return this.http.get<ProfileOut>('/profile');
  }

  saveProfile(profile: Profile) {
    return this.http.put<ProfileOut>('/profile', profile);
  }

  importResumeFile(file: File) {
    const body = new FormData();
    body.append('file', file, file.name);
    return this.http.post<ImportResult>('/profile/import', body);
  }

  importResumeText(text: string) {
    return this.http.post<ImportResult>('/profile/import-text', { text });
  }

  analyzeJob(text: string) {
    return this.http.post<AnalysisResult>('/jobs/analyze', { text });
  }

  tailorResume(analysis: AnalysisResult, length: ResumeLength) {
    return this.http.post<TailoredResume>('/jobs/tailor', { analysis, length });
  }

  exportResume(
    profile: Profile,
    jobTitle: string,
    company: string,
    skillsFirst: boolean,
    applicationId: number | null = null,
  ) {
    return this.http.post<ExportResult>('/export', {
      profile,
      job_title: jobTitle,
      company,
      skills_first: skillsFirst,
      application_id: applicationId,
    });
  }

  checkHealth(profile: Profile) {
    return this.http.post<HealthReport>('/health-check', { profile });
  }

  createApplication(postingText: string, analysis: AnalysisResult | null) {
    return this.http.post<ApplicationCreated>('/applications', { posting_text: postingText, analysis });
  }

  listApplications(query: string, status: ApplicationStatus | '', sort: ApplicationSort) {
    let params = new HttpParams().set('sort', sort);
    if (query.trim()) {
      params = params.set('q', query.trim());
    }
    if (status) {
      params = params.set('status', status);
    }
    return this.http.get<ApplicationSummary[]>('/applications', { params });
  }

  getApplication(id: number) {
    return this.http.get<ApplicationDetail>(`/applications/${id}`);
  }

  patchApplication(id: number, patch: ApplicationPatch) {
    return this.http.patch<ApplicationDetail>(`/applications/${id}`, patch);
  }

  deleteApplication(id: number, deleteFiles: boolean) {
    return this.http.delete<void>(`/applications/${id}`, { params: { delete_files: deleteFiles } });
  }

  getVersion(applicationId: number, versionId: number) {
    return this.http.get<VersionDetail>(`/applications/${applicationId}/versions/${versionId}`);
  }

  setSubmitted(applicationId: number, versionId: number, submitted: boolean) {
    return this.http.put<ApplicationDetail>(
      `/applications/${applicationId}/versions/${versionId}/submitted`,
      null,
      { params: { submitted } },
    );
  }

  /** The bytes of an exported file, for browser mode where the desktop shell cannot open it directly. */
  downloadExport(path: string) {
    return this.http.get('/export/file', { params: { path }, responseType: 'blob' });
  }
}
