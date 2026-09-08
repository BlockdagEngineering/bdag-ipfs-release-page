import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {assertDistribution, DOWNLOADS_SHA256} from '../releases/2.1.0-rc.2/assets/distribution.mjs';
const root = new URL('../releases/2.1.0-rc.2/', import.meta.url);
const release = JSON.parse(fs.readFileSync(new URL('records/release.json', root)));
const bytes = fs.readFileSync(new URL('install-v1/downloads.json', root));
const data = JSON.parse(bytes);
test('separate mirror metadata binds all original payloads without changing them', () => {
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), DOWNLOADS_SHA256);
  assert.equal(assertDistribution(data, release), data);
  assert.equal(data.files.filter(f => f.group === 'software').length, 26);
});
test('invalid mirror identity, destination, hash, URL or dataset assembly fails closed', () => {
  for (const mutate of [
    d => { d.original_release_sha256 = '0'.repeat(64); },
    d => { d.files[0].path = '../bad'; },
    d => { d.files.push(d.files[0]); },
    d => { d.files.find(f => f.path.startsWith('artifacts/')).sha256 = '0'.repeat(64); },
    d => { d.files[0].urls = ['https://evil.example/asset']; },
    d => { d.files.find(f => f.parts).parts.reverse(); },
    d => { d.files.find(f => f.parts).parts[0].bytes--; },
  ]) { const changed = structuredClone(data); mutate(changed); assert.throws(() => assertDistribution(changed, release)); }
});
