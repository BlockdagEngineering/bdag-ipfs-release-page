import {RECORD_SHA256} from './record-binding.mjs';

export const DOWNLOADS_SHA256 = '54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c';
const ROOT = 'https://github.com/BlockdagEngineering/bdag-ipfs-release-page/releases/download/jeremy%2Fdistribution%2F2.1.0-rc.2-install-v1/';
const hex = bytes => [...new Uint8Array(bytes)].map(n => n.toString(16).padStart(2, '0')).join('');

export function assertDistribution(value, release) {
  if (value?.schema !== 'blockdag.downloads/v1' || value.version !== release.version ||
      value.original_release_sha256 !== RECORD_SHA256 || value.software_cid !== release.software.cid ||
      value.dataset_cid !== release.dataset.cid || !Array.isArray(value.files)) throw new Error('Distribution identity mismatch');
  const seen = new Set();
  for (const file of value.files) {
    if (!/^[\w.-]+(?:\/[\w.-]+)*$/.test(file.path) || file.path.split('/').some(p => p === '..' || p === '.') ||
        seen.has(file.path) || !/^[0-9a-f]{64}$/.test(file.sha256) || !Number.isSafeInteger(file.bytes) || file.bytes <= 0) throw new Error('Invalid distribution file');
    seen.add(file.path);
    for (const u of [...(file.urls ?? []), ...(file.parts ?? []).flatMap(p => p.urls)]) {
      if (!u.startsWith(ROOT) || new URL(u).search || new URL(u).hash || u.slice(ROOT.length).includes('/')) throw new Error('Unexpected mirror URL');
    }
  }
  for (const artifact of release.software.artifacts) {
    const file = value.files.find(f => f.path === artifact.path);
    if (!file || file.sha256 !== artifact.sha256 || file.bytes !== artifact.bytes || file.urls.length !== 1 ||
        file.ipfs !== `/ipfs/${release.software.cid}/${artifact.path}`) throw new Error('Software mirror binding mismatch');
  }
  const data = value.files.find(f => f.path === release.dataset.name);
  if (!data || data.bytes !== release.dataset.bytes || data.sha256 !== release.dataset.sha256 ||
      data.ipfs !== `/ipfs/${release.dataset.cid}/${data.path}` || data.parts?.length !== 13 ||
      data.parts.reduce((n, p) => n + p.bytes, 0) !== data.bytes) throw new Error('Dataset mirror binding mismatch');
  for (const [index, part] of data.parts.entries()) {
    if (part.name !== `${data.path}.part-${String(index + 1).padStart(3, '0')}` || !/^[0-9a-f]{64}$/.test(part.sha256) ||
        !Number.isSafeInteger(part.bytes) || part.bytes <= 0 || part.bytes > 1073741824 || part.urls.length !== 1) throw new Error('Invalid dataset part');
  }
  return value;
}

export async function enableDistribution(release, getArtifact) {
  const status = document.getElementById('distribution-status');
  const button = document.getElementById('mirror-download');
  try {
    const response = await fetch('install-v1/downloads.json', {credentials: 'omit', cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    if (hex(await crypto.subtle.digest('SHA-256', bytes)) !== DOWNLOADS_SHA256) throw new Error('Manifest SHA-256 mismatch');
    const manifest = assertDistribution(JSON.parse(new TextDecoder().decode(bytes)), release);
    button.disabled = false;
    for (const id of ['architecture', 'component']) document.getElementById(id).addEventListener('change', () => { button.disabled = !getArtifact(); });
    button.addEventListener('click', () => {
      const current = getArtifact();
      const file = current && manifest.files.find(f => f.path === current.path && f.sha256 === current.sha256);
      if (!file) { button.disabled = true; return; }
      window.open(file.urls[0], '_blank', 'noopener,noreferrer');
    });
    const list = document.getElementById('dataset-parts');
    for (const part of manifest.files.find(f => f.path === release.dataset.name).parts) {
      const li = document.createElement('li'); const a = document.createElement('a');
      a.href = part.urls[0]; a.rel = 'noopener noreferrer'; a.textContent = `${part.name} (${part.bytes.toLocaleString()} bytes)`;
      const code = document.createElement('code'); code.textContent = part.sha256;
      li.append(a, document.createElement('br'), code); list.append(li);
    }
    status.textContent = 'Mirror manifest verified. No account or publisher signature required. Check downloaded bytes before use.';
  } catch (error) {
    button.disabled = true;
    status.textContent = `Mirror verification failed: ${error.message}. Native IPFS and the original record remain available.`;
  }
}
