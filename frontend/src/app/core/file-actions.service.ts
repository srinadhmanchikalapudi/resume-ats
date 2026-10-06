import { Injectable, inject } from '@angular/core';
import { isTauri } from '@tauri-apps/api/core';
import { openPath } from '@tauri-apps/plugin-opener';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { ExportedFile } from './models';

/**
 * Opens exported files. In the desktop app they open in the user's own programs (Word, a PDF viewer) and the
 * folder opens in Finder or Explorer. In browser dev mode there is no such shell, so the file is downloaded.
 *
 * The desktop app may only open paths inside its own data folder (see src-tauri/capabilities/default.json).
 */
@Injectable({ providedIn: 'root' })
export class FileActions {
  private readonly api = inject(ApiService);

  /** Whether files and folders can be opened in place (desktop app) rather than downloaded. */
  readonly canOpenInPlace = isTauri();

  async open(file: ExportedFile): Promise<void> {
    if (this.canOpenInPlace) {
      await openPath(file.path);
      return;
    }
    await this.download(file);
  }

  async openFolder(folder: string): Promise<void> {
    if (this.canOpenInPlace) {
      await openPath(folder);
    }
  }

  private async download(file: ExportedFile): Promise<void> {
    const blob = await firstValueFrom(this.api.downloadExport(file.path));
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
