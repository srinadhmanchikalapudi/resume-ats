import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { ModelInfo } from '../../core/models';
import { UpdaterService } from '../../core/updater.service';
import { ModelPicker } from '../../shared/model-picker/model-picker';

interface Notice {
  kind: 'ok' | 'error';
  text: string;
}

@Component({
  selector: 'app-settings',
  imports: [FormsModule, ModelPicker],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class SettingsPage implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly updater = inject(UpdaterService);

  protected readonly baseUrl = signal('');
  protected readonly model = signal('');
  protected readonly extractionModel = signal('');
  protected readonly rewriteModel = signal('');
  protected readonly apiKey = signal('');
  protected readonly hasApiKey = signal(false);
  protected readonly models = signal<ModelInfo[]>([]);
  protected readonly modelsNotice = signal<string | null>(null);
  protected readonly version = signal('');

  protected readonly keyNotice = signal<Notice | null>(null);
  protected readonly settingsNotice = signal<Notice | null>(null);
  protected readonly busy = signal(false);

  async ngOnInit(): Promise<void> {
    try {
      const [settings, health] = await Promise.all([
        firstValueFrom(this.api.getSettings()),
        firstValueFrom(this.api.health()),
      ]);
      this.baseUrl.set(settings.base_url);
      this.model.set(settings.model);
      this.extractionModel.set(settings.extraction_model);
      this.rewriteModel.set(settings.rewrite_model);
      this.hasApiKey.set(settings.has_api_key);
      this.version.set(health.version);
    } catch (error) {
      this.settingsNotice.set({ kind: 'error', text: errorMessage(error) });
      return;
    }
    await this.loadModels();
  }

  protected async loadModels(): Promise<void> {
    this.modelsNotice.set(null);
    try {
      this.models.set(await firstValueFrom(this.api.getModels()));
    } catch (error) {
      this.modelsNotice.set(`${errorMessage(error)} You can still type a model ID by hand.`);
    }
  }

  protected async saveKey(): Promise<void> {
    const key = this.apiKey().trim();
    if (!key) {
      return;
    }
    await this.run(this.keyNotice, async () => {
      await firstValueFrom(this.api.saveApiKey(key));
      this.apiKey.set('');
      this.hasApiKey.set(true);
      await this.loadModels();
      return 'API key saved to your system keychain.';
    });
  }

  protected async removeKey(): Promise<void> {
    await this.run(this.keyNotice, async () => {
      await firstValueFrom(this.api.deleteApiKey());
      this.hasApiKey.set(false);
      return 'API key removed.';
    });
  }

  protected async saveSettings(): Promise<void> {
    await this.run(this.settingsNotice, async () => {
      const saved = await firstValueFrom(
        this.api.saveSettings({
          base_url: this.baseUrl(),
          model: this.model(),
          extraction_model: this.extractionModel(),
          rewrite_model: this.rewriteModel(),
        }),
      );
      this.baseUrl.set(saved.base_url);
      await this.loadModels();
      return 'Settings saved.';
    });
  }

  protected async testConnection(): Promise<void> {
    this.busy.set(true);
    this.settingsNotice.set(null);
    try {
      // Test what is saved, so persist the current form first.
      await firstValueFrom(
        this.api.saveSettings({
          base_url: this.baseUrl(),
          model: this.model(),
          extraction_model: this.extractionModel(),
          rewrite_model: this.rewriteModel(),
        }),
      );
      const result = await firstValueFrom(this.api.testConnection());
      this.settingsNotice.set({ kind: result.ok ? 'ok' : 'error', text: result.message });
    } catch (error) {
      this.settingsNotice.set({ kind: 'error', text: errorMessage(error) });
    } finally {
      this.busy.set(false);
    }
  }

  protected checkForUpdates(): Promise<void> {
    return this.updater.checkForUpdate(true);
  }

  private async run(target: { set(value: Notice | null): void }, action: () => Promise<string>): Promise<void> {
    this.busy.set(true);
    target.set(null);
    try {
      target.set({ kind: 'ok', text: await action() });
    } catch (error) {
      target.set({ kind: 'error', text: errorMessage(error) });
    } finally {
      this.busy.set(false);
    }
  }
}
