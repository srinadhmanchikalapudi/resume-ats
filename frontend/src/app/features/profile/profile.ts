import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/errors';
import { Check, Experience, ImportResult, Profile } from '../../core/models';
import { HealthPanel } from '../health/health-panel';
import {
  blankCertification,
  blankEducation,
  blankExperience,
  blankLink,
  blankProfile,
  blankProject,
  blankSkillGroup,
  commaToList,
  hasContent,
  linesToList,
  listToComma,
  listToLines,
  moveItem,
  removeItem,
} from './profile-utils';

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];

@Component({
  selector: 'app-profile',
  imports: [FormsModule, RouterLink, HealthPanel],
  templateUrl: './profile.html',
  styleUrl: './profile.scss',
})
export class ProfilePage implements OnInit {
  private readonly api = inject(ApiService);

  /** The profile being edited. Fields are edited in place through ngModel. */
  protected readonly profile = signal<Profile>(blankProfile());
  protected readonly loading = signal(true);
  protected readonly editing = signal(false);
  protected readonly showImport = signal(false);
  protected readonly dirty = signal(false);
  protected readonly savedAt = signal<string | null>(null);
  protected readonly isDraft = signal(false);
  protected readonly warnings = signal<string[]>([]);
  protected readonly fileChecks = signal<Check[]>([]);
  protected readonly importing = signal(false);
  protected readonly saving = signal(false);
  protected readonly dragging = signal(false);
  protected readonly pasteText = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly saveNotice = signal<string | null>(null);
  private readonly hasKey = signal(false);
  private readonly hasModel = signal(false);

  protected readonly needsSetup = computed(() => !this.hasKey() || !this.hasModel());
  /** What the health panel checks: the profile as it is in the editor right now, saved or not. */
  protected readonly healthSource = (): Profile => this.profile();
  protected readonly healthSnapshot = (): string => JSON.stringify(this.healthSource());

  protected readonly savedLabel = computed(() => {
    const value = this.savedAt();
    return value ? `Last saved ${new Date(value).toLocaleString()}` : 'Not saved yet';
  });

  // Template helpers
  protected readonly blankLink = blankLink;
  protected readonly blankExperience = blankExperience;
  protected readonly blankEducation = blankEducation;
  protected readonly blankSkillGroup = blankSkillGroup;
  protected readonly blankCertification = blankCertification;
  protected readonly blankProject = blankProject;
  protected readonly linesToList = linesToList;
  protected readonly listToLines = listToLines;
  protected readonly commaToList = commaToList;
  protected readonly listToComma = listToComma;

  async ngOnInit(): Promise<void> {
    try {
      const [saved, settings] = await Promise.all([
        firstValueFrom(this.api.getProfile()),
        firstValueFrom(this.api.getSettings()),
      ]);
      this.hasKey.set(settings.has_api_key);
      this.hasModel.set(Boolean(settings.extraction_model || settings.model));
      if (saved.exists) {
        this.profile.set(saved.profile);
        this.savedAt.set(saved.updated_at);
        this.editing.set(true);
      }
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  // --- import -------------------------------------------------------------------------------

  protected onFileChosen(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // allow choosing the same file again
    if (file) {
      void this.importFile(file);
    }
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files[0];
    if (file) {
      void this.importFile(file);
    }
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected importFile(file: File): Promise<void> {
    const name = file.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
      this.error.set('Use a PDF, DOCX or plain-text file.');
      return Promise.resolve();
    }
    return this.runImport(() => firstValueFrom(this.api.importResumeFile(file)));
  }

  protected importPasted(): Promise<void> {
    return this.runImport(() => firstValueFrom(this.api.importResumeText(this.pasteText())));
  }

  private async runImport(call: () => Promise<ImportResult>): Promise<void> {
    this.importing.set(true);
    this.error.set(null);
    this.saveNotice.set(null);
    try {
      const result = await call();
      this.profile.set(result.profile);
      this.warnings.set(result.warnings);
      this.fileChecks.set(result.file_checks ?? []);
      this.isDraft.set(true);
      this.dirty.set(true);
      this.editing.set(true);
      this.showImport.set(false);
      this.pasteText.set('');
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.importing.set(false);
    }
  }

  protected startBlank(): void {
    this.profile.set(blankProfile());
    this.editing.set(true);
  }

  // --- editing ------------------------------------------------------------------------------

  protected markDirty(): void {
    this.dirty.set(true);
    this.saveNotice.set(null);
  }

  protected add<T>(items: T[], factory: () => T): void {
    items.push(factory());
    this.markDirty();
  }

  protected remove<T>(items: T[], index: number): void {
    removeItem(items, index);
    this.markDirty();
  }

  protected move<T>(items: T[], index: number, delta: -1 | 1): void {
    moveItem(items, index, delta);
    this.markDirty();
  }

  /** A current role has no end date; clear any old one so it is not saved invisibly. */
  protected setCurrent(role: Experience, current: boolean): void {
    role.current = current;
    if (current) {
      role.end = '';
    }
    this.markDirty();
  }

  protected rowsFor(items: string[]): number {
    return Math.max(3, items.length + 1);
  }

  protected hasContent(): boolean {
    return hasContent(this.profile());
  }

  // --- saving -------------------------------------------------------------------------------

  protected async save(): Promise<void> {
    this.saving.set(true);
    this.error.set(null);
    try {
      const saved = await firstValueFrom(this.api.saveProfile(this.profile()));
      this.profile.set(saved.profile);
      this.savedAt.set(saved.updated_at);
      this.dirty.set(false);
      this.isDraft.set(false);
      this.warnings.set([]);
      this.fileChecks.set([]);
      this.saveNotice.set('Profile saved.');
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.saving.set(false);
    }
  }

  /** Throws away unsaved edits and reloads the saved profile. */
  protected async discard(): Promise<void> {
    try {
      const saved = await firstValueFrom(this.api.getProfile());
      this.profile.set(saved.profile);
      this.savedAt.set(saved.updated_at);
      this.editing.set(saved.exists);
      this.dirty.set(false);
      this.isDraft.set(false);
      this.warnings.set([]);
      this.fileChecks.set([]);
      this.saveNotice.set(null);
    } catch (error) {
      this.error.set(errorMessage(error));
    }
  }
}
