const assert = require('node:assert/strict');
const test = require('node:test');
const { validate } = require('../scripts/check_commit_messages');

test('accepts valid messages, optional scopes, and breaking changes', () => {
  for (const message of [
    'feat: add lobby timer',
    'fix(audio): handle silence\n\nExplain the change.',
    'feat(api)!: remove legacy endpoint\n\nBREAKING CHANGE: Old clients must update.',
  ]) {
    assert.deepEqual(validate(message), []);
  }
});

test('rejects non-ASCII text, invalid types and format, and long subjects', () => {
  for (const message of [
    'feat: 로비 타이머 추가',
    'fix: handle silence\n\n한글 본문',
    'feature: add lobby timer',
    'feat add lobby timer',
    'feat: ' + 'a'.repeat(67),
  ]) {
    assert.notEqual(validate(message).length, 0);
  }
});
