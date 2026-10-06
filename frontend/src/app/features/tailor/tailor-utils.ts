import {
  Certification,
  Contact,
  DroppedBullet,
  Education,
  Flag,
  Profile,
  Project,
  SkillGroup,
  TailoredBullet,
  TailoredResume,
  TailoredRole,
} from '../../core/models';

/** A bullet in the editor: the model's proposal plus what the user has chosen to keep. */
export interface EditableBullet extends TailoredBullet {
  key: string;
  text: string;
  included: boolean;
}

export interface EditableRole extends Omit<TailoredRole, 'bullets'> {
  bullets: EditableBullet[];
}

export interface EditableResume {
  contact: Contact;
  summary: { original: string; proposed: string; flags: Flag[]; text: string };
  roles: EditableRole[];
  skills: SkillGroup[];
  education: Education[];
  certifications: Certification[];
  projects: Project[];
  warnings: string[];
}

export type TextState = 'original' | 'proposed' | 'edited';

/**
 * What an item starts as. A rewrite is only pre-selected when it came back clean; anything the server
 * flagged for review starts as the user's original wording and has to be opted into.
 */
export function defaultText(original: string, proposed: string, flags: Flag[]): string {
  const needsReview = flags.some((flag) => flag.kind === 'review');
  return proposed !== original && !needsReview ? proposed : original;
}

export function textState(item: { original: string; proposed: string; text: string }): TextState {
  if (item.text === item.original) {
    return 'original';
  }
  return item.text === item.proposed ? 'proposed' : 'edited';
}

let counter = 0;
const nextKey = (): string => `b${++counter}`;

export function toEditable(tailored: TailoredResume): EditableResume {
  return {
    contact: tailored.contact,
    summary: {
      ...tailored.summary,
      text: defaultText(tailored.summary.original, tailored.summary.proposed, tailored.summary.flags),
    },
    roles: tailored.roles.map((role) => ({
      ...role,
      bullets: role.bullets.map((bullet) => ({
        ...bullet,
        key: nextKey(),
        text: defaultText(bullet.original, bullet.proposed, bullet.flags),
        included: true,
      })),
    })),
    skills: tailored.skills,
    education: tailored.education,
    certifications: tailored.certifications,
    projects: tailored.projects,
    warnings: tailored.warnings,
  };
}

/** Moves a left-out bullet back into the role, using the user's own wording. */
export function addBack(role: EditableRole, dropped: DroppedBullet): void {
  role.dropped = role.dropped.filter((item) => item.source !== dropped.source);
  role.bullets.push({
    source: dropped.source,
    original: dropped.original,
    proposed: dropped.original,
    flags: [],
    key: nextKey(),
    text: dropped.original,
    included: true,
  });
}

/** The resume as it will be exported: only included, non-empty bullets, in the chosen order. */
export function toProfile(resume: EditableResume): Profile {
  return {
    contact: resume.contact,
    summary: resume.summary.text.trim(),
    experience: resume.roles.map((role) => ({
      id: role.id,
      title: role.title,
      company: role.company,
      location: role.location,
      start: role.start,
      end: role.end,
      current: role.current,
      bullets: role.bullets.filter((b) => b.included && b.text.trim()).map((b) => b.text.trim()),
    })),
    education: resume.education,
    skills: resume.skills.filter((group) => group.items.length > 0),
    certifications: resume.certifications,
    projects: resume.projects,
  };
}

function dateRange(start: string, end: string, current: boolean): string {
  const last = current && !end ? 'Present' : end;
  return [start, last].filter(Boolean).join(' - ');
}

/**
 * Plain, ATS-friendly text rendering: single column, standard headings, simple bullets.
 * Section order matches the exported files; `skillsFirst` puts Skills before Experience.
 */
export function toPlainText(profile: Profile, skillsFirst = true): string {
  const lines: string[] = [];
  const { contact } = profile;

  if (contact.name) {
    lines.push(contact.name.toUpperCase());
  }
  const contactLine = [contact.email, contact.phone, contact.location, ...contact.links.map((l) => l.url)]
    .filter(Boolean)
    .join(' | ');
  if (contactLine) {
    lines.push(contactLine);
  }

  const section = (title: string, body: string[]): void => {
    if (body.length > 0) {
      lines.push('', title, ...body);
    }
  };

  const skills = (): void =>
    section(
      'SKILLS',
      profile.skills
        .filter((group) => group.items.length > 0)
        .map((group) =>
          group.category ? `${group.category}: ${group.items.join(', ')}` : group.items.join(', '),
        ),
    );

  const experience = (): void =>
    section(
      'EXPERIENCE',
      profile.experience.flatMap((role, index) => [
        ...(index > 0 ? [''] : []),
        [role.title, role.company].filter(Boolean).join(', ') +
          (role.location ? `, ${role.location}` : ''),
        dateRange(role.start, role.end, role.current),
        ...role.bullets.map((bullet) => `- ${bullet}`),
      ]),
    );

  section('SUMMARY', profile.summary ? [profile.summary] : []);
  if (skillsFirst) {
    skills();
    experience();
  } else {
    experience();
    skills();
  }

  section(
    'EDUCATION',
    profile.education.map((edu) =>
      [
        [edu.degree, edu.field].filter(Boolean).join(', '),
        edu.school,
        dateRange(edu.start, edu.end, false),
      ]
        .filter(Boolean)
        .join(' - '),
    ),
  );

  section(
    'CERTIFICATIONS',
    profile.certifications.map((c) => [c.name, c.issuer, c.date].filter(Boolean).join(' - ')),
  );

  section(
    'PROJECTS',
    profile.projects.flatMap((p) => [
      [p.name, p.description].filter(Boolean).join(': '),
      ...p.bullets.map((bullet) => `- ${bullet}`),
    ]),
  );

  return lines.join('\n');
}
