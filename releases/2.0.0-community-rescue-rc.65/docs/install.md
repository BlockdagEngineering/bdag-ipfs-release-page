# Install or upgrade RC65

RC65 supplies signed `linux/amd64` and `linux/arm64` software. The loader
maps `x86_64` to AMD64 and `aarch64` to ARM64 and rejects every other
architecture. It refuses to proceed when the release record, detached
signatures, archive hashes, signed image provenance, or dataset CIDs are
missing, stale, tampered, or still publication placeholders.

For an existing qualified node, stage the exact software beside the running
stack and reuse its chain data, peerstore, accounting, Stratum identity, and
payout mapping. An upgrade downloads neither the compact dataset nor the full
archive dataset, and does not require dataset download or extraction tools.
Cutover is permitted only after native-safe readiness and
accepted-share growth are proven, with the prior stack retained for rollback.

For a genuinely empty node, choose exactly one signed dataset:

```bash
BDAG_RC65_DATASET=compactMiningNode ./install-or-reuse-data.sh VERIFIED_RC65 /absolute/path/to/empty-data
BDAG_RC65_DATASET=fullArchive ./install-or-reuse-data.sh VERIFIED_RC65 /absolute/path/to/empty-data
```

The compact choice is for normal mining nodes; the full-archive choice is for
operators who need archive history. Dataset signatures, SHA-256, byte size,
Chain ID 1404, fixed anchors, and clean-shutdown metadata must be checked
before extraction. IPFS gateways are transport only. Bootstrap peers are
signed discovery input and never consensus or mining-readiness authorities.

The signed software tag is `jeremy-community-rescue-rc.65.6`. Authenticate the
software key fingerprint and `release-auth-manifest.json` before downloading
the architecture-specific ZIP. The full-archive restore is intentionally the
previously qualified v28 archive through EVM block 14,977,965 and must catch up
from ordinary Chain ID 1404 peers after extraction.
