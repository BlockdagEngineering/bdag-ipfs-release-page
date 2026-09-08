import {RECORD_SHA256} from './record-binding.mjs';
import {enableDistribution} from './distribution.mjs';

export const ARCHITECTURES = Object.freeze(['linux-amd64', 'linux-arm64']);
export const COMPONENTS = Object.freeze(['full-stack', 'corechain', 'pool', 'dashboard', 'stack']);

export function isSha256(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
export function isCid(value) { return typeof value === 'string' && /^b[a-z2-7]{20,}$/.test(value); }
export function formatBytes(value) {
  if (!Number.isFinite(value) || value < 0) return '—';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']; let amount = value; let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1; }
  return `${amount >= 10 || unit === 0 ? amount.toFixed(unit === 0 ? 0 : 1) : amount.toFixed(2)} ${units[unit]}`;
}

export function assertRelease(record) {
  const sha = isSha256;
  const cid = isCid;
  if (record?.schema !== 'blockdag.develop-release/v1' || record.version !== '2.1.0-rc.2' ||
      !['prepared', 'published'].includes(record.status) || record.branch !== 'develop' ||
      record.main_promoted !== false || record.chain_id !== 1404 || !cid(record.software?.cid) ||
      !Array.isArray(record.software.artifacts) || record.software.artifacts.length !== 10) {
    throw new Error('Release identity is invalid');
  }
  for (const file of record.software.artifacts) {
    if (!/^[a-zA-Z0-9._-]+$/.test(file.name) || file.path !== `artifacts/${file.name}` ||
        !sha(file.sha256) || !Number.isSafeInteger(file.bytes) || file.bytes <= 0 ||
        !ARCHITECTURES.includes(file.platform) || !['corechain', 'pool', 'dashboard', 'stack', 'full stack'].includes(file.component) || file.mirror) {
      throw new Error('Invalid software record');
    }
  }
  const data = record.dataset;
  if (!data || data.status !== 'accepted' || !cid(data.cid) || !sha(data.sha256) || !sha(data.manifest_sha256) ||
      !/^[a-zA-Z0-9._-]+\.bdsnap$/.test(data.name) || data.format_version !== 4 ||
      JSON.stringify(data.sources) !== JSON.stringify(['chain', 'evm']) || data.independent_import_passed !== true) {
    throw new Error('Dataset acceptance is incomplete');
  }
  if (record.status === 'published' && (!record.qualification || record.qualification.mining_completion_claimed !== true ||
      record.qualification.detached_120s_receipt !== 'records/mining-acceptance.json' || !sha(record.qualification.mining_acceptance_sha256))) {
    throw new Error('Published release is missing accepted mining evidence');
  }
  return record;
}

function componentName(value) { return value === 'full-stack' ? 'full stack' : value; }
export function selectArtifact(record, architecture, component) {
  if (!ARCHITECTURES.includes(architecture) || !COMPONENTS.includes(component)) return null;
  return record.software.artifacts.find((file) => file.platform === architecture && file.component === componentName(component)) ?? null;
}
export function nativeIpfsUrl(record, path) { return `ipfs://${record.software.cid}/${path}`; }
export function gatewayUrl(record, path) { return `https://dweb.link/ipfs/${record.software.cid}/${path}`; }
export function nativeDatasetUrl(record, path) { return `ipfs://${record.dataset.cid}/${path}`; }
export function gatewayDatasetUrl(record, path) { return `https://dweb.link/ipfs/${record.dataset.cid}/${path}`; }
export function buildVerifyCommand(record, artifact) {
  if (!artifact || !record?.software?.cid) return '';
  return `ipfs get /ipfs/${record.software.cid}/${artifact.path} -o ${artifact.name}\nprintf '%s  %s\\n' '${artifact.sha256}' '${artifact.name}' | sha256sum -c -`;
}
export async function copyText(value, clipboard = globalThis.navigator?.clipboard) {
  if (!clipboard || typeof clipboard.writeText !== 'function') return false;
  try { await clipboard.writeText(value); return true; } catch { return false; }
}

const hex = (bytes) => [...new Uint8Array(bytes)].map((n) => n.toString(16).padStart(2, '0')).join('');
async function fetchRecord() {
  const response = await fetch('records/release.json', {cache: 'no-store', credentials: 'omit'});
  if (!response.ok) throw new Error(`Release record HTTP ${response.status}`);
  const bytes = await response.arrayBuffer();
  if (!globalThis.crypto?.subtle) throw new Error('Browser SHA-256 support is unavailable');
  if (hex(await crypto.subtle.digest('SHA-256', bytes)) !== RECORD_SHA256) throw new Error('Release record SHA-256 mismatch');
  return assertRelease(JSON.parse(new TextDecoder().decode(bytes)));
}

function dom(id) { return document.getElementById(id); }
function actionButtons() { return [...document.querySelectorAll('[data-action]')]; }
function artifactActions() { return [...actionButtons(), dom('copy-command')].filter(Boolean); }
function setArtifactActionsEnabled(enabled) { for (const element of artifactActions()) element.disabled = !enabled; }
function setActionsEnabled(enabled) {
  setArtifactActionsEnabled(enabled);
  for (const element of [dom('architecture'), dom('component')]) if (element) element.disabled = !enabled;
}
function openUrl(url) {
  if (typeof window !== 'undefined' && url) window.open(url, '_blank', 'noopener,noreferrer');
}

function render(record) {
  let current = null;
  const arch = dom('architecture'); const component = dom('component');
  const selectedName = dom('selectedName'); const selectedSize = dom('selectedSize'); const selectedSha = dom('selectedSha'); const selectedPath = dom('selectedPath');
  const command = dom('download-command'); const copy = dom('copy-command'); const copyStatus = dom('copy-status');
  const selectionNotice = dom('selectionNotice');
  const clearSelection = (message = 'Choose a listed architecture and payload to continue.') => {
    current = null;
    selectedName.textContent = 'Selection unavailable'; selectedSize.textContent = '—'; selectedSha.textContent = '—'; selectedPath.textContent = '—';
    command.textContent = 'Commands remain locked until a verified artifact is selected.'; delete copy.dataset.command;
    selectionNotice.textContent = message; setArtifactActionsEnabled(false);
  };
  const update = () => {
    current = selectArtifact(record, arch.value, component.value);
    if (!current) { clearSelection('That selection is not in the verified release record. Choose another payload.'); return false; }
    selectedName.textContent = current.name; selectedSize.textContent = formatBytes(current.bytes); selectedSha.textContent = current.sha256; selectedPath.textContent = current.path;
    command.textContent = buildVerifyCommand(record, current); copy.dataset.command = command.textContent;
    selectionNotice.textContent = `${current.platform} · ${current.component} · verify the displayed SHA-256 before unpacking.`; setArtifactActionsEnabled(true); return true;
  };
  arch.addEventListener('change', update); component.addEventListener('change', update);
  dom('native-download').addEventListener('click', () => { if (!current || selectArtifact(record, arch.value, component.value) !== current) return clearSelection('Selection changed; choose the verified artifact again.'); openUrl(nativeIpfsUrl(record, current.path)); });
  dom('gateway-download').addEventListener('click', () => { if (!current || selectArtifact(record, arch.value, component.value) !== current) return clearSelection('Selection changed; choose the verified artifact again.'); openUrl(gatewayUrl(record, current.path)); });
  copy.addEventListener('click', async () => {
    if (!current || selectArtifact(record, arch.value, component.value) !== current || copy.dataset.command !== buildVerifyCommand(record, current)) { clearSelection('Selection changed; choose the verified artifact again.'); return; }
    const ok = await copyText(copy.dataset.command);
    copyStatus.textContent = ok ? 'Command copied. Review it before running.' : 'Clipboard unavailable or denied; select the command manually.';
  });
  for (const pathButton of document.querySelectorAll('[data-path]')) pathButton.addEventListener('click', () => {
    if (pathButton.dataset.path === 'new') document.getElementById('dataset').scrollIntoView({behavior: 'smooth'});
    else {
      component.value = pathButton.dataset.path === 'component' ? 'corechain' : 'full-stack';
      update();
      document.getElementById('download').scrollIntoView({behavior: 'smooth'});
    }
  });

  const data = record.dataset;
  dom('dataset-status').textContent = `Accepted Chain 1404 bootstrap: native order ${data.native.order}; EVM block ${data.evm.number}. Independent import and semantic checks passed; catch-up remains necessary.`;
  dom('dataset-name').textContent = data.name; dom('dataset-boundary').textContent = `Native order ${data.native.order} · EVM ${data.evm.number}`; dom('dataset-sha').textContent = data.sha256; dom('dataset-cid').textContent = data.cid;
  const datasetActionAllowed = (button) => !button.disabled && current && selectArtifact(record, arch.value, component.value) === current;
  dom('native-dataset').addEventListener('click', (event) => { if (datasetActionAllowed(event.currentTarget)) openUrl(nativeDatasetUrl(record, data.name)); });
  dom('gateway-dataset').addEventListener('click', (event) => { if (datasetActionAllowed(event.currentTarget)) openUrl(gatewayDatasetUrl(record, data.name)); });
  dom('dataset-command').textContent = `ipfs get /ipfs/${data.cid}/${data.name} -o ${data.name}\nprintf '%s  %s\\n' '${data.sha256}' '${data.name}' | sha256sum -c -\n# Use a NEW EMPTY destination, then read README.md for the reviewed dataset workflow.`;
  dom('record-digest').textContent = `Bound SHA-256: ${RECORD_SHA256}`;
  dom('record-status').textContent = record.status === 'published' ? 'Release record verified' : 'Prepared release record verified'; dom('trust-detail').textContent = 'This release record matches its expected SHA-256. Choose a download below, then use the checksum command to check your downloaded files.';
  dom('trust-dot').className = 'status-dot ready'; dom('qualification-status').textContent = record.status === 'published' && record.qualification.mining_completion_claimed === true
    ? 'Tested on AMD64 with three physical ASICs: shares and accepted blocks increased during a 120-second check, with accounting preserved. ARM64 hardware, reboot and long-run testing are not covered.'
    : 'AMD64 physical-mining/accounting qualification remains pending a detached 120-second receipt. ARM64 hardware, main promotion, reboot and long-soak qualification are not claimed.';
  setActionsEnabled(true); update();
  enableDistribution(record, () => selectArtifact(record, arch.value, component.value));
}

function fail(error) {
  setActionsEnabled(false);
  dom('record-status').textContent = `Release checks failed: ${error.message}`; dom('trust-detail').textContent = 'Actions remain disabled. Inspect the records locally and do not use unverified downloads.'; dom('trust-dot').className = 'status-dot failed'; dom('selectionNotice').textContent = 'Verification failed; download and clipboard actions are disabled.';
}

if (typeof document !== 'undefined') {
  fetchRecord().then(render).catch(fail);
}
