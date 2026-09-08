import {RECORD_SHA256} from './record-binding.mjs';

export function assertRelease(record) {
  const sha = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
  const cid = value => typeof value === 'string' && /^b[a-z2-7]{20,}$/.test(value);
  if (record.schema !== 'blockdag.develop-release/v1' || record.version !== '2.1.0-rc.2' ||
      !['prepared','published'].includes(record.status) ||
      record.branch !== 'develop' || record.main_promoted !== false || record.chain_id !== 1404 ||
      !cid(record.software.cid) || !Array.isArray(record.software.artifacts) || record.software.artifacts.length !== 10) {
    throw new Error('Release identity is invalid');
  }
  for (const file of record.software.artifacts) {
    if (!/^[a-zA-Z0-9._-]+$/.test(file.name) || file.path !== 'artifacts/' + file.name ||
        !sha(file.sha256) || !Number.isSafeInteger(file.bytes) || file.bytes <= 0 ||
        !['linux-amd64', 'linux-arm64'].includes(file.platform)) throw new Error('Invalid software record');
    if (file.mirror) throw new Error('Unexpected mirror');
  }
  if (record.dataset) {
    const data = record.dataset;
    if (data.status !== 'accepted' || !cid(data.cid) || !sha(data.sha256) || !sha(data.manifest_sha256) ||
        !/^[a-zA-Z0-9._-]+\.bdsnap$/.test(data.name) || data.format_version !== 4 ||
        JSON.stringify(data.sources) !== JSON.stringify(['chain','evm']) || !data.independent_import_passed) {
      throw new Error('Dataset acceptance is incomplete');
    }
  }
  if (record.status === 'published' && (!record.dataset ||
      record.qualification?.mining_completion_claimed !== true ||
      record.qualification.detached_120s_receipt !== 'records/mining-acceptance.json' ||
      !sha(record.qualification.mining_acceptance_sha256))) {
    throw new Error('Published release is missing accepted data or mining evidence');
  }
  return record;
}

const hex = bytes => [...new Uint8Array(bytes)].map(n => n.toString(16).padStart(2, '0')).join('');
const elem = id => document.getElementById(id);
function link(text, url) { const a=document.createElement('a');a.textContent=text;a.href=url;a.rel='noopener noreferrer';return a; }
function render(record) {
  elem('record-status').textContent = record.status === 'published' ? 'Exact release record verified. Develop prerelease; qualification limits below.' : 'Prepared release record verified; publication is not complete.';
  elem('gateway-note').textContent = record.download_note;
  if (record.status === 'published' && record.qualification.mining_completion_claimed === true) {
    elem('qualification-status').textContent = 'AMD64 passed a nominal 120-second mining test on TesterD with three physical ASICs, advancing shares, accepted blocks, preserved accounting and an independent canonical witness. ARM64 hardware, fleet, reboot and six-hour soak qualification are not claimed. ';
    elem('qualification-status').append(link('Qualification receipt', 'records/mining-acceptance.json'));
  }
  for (const file of record.software.artifacts) {
    const row=document.createElement('tr');
    for (const value of [file.component, file.platform, `${(file.bytes/1048576).toFixed(1)} MiB`]) { const td=document.createElement('td');td.textContent=value;row.append(td); }
    const download=document.createElement('td');
    download.append(link('Native IPFS', `ipfs://${record.software.cid}/${file.path}`));
    if (file.mirror) download.append(' · ', link('GitHub fallback', file.mirror));
    row.append(download);
    const digest=document.createElement('td');const code=document.createElement('code');code.textContent=file.sha256;digest.append(code);row.append(digest);elem('software-downloads').append(row);
  }
  elem('software-command').textContent = `# Optional direct connection to the verified public seeder:\nipfs swarm peering add /ip4/102.39.223.233/tcp/4001/p2p/12D3KooW9uWWJz7nQ5kvg9abq7CHsZJ9HxzQq6oFQVPsFn3mr5Ae\nipfs get /ipfs/${record.software.cid} -o blockdag-software-2.1.0-rc.2\ncd blockdag-software-2.1.0-rc.2\nsha256sum -c SHA256SUMS\n# Select your architecture, unpack its runtime ZIP, then read README.md.\n# No BlockDAG service, identity, payout or accounting changes occur.\n# The optional peering hint changes only this running IPFS client's peers.`;
  if (!record.dataset) return;
  const data=record.dataset;
  elem('dataset-status').textContent = `Accepted bootstrap: native order ${data.native.order}; EVM block ${data.evm.number}. SHA-256 and independent import/semantic checks passed. Catch-up remains necessary.`;
  elem('dataset-download').append(link('Native IPFS dataset', `ipfs://${data.cid}/${data.name}`), ' · ', link('Acceptance details', 'records/dataset-acceptance.json'));
  elem('dataset-command').textContent = `ipfs get /ipfs/${data.cid}/${data.name} -o ${data.name}\nprintf '%s  %s\\n' '${data.sha256}' '${data.name}' | sha256sum -c -\n# CORE_BIN must be the verified binary for this machine's architecture.\n"$CORE_BIN" snap verify --path "${data.name}"\n# CANDIDATE must be your NEW EMPTY datadir, never a running node's data.\n"$CORE_BIN" snap import --datadir "$CANDIDATE" --path "${data.name}"\n"$CORE_BIN" dataset inspect --datadir "$CANDIDATE"\n"$CORE_BIN" dataset manifest create --datadir "$CANDIDATE" --include-current-checkpoint\n"$CORE_BIN" dataset verify --datadir "$CANDIDATE"`;
}

if (typeof document !== 'undefined') {
  try {
    const response=await fetch('records/release.json', {cache:'no-store',credentials:'omit'});
    if (!response.ok) throw new Error(`Release record HTTP ${response.status}`);
    const bytes=await response.arrayBuffer();
    if (hex(await crypto.subtle.digest('SHA-256',bytes)) !== RECORD_SHA256) throw new Error('Release record SHA-256 mismatch');
    render(assertRelease(JSON.parse(new TextDecoder().decode(bytes))));
  } catch(error) { elem('record-status').textContent=`Release checks failed: ${error.message}. Do not use unverified downloads.`; }
}
