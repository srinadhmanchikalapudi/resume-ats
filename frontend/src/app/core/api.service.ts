import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { ConnectionResult, Health, ModelInfo, Settings, SettingsOut } from './models';

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
}
