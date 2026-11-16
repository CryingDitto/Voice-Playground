#!/usr/bin/env node
// Shared validator for the commit-msg hook and GitHub Actions.
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');

const initialCommit = 'a3a3183';
const subjectPattern = /^(feat|fix|refactor|perf|test|docs|build|ci|chore|revert)(\([a-z0-9][a-z0-9._/-]*\))?!?: \S.*$/;

function validate(message) {
  const subject = message.split(/\r?\n/, 1)[0];
  const errors = [];
  if (!/^[\x00-\x7F]*$/.test(message)) {
    errors.push('the whole message must use ASCII characters');
  }
  if (subject.length > 72) {
    errors.push('the subject must be at most 72 characters');
  }
  if (!subjectPattern.test(subject)) {
    errors.push('the subject must use an allowed Conventional Commit type and format');
  }
  return errors;
}

function git(...args) {
  return execFileSync('git', args, { encoding: 'utf8' });
}

function main(args) {
  if (args.length !== 2 || !['--message-file', '--range'].includes(args[0])) {
    console.error('Usage: node scripts/check_commit_messages.js (--message-file FILE | --range BASE..HEAD)');
    return 2;
  }
  const items = [];
  if (args[0] === '--message-file') {
    items.push([args[1], fs.readFileSync(args[1], 'utf8').replace(/^\uFEFF/, '')]);
  } else {
    const commits = git('rev-list', '--reverse', args[1]).trim().split('\n').filter(Boolean);
    for (const sha of commits) {
      if (sha.startsWith(initialCommit)) continue;
      if (git('show', '-s', '--format=%P', sha).trim().split(/\s+/).length > 1) continue;
      items.push([sha.slice(0, 12), git('show', '-s', '--format=%B', sha)]);
    }
  }
  let failed = false;
  for (const [name, message] of items) {
    const errors = validate(message);
    for (const error of errors) {
      console.error(`${name}: ${error}`);
      failed = true;
    }
    if (!errors.length) console.log(`${name}: valid`);
  }
  return Number(failed);
}

if (require.main === module) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 2;
  }
}

module.exports = { validate };
