import { describe, expect, it } from 'vitest';
import {
  blankExperience,
  blankProfile,
  commaToList,
  hasContent,
  linesToList,
  listToComma,
  listToLines,
  moveItem,
  newId,
  removeItem,
} from './profile-utils';

describe('list <-> text helpers', () => {
  it('splits lines, trimming and dropping blanks', () => {
    expect(linesToList('  Built an API \r\n\n Cut costs 30%\n')).toEqual(['Built an API', 'Cut costs 30%']);
    expect(linesToList('')).toEqual([]);
  });

  it('round-trips bullets', () => {
    const bullets = ['One', 'Two'];
    expect(linesToList(listToLines(bullets))).toEqual(bullets);
  });

  it('splits comma lists', () => {
    expect(commaToList('Python, C# ,, Azure ')).toEqual(['Python', 'C#', 'Azure']);
    expect(listToComma(['Python', 'C#'])).toBe('Python, C#');
  });
});

describe('list editing', () => {
  it('moves items and ignores out-of-range moves', () => {
    const items = ['a', 'b', 'c'];
    moveItem(items, 1, -1);
    expect(items).toEqual(['b', 'a', 'c']);
    moveItem(items, 0, -1);
    moveItem(items, 2, 1);
    expect(items).toEqual(['b', 'a', 'c']);
  });

  it('removes an item', () => {
    const items = ['a', 'b', 'c'];
    removeItem(items, 1);
    expect(items).toEqual(['a', 'c']);
  });
});

describe('profile helpers', () => {
  it('generates unique ids', () => {
    expect(newId()).not.toBe(newId());
    expect(blankExperience().id).toMatch(/^[0-9a-f]{32}$/);
  });

  it('detects whether a profile has content', () => {
    const profile = blankProfile();
    expect(hasContent(profile)).toBe(false);
    profile.contact.name = 'Jane';
    expect(hasContent(profile)).toBe(true);
    expect(hasContent({ ...blankProfile(), experience: [blankExperience()] })).toBe(true);
  });
});
