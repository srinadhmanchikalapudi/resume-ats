import {
  Certification,
  Education,
  Experience,
  Link,
  Profile,
  Project,
  SkillGroup,
} from '../../core/models';

export function newId(): string {
  return crypto.randomUUID().replaceAll('-', '');
}

export const blankLink = (): Link => ({ label: '', url: '' });

export const blankExperience = (): Experience => ({
  id: newId(),
  title: '',
  company: '',
  location: '',
  start: '',
  end: '',
  current: false,
  bullets: [],
});

export const blankEducation = (): Education => ({
  id: newId(),
  school: '',
  degree: '',
  field: '',
  location: '',
  start: '',
  end: '',
  details: [],
});

export const blankSkillGroup = (): SkillGroup => ({ category: '', items: [] });

export const blankCertification = (): Certification => ({ id: newId(), name: '', issuer: '', date: '' });

export const blankProject = (): Project => ({
  id: newId(),
  name: '',
  description: '',
  url: '',
  tech: [],
  bullets: [],
});

export const blankProfile = (): Profile => ({
  contact: { name: '', email: '', phone: '', location: '', links: [] },
  summary: '',
  experience: [],
  education: [],
  skills: [],
  certifications: [],
  projects: [],
});

/** One list item per non-empty line (used for bullet editing in a textarea). */
export function linesToList(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export const listToLines = (items: string[]): string => items.join('\n');

/** Comma-separated text to a list (used for skills and tech). */
export function commaToList(text: string): string[] {
  return text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export const listToComma = (items: string[]): string => items.join(', ');

/** Moves an item up (-1) or down (+1); out-of-range moves are ignored. */
export function moveItem<T>(items: T[], index: number, delta: -1 | 1): void {
  const target = index + delta;
  if (target < 0 || target >= items.length) {
    return;
  }
  [items[index], items[target]] = [items[target], items[index]];
}

export function removeItem<T>(items: T[], index: number): void {
  items.splice(index, 1);
}

/** Whether the profile has any real content (used to decide between import and editor views). */
export function hasContent(profile: Profile): boolean {
  const { contact } = profile;
  return Boolean(
    contact.name ||
      contact.email ||
      profile.summary ||
      profile.experience.length ||
      profile.education.length ||
      profile.skills.length ||
      profile.certifications.length ||
      profile.projects.length,
  );
}
