import { describe, expect, it } from 'vitest';
import { ApplicationStatus, ApplicationSummary, VersionOut } from '../../core/models';
import {
  baseName,
  daysUntil,
  formatDay,
  statusLabel,
  upcomingInterviews,
  versionFile,
  whenLabel,
} from './application-utils';

const TODAY = new Date(2026, 9, 6, 15, 30); // 6 Oct 2026, mid-afternoon

function app(id: number, interviewOn: string | null, status: ApplicationStatus = 'interviewing'): ApplicationSummary {
  return {
    id,
    company: `Co${id}`,
    title: 'Engineer',
    location: '',
    status,
    match_score: null,
    applied_on: null,
    interview_on: interviewOn,
    created_at: '',
    updated_at: '',
    version_count: 0,
    submitted_version: null,
  };
}

describe('daysUntil', () => {
  it('counts calendar days regardless of the time of day', () => {
    expect(daysUntil('2026-10-06', TODAY)).toBe(0);
    expect(daysUntil('2026-10-07', TODAY)).toBe(1);
    expect(daysUntil('2026-10-20', TODAY)).toBe(14);
    expect(daysUntil('2026-10-05', TODAY)).toBe(-1);
  });

  it('is null without a date', () => {
    expect(daysUntil(null, TODAY)).toBeNull();
  });

  it('handles month and year boundaries', () => {
    expect(daysUntil('2026-11-01', TODAY)).toBe(26);
    expect(daysUntil('2027-01-01', TODAY)).toBe(87);
  });
});

describe('whenLabel', () => {
  it.each([
    [0, 'today'],
    [1, 'tomorrow'],
    [5, 'in 5 days'],
    [-1, '1 day ago'],
    [-3, '3 days ago'],
  ])('describes %i as "%s"', (days, label) => {
    expect(whenLabel(days)).toBe(label);
  });
});

describe('upcomingInterviews', () => {
  it('keeps today and later, soonest first, and ignores undated ones', () => {
    const list = [app(1, '2026-12-01'), app(2, '2026-10-06'), app(3, null), app(4, '2026-10-01'), app(5, '2026-10-20')];
    expect(upcomingInterviews(list, TODAY).map((a) => a.id)).toEqual([2, 5, 1]);
  });

  it('skips applications that are already over', () => {
    const list = [app(1, '2026-10-10', 'rejected'), app(2, '2026-10-11', 'withdrawn'), app(3, '2026-10-12', 'offer')];
    expect(upcomingInterviews(list, TODAY).map((a) => a.id)).toEqual([3]);
  });
});

describe('formatting', () => {
  it('formats a day without shifting it across a time zone', () => {
    expect(formatDay('2026-10-06')).toContain('6');
    expect(formatDay('2026-10-06')).toContain('2026');
    expect(formatDay(null)).toBe('');
  });

  it('labels statuses', () => {
    expect(statusLabel('interviewing')).toBe('Interviewing');
    expect(statusLabel('withdrawn')).toBe('Withdrawn');
  });
});

describe('file helpers', () => {
  it('takes the file name from Windows and POSIX paths', () => {
    expect(baseName('C:\\Users\\J\\ResumeATS\\applications\\x\\v1\\Jane_Resume.pdf')).toBe('Jane_Resume.pdf');
    expect(baseName('/home/j/x/v2/Jane_Resume.docx')).toBe('Jane_Resume.docx');
  });

  it('exposes a version file with its name', () => {
    const version = {
      docx_path: 'C:\\a\\v1\\Jane_Resume.docx',
      pdf_path: 'C:\\a\\v1\\Jane_Resume.pdf',
    } as VersionOut;
    expect(versionFile(version, 'pdf')).toEqual({ path: 'C:\\a\\v1\\Jane_Resume.pdf', filename: 'Jane_Resume.pdf' });
    expect(versionFile(version, 'docx').filename).toBe('Jane_Resume.docx');
  });
});
