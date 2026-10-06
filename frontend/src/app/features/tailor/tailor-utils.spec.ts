import { describe, expect, it } from 'vitest';
import { Flag, TailoredResume } from '../../core/models';
import { addBack, defaultText, textState, toEditable, toPlainText, toProfile } from './tailor-utils';

const review: Flag = { kind: 'review', message: 'check' };
const reverted: Flag = { kind: 'reverted', message: 'no' };

function tailored(): TailoredResume {
  return {
    contact: { name: 'Jane Doe', email: 'jane@example.com', phone: '', location: 'Austin, TX', links: [] },
    summary: { original: 'Old summary.', proposed: 'New summary.', flags: [] },
    roles: [
      {
        id: 'r1',
        title: 'Senior Engineer',
        company: 'Acme',
        location: '',
        start: '2020',
        end: '',
        current: true,
        bullets: [
          { source: 2, original: 'Built an API.', proposed: 'Built a REST API.', flags: [] },
          { source: 1, original: 'Wrote docs.', proposed: 'Wrote docs.', flags: [] },
          { source: 3, original: 'Ran jobs.', proposed: 'Ran queue jobs.', flags: [review] },
        ],
        dropped: [{ source: 4, original: 'Fixed printers.' }],
      },
    ],
    skills: [{ category: 'Languages', items: ['C#', 'Python'] }],
    education: [],
    certifications: [],
    projects: [],
    warnings: [],
  };
}

describe('defaultText', () => {
  it('uses a clean rewrite', () => {
    expect(defaultText('a', 'b', [])).toBe('b');
  });

  it('starts from the original when the rewrite needs review', () => {
    expect(defaultText('a', 'b', [review])).toBe('a');
  });

  it('keeps the original when nothing changed or the rewrite was reverted', () => {
    expect(defaultText('a', 'a', [])).toBe('a');
    expect(defaultText('a', 'a', [reverted])).toBe('a');
  });
});

describe('toEditable', () => {
  it('applies safe defaults per bullet and the summary', () => {
    const resume = toEditable(tailored());
    expect(resume.summary.text).toBe('New summary.');
    expect(resume.roles[0].bullets.map((b) => b.text)).toEqual(['Built a REST API.', 'Wrote docs.', 'Ran jobs.']);
    expect(resume.roles[0].bullets.every((b) => b.included)).toBe(true);
  });

  it('gives every bullet a unique key', () => {
    const keys = toEditable(tailored()).roles[0].bullets.map((b) => b.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe('textState', () => {
  it('reports which version the text currently is', () => {
    const item = { original: 'a', proposed: 'b', text: 'a' };
    expect(textState(item)).toBe('original');
    expect(textState({ ...item, text: 'b' })).toBe('proposed');
    expect(textState({ ...item, text: 'my own' })).toBe('edited');
  });
});

describe('addBack', () => {
  it('moves a left-out bullet into the role with the original wording', () => {
    const resume = toEditable(tailored());
    const role = resume.roles[0];
    addBack(role, role.dropped[0]);
    expect(role.dropped).toEqual([]);
    expect(role.bullets.at(-1)).toMatchObject({ text: 'Fixed printers.', included: true, source: 4 });
  });
});

describe('toProfile', () => {
  it('exports only included, non-empty bullets in order, with trimmed text', () => {
    const resume = toEditable(tailored());
    resume.roles[0].bullets[1].included = false;
    resume.roles[0].bullets[2].text = '   ';
    resume.summary.text = '  Edited summary.  ';
    const profile = toProfile(resume);
    expect(profile.experience[0].bullets).toEqual(['Built a REST API.']);
    expect(profile.summary).toBe('Edited summary.');
    expect(profile.skills).toEqual([{ category: 'Languages', items: ['C#', 'Python'] }]);
  });

  it('drops skill groups that have no items', () => {
    const resume = toEditable(tailored());
    resume.skills.push({ category: 'Empty', items: [] });
    expect(toProfile(resume).skills.map((g) => g.category)).toEqual(['Languages']);
  });
});

describe('toPlainText', () => {
  it('renders a single-column resume with standard headings', () => {
    const text = toPlainText(toProfile(toEditable(tailored())));
    expect(text.split('\n')).toEqual([
      'JANE DOE',
      'jane@example.com | Austin, TX',
      '',
      'SUMMARY',
      'New summary.',
      '',
      'EXPERIENCE',
      'Senior Engineer, Acme',
      '2020 - Present',
      '- Built a REST API.',
      '- Wrote docs.',
      '- Ran jobs.',
      '',
      'SKILLS',
      'Languages: C#, Python',
    ]);
  });

  it('omits sections that are empty', () => {
    const resume = toEditable(tailored());
    resume.summary.text = '';
    resume.skills = [];
    const text = toPlainText(toProfile(resume));
    expect(text).not.toContain('SUMMARY');
    expect(text).not.toContain('SKILLS');
    expect(text).toContain('EXPERIENCE');
  });
});
