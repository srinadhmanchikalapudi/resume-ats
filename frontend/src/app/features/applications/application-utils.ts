import { ApplicationStatus, ApplicationSummary, VersionOut } from '../../core/models';

export interface StatusOption {
  value: ApplicationStatus;
  label: string;
}

export const STATUS_OPTIONS: StatusOption[] = [
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'screening', label: 'Screening' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

export function statusLabel(status: ApplicationStatus): string {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

/** Parses a YYYY-MM-DD string as a local date (new Date('2026-10-06') would be UTC and can shift a day). */
function parseDay(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function formatDay(iso: string | null): string {
  return iso ? parseDay(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** Whole days from `today` to the given day: 0 is today, negative is in the past. */
export function daysUntil(iso: string | null, today: Date = new Date()): number | null {
  if (!iso) {
    return null;
  }
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((parseDay(iso).getTime() - start.getTime()) / 86_400_000);
}

export function whenLabel(days: number): string {
  if (days === 0) {
    return 'today';
  }
  if (days === 1) {
    return 'tomorrow';
  }
  return days > 0 ? `in ${days} days` : `${-days} day${days === -1 ? '' : 's'} ago`;
}

/** Applications with an interview today or later, soonest first. Finished ones (rejected, withdrawn) are skipped. */
export function upcomingInterviews(
  applications: ApplicationSummary[],
  today: Date = new Date(),
): ApplicationSummary[] {
  return applications
    .filter((a) => a.status !== 'rejected' && a.status !== 'withdrawn')
    .filter((a) => (daysUntil(a.interview_on, today) ?? -1) >= 0)
    .sort((a, b) => (a.interview_on ?? '').localeCompare(b.interview_on ?? ''));
}

export function baseName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

/** A version's DOCX or PDF in the shape the file-opening helper expects. */
export function versionFile(version: VersionOut, kind: 'docx' | 'pdf'): { path: string; filename: string } {
  const path = kind === 'docx' ? version.docx_path : version.pdf_path;
  return { path, filename: baseName(path) };
}
