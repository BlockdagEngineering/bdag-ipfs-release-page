import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import {buildMirrorCommand} from '../releases/2.1.0-rc.2/assets/distribution.mjs';
import {ARCHITECTURES, COMPONENTS, selectArtifact} from '../releases/2.1.0-rc.2/assets/release.mjs';

const root = new URL('../releases/2.1.0-rc.2/', import.meta.url);
const read = (relative) => fs.readFileSync(new URL(relative, root), 'utf8');
const release = JSON.parse(read('records/release.json'));
const distribution = JSON.parse(read('install-v1/downloads.json'));

test('generated software commands are explicit HTTP/1.1 and non-clobbering for all selections', () => {
  for (const architecture of ARCHITECTURES) for (const component of COMPONENTS) {
    const artifact = selectArtifact(release, architecture, component);
    const file = distribution.files.find((entry) => entry.path === artifact.path && entry.sha256 === artifact.sha256);
    const command = buildMirrorCommand(file);
    assert.match(command, /\( set -eu/);
    assert.match(command, /curl --http1\.1 --fail --location --proto '=https' --proto-redir '=https'/);
    assert.match(command, /--max-filesize \d+ --output "\$partial"/);
    assert.match(command, /wc -c/);
    assert.match(command, /sha256sum -c/);
    assert.match(command, /mv -n/);
    assert.match(command, new RegExp(artifact.sha256));
    assert.match(command, new RegExp(artifact.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('publisher record binds original trust roots and excludes self-referential publication values', () => {
  const publisher = JSON.parse(read('install-v1/publisher.json'));
  assert.equal(publisher.publication.signature_status, 'absent/optional');
  assert.equal(publisher.publication.cryptographic_signature, false);
  assert.equal(publisher.publication.mandatory_account_or_approval, false);
  assert.equal(publisher.publication.authenticated_statement_issue, 'https://github.com/BlockdagEngineering/bdag-ipfs-release-page/issues/9');
  assert.equal(publisher.bindings.software_cid, release.software.cid);
  assert.equal(publisher.bindings.dataset_cid, release.dataset.cid);
  assert.equal(publisher.bindings.original_release_record_sha256, crypto.createHash('sha256').update(read('records/release.json')).digest('hex'));
  assert.equal(publisher.policy.rc65_migration, 'not_qualified');
  const serialized = JSON.stringify(publisher);
  assert.doesNotMatch(serialized, /page_cid|commit_sha256|publisher_json_sha256|companion_sha256/i);
});

test('guides disclose protocol limits, trust separation and unqualified migration', () => {
  const page = read('index.html');
  const companion = read('install-v1/index.html');
  const downloads = read('install-v1/DOWNLOADS.md');
  const migration = read('install-v1/MIGRATION.md');
  const ai = read('install-v1/MIGRATION-AGENTS.md');
  for (const text of [page, companion, downloads]) {
    assert.match(text, /HTTP\/1\.1/);
    assert.match(text, /browser[^.]*cannot force/i);
    assert.match(text, /https:\/\/blockdagengineering\.github\.io/);
  }
  assert.match(migration, /NOT QUALIFIED/);
  assert.match(ai, /NOT QUALIFIED/);
  assert.match(page, /MIGRATION\.html/);
  assert.match(page, /MIGRATION-AGENTS\.html/);
});

test('bootstrap examples pin only fetched execution inputs and page wiring keeps browser controls distinct', () => {
  const install = read('install-v1/INSTALL.md');
  const downloads = read('install-v1/DOWNLOADS.md');
  for (const text of [install, downloads]) {
    assert.doesNotMatch(text, /< COMPANION-SHA256SUMS/);
    assert.match(text, /57580591bb62ef724f66fddca0f050c9610843103c724d1c09cc2f6357099174/);
    assert.match(text, /54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c/);
    assert.match(text, /if \[ -e \"\$name\" \] \|\| \[ -L \"\$name\" \]/);
    assert.match(text, /mv -n/);
  }
  const page = read('index.html');
  const js = read('assets/release.mjs');
  const companion = read('install-v1/index.html');
  const downloadsHtml = read('install-v1/DOWNLOADS.html');
  assert.match(page, /Primary HTTPS IPFS browser convenience/);
  assert.match(page, /Native IPFS link \(IPFS client\)/);
  assert.match(companion, /DOWNLOADS\.html#optional-dataset-one-snapshot-in-thirteen-ordered-parts/);
  assert.match(downloadsHtml, /id="optional-dataset-one-snapshot-in-thirteen-ordered-parts"/);
  assert.doesNotMatch(companion, /optional-dataset-resumable-in-13-parts/);
  assert.match(js, /component\.dispatchEvent\(new Event\('change'\)\)/);
  assert.match(js, /value\.includes\('curl --http1\.1'\)/);
  assert.ok(js.includes('wc -c < \\"$SNAP\\"'));
});
