import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import {
  AnalysisResult,
  ConnectionResult,
  Health,
  ImportResult,
  ModelInfo,
  Profile,
  ProfileOut,
  ResumeLength,
  Settings,
  SettingsOut,
  TailoredResume,
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
}
