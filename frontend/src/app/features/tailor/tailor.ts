import { Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DroppedBullet, ResumeLength, SkillGroup } from '../../core/models';
import { JobAnalysisState } from '../jobs/job-analysis.state';
import { commaToList, listToComma, moveItem } from '../profile/profile-utils';
import { TailorState } from './tailor.state';
import { EditableBullet, EditableRole, addBack, textState, toPlainText, toProfile } from './tailor-utils';

interface LengthOption {
  value: ResumeLength;
  label: string;
  hint: string;
}

@Component({
  selector: 'app-tailor',
  imports: [FormsModule, RouterLink],
  templateUrl: './tailor.html',
  styleUrl: './tailor.scss',
})
export class TailorPage {
  protected readonly jobs = inject(JobAnalysisState);
  protected readonly state = inject(TailorState);

  protected readonly lengths: LengthOption[] = [
    { value: 'concise', label: 'Concise', hint: 'About one page: 5, 4, then 3 bullets per role' },
    { value: 'standard', label: 'Standard', hint: 'About two pages: 8, 6, 5, then 4 bullets per role' },
    { value: 'full', label: 'Full', hint: 'Every bullet, reordered by relevance' },
  ];

  protected readonly copied = signal(false);
  private readonly previewBox = viewChild<ElementRef<HTMLTextAreaElement>>('previewBox');

  protected readonly job = computed(() => this.jobs.result()?.job ?? null);
  protected readonly textState = textState;
  protected readonly listToComma = listToComma;

  protected generate(): Promise<void> {
    this.copied.set(false);
    return this.state.generate();
  }

  protected useOriginal(item: { original: string; text: string }): void {
    item.text = item.original;
  }

  protected useProposed(item: { proposed: string; text: string }): void {
    item.text = item.proposed;
  }

  protected move(role: EditableRole, index: number, delta: -1 | 1): void {
    moveItem(role.bullets, index, delta);
  }

  protected restore(role: EditableRole, dropped: DroppedBullet): void {
    addBack(role, dropped);
  }

  protected setSkills(group: SkillGroup, text: string): void {
    group.items = commaToList(text);
  }

  protected rowsFor(text: string): number {
    return Math.max(2, Math.ceil(text.length / 95));
  }

  protected includedCount(role: EditableRole): number {
    return role.bullets.filter((bullet: EditableBullet) => bullet.included).length;
  }

  /** The finished resume as plain text. Recomputed on every change detection pass, which is cheap here. */
  protected preview(): string {
    const resume = this.state.resume();
    return resume ? toPlainText(toProfile(resume)) : '';
  }

  protected async copy(): Promise<void> {
    const text = this.preview();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // The clipboard API is unavailable in some webview contexts; fall back to the selection copy command.
      const box = this.previewBox()?.nativeElement;
      box?.select();
      document.execCommand('copy');
    }
    this.copied.set(true);
  }
}
