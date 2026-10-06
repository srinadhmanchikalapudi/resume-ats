import { Component, inject } from '@angular/core';
import { UpdaterService } from '../core/updater.service';

/** Offers "Update / Later" when a newer release is published. */
@Component({
  selector: 'app-update-banner',
  template: `
    @if (updater.available(); as update) {
      @if (!updater.dismissed() || updater.status() !== 'idle') {
        <div class="banner" role="status">
          @switch (updater.status()) {
            @case ('downloading') {
              <span>
                Downloading version {{ update.version }}…
                @if (updater.progress() !== null) {
                  {{ updater.progress() }}%
                }
              </span>
            }
            @case ('installing') {
              <span>Installing version {{ update.version }}. The app will restart.</span>
            }
            @default {
              <span>Version {{ update.version }} is available.</span>
              <span class="actions">
                <button type="button" class="primary" (click)="updater.install()">Update</button>
                <button type="button" (click)="updater.dismiss()">Later</button>
              </span>
            }
          }
          @if (updater.error(); as text) {
            <span class="error">{{ text }}</span>
          }
        </div>
      }
    }
  `,
  styles: `
    .banner {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 24px;
      background: var(--accent-soft);
      border-bottom: 1px solid var(--border);
    }

    .actions {
      display: flex;
      gap: 8px;
    }

    .error {
      flex-basis: 100%;
      color: var(--error);
      font-size: 0.9rem;
    }
  `,
})
export class UpdateBanner {
  protected readonly updater = inject(UpdaterService);
}
