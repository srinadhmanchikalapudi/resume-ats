import { Injectable, signal } from '@angular/core';
import { isTauri } from '@tauri-apps/api/core';
import { relaunch } from '@tauri-apps/plugin-process';
import { check, Update } from '@tauri-apps/plugin-updater';

export type UpdateStatus = 'idle' | 'checking' | 'downloading' | 'installing' | 'error';

@Injectable({ providedIn: 'root' })
export class UpdaterService {
  readonly available = signal<Update | null>(null);
  readonly status = signal<UpdateStatus>('idle');
  /** 0-100 while downloading, null when the size is unknown. */
  readonly progress = signal<number | null>(null);
  readonly error = signal<string | null>(null);
  readonly dismissed = signal(false);
  /** Result of the last manual check, e.g. "You're up to date." */
  readonly lastCheckMessage = signal<string | null>(null);

  /** Whether updating is possible here (it is not in browser dev mode). */
  readonly supported = isTauri();

  /** Looks for a newer release. Silent on failure at startup; a manual check reports errors. */
  async checkForUpdate(manual = false): Promise<void> {
    if (!this.supported) {
      this.lastCheckMessage.set('Updates are only available in the installed app.');
      return;
    }
    this.status.set('checking');
    this.error.set(null);
    try {
      const update = await check();
      this.available.set(update);
      this.dismissed.set(false);
      this.lastCheckMessage.set(update ? `Version ${update.version} is available.` : "You're up to date.");
      this.status.set('idle');
    } catch (error) {
      this.status.set('idle');
      if (manual) {
        this.error.set(`Could not check for updates: ${String(error)}`);
      } else {
        console.warn('Update check failed', error);
      }
    }
  }

  async install(): Promise<void> {
    const update = this.available();
    if (!update) {
      return;
    }
    this.status.set('downloading');
    this.progress.set(null);
    this.error.set(null);
    let total = 0;
    let downloaded = 0;
    try {
      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case 'Started':
            total = event.data.contentLength ?? 0;
            break;
          case 'Progress':
            downloaded += event.data.chunkLength;
            this.progress.set(total > 0 ? Math.min(100, Math.round((downloaded / total) * 100)) : null);
            break;
          case 'Finished':
            this.status.set('installing');
            break;
        }
      });
      await relaunch();
    } catch (error) {
      this.status.set('error');
      this.error.set(`The update failed: ${String(error)}`);
    }
  }

  dismiss(): void {
    this.dismissed.set(true);
  }
}
