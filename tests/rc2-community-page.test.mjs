import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import test from 'node:test';
import {
  ARCHITECTURES,
  COMPONENTS,
  assertRelease,
  buildVerifyCommand,
  copyText,
  gatewayDatasetUrl,
  nativeDatasetUrl,
  selectArtifact,
} from '../releases/2.1.0-rc.2/assets/release.mjs';

const page = new URL('../releases/2.1.0-rc.2/', import.meta.url);
const read = (relative) => fs.readFileSync(new URL(relative, page));
const recordBytes = read('records/release.json');
const record = JSON.parse(recordBytes);

test('frozen RC2 records and binding remain byte-identical', () => {
  const expected = {
    'records/bootstrap-peers.json': 'c5c6c63412156ef03380c4a926bf8b5139dc0791957351255e0b6a30e75c0166',
    'records/dataset-acceptance.json': '235135c30a111b62b9b7115e84499c06620052917810e19c83b64e4b1f8a1852',
    'records/mining-acceptance.json': 'd29cc56572a4ce1598c82222a9da22fed7ab10ed87fee21ea6ebedd88d91f05b',
    'records/release.json': '468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2',
    'records/software-SHA256SUMS': '233ac434c70efa6f928ddb1ceb21bb4862cba73ef1bd27ca918ea17370620c3b',
    'assets/record-binding.mjs': '380d9f3ba1f22754329ffde643ba815e709419bee23ea95199aa0da327e01dba',
  };
  for (const [relative, expectedSha] of Object.entries(expected)) assert.equal(crypto.createHash('sha256').update(read(relative)).digest('hex'), expectedSha, relative);
  assert.equal(assertRelease(record).version, '2.1.0-rc.2');
});

test('finite artifact selections and dataset URLs derive from the release record', () => {
  assert.deepEqual(ARCHITECTURES, ['linux-amd64', 'linux-arm64']);
  assert.deepEqual(COMPONENTS, ['full-stack', 'corechain', 'pool', 'dashboard', 'stack']);
  for (const architecture of ARCHITECTURES) for (const component of COMPONENTS) {
    const artifact = selectArtifact(record, architecture, component);
    assert.ok(artifact, `${architecture}/${component}`);
    assert.match(buildVerifyCommand(record, artifact), new RegExp(`/ipfs/${record.software.cid}/${artifact.path}`));
  }
  assert.equal(selectArtifact(record, 'linux-mips', 'corechain'), null);
  assert.equal(selectArtifact(record, 'linux-amd64', 'wallet'), null);
  assert.equal(nativeDatasetUrl(record, record.dataset.name), `ipfs://${record.dataset.cid}/${record.dataset.name}`);
  assert.equal(gatewayDatasetUrl(record, record.dataset.name), `https://dweb.link/ipfs/${record.dataset.cid}/${record.dataset.name}`);
});

test('dataset guidance is download and checksum only', () => {
  const html = read('index.html').toString();
  const js = read('assets/release.mjs').toString();
  assert(!html.includes('snap import'));
  assert(!html.includes('snap verify'));
  assert(!js.includes('snap import'));
  assert(!js.includes('snap verify'));
  assert.match(js, /ipfs get \/ipfs\/\$\{data\.cid\}/);
  assert.match(js, /sha256sum -c/);
});

test('invalid record data and clipboard denial fail closed', async () => {
  for (const patch of [{branch: 'main'}, {chain_id: 1}, {dataset: null}]) assert.throws(() => assertRelease({...record, ...patch}));
  assert.equal(await copyText('stale command', null), false);
  assert.equal(await copyText('stale command', {writeText: async () => { throw new Error('denied'); }}), false);
});

test('presentation starts guarded and exposes stable browser selectors', () => {
  const html = read('index.html').toString();
  for (const id of ['record-status', 'architecture', 'component', 'download-command', 'copy-command', 'artifact-grid', 'copy-status', 'dataset-status', 'dataset-command', 'qualification-status']) assert(html.includes(`id="${id}"`), id);
  assert(html.includes('id="native-download"') && html.includes('disabled'));
  assert(html.includes('id="gateway-download"') && html.includes('disabled'));
  assert(!/id="(?:wallet|mac|data-dir|download-dir)"/i.test(html));
});
