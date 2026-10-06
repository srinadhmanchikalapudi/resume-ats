import { Injectable } from '@angular/core';
import { invoke, isTauri } from '@tauri-apps/api/core';

export interface BackendInfo {
  baseUrl: string;
  token: string | null;
}

/** Used in browser dev mode (`ng serve` + `python backend/run.py`), where there is no Tauri shell. */
const DEV_BACKEND: BackendInfo = { baseUrl: 'http://127.0.0.1:8000', token: null };

const READY_TIMEOUT_MS = 20_000;

/** Finds the local Python backend and waits until it answers, since the shell starts it in parallel with the UI. */
@Injectable({ providedIn: 'root' })
export class BackendService {
  private info?: Promise<BackendInfo>;

  resolve(): Promise<BackendInfo> {
    this.info ??= this.locate().then((info) => this.waitUntilReady(info));
    return this.info;
  }

  private async locate(): Promise<BackendInfo> {
    if (!isTauri()) {
      return DEV_BACKEND;
    }
    const { port, token } = await invoke<{ port: number; token: string }>('get_backend_info');
    return { baseUrl: `http://127.0.0.1:${port}`, token };
  }

  private async waitUntilReady(info: BackendInfo): Promise<BackendInfo> {
    const deadline = Date.now() + READY_TIMEOUT_MS;
    while (Date.now() < deadline) {
      try {
        const response = await fetch(`${info.baseUrl}/health`);
        if (response.ok) {
          return info;
        }
      } catch {
        // Not listening yet; retry.
      }
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    throw new Error('The local backend did not start. Please restart the app.');
  }
}
