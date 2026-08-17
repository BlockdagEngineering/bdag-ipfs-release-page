# RC62 Publication Record

This record identifies the protected build and immutable software objects used
for the published RC62 release. It contains no dataset identity because RC62 is
software-only.

## Release identity

- Version: `2.0.0-community-rescue-rc.62`
- Sequence: `62`
- Channel: `community-rescue`
- Mainnet chain ID: `1404`
- Status: `published`
- Publication timestamp: `2026-07-29T21:32:22Z`

## Source identity

- Repository: `https://github.com/BlockdagEngineering/stack`
- Tag: `2.0.0-community-rescue-rc.62`
- Stack commit: `60c3c6fd66edf24f79aff8ae8e0f91a3d01adb2e`
- Corechain commit: `bb0f7a6fed918e56251aa602503c90f1e1f30cb8`
- Pool commit: `79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50`
- Dashboard commit: `f00b654f79e50346bf6e866348cf07bdcb3b44ec`
- Source-lock SHA-256:
  `09eef25d1a70af571ccce655162dfb579ff5836e62999900c2cda0fdabc7c729`
- Signed release-lock SHA-256:
  `650d7f946ad77e3bf20670e9e2c89d8235371798857cbdd22177c91c9bb5a712`

## Protected build

- GitHub Actions run: `30482572680`
- Run attempt: `5`
- Workflow: `.github/workflows/dev-release.yml`
- Event: `workflow_dispatch`
- Qualified source head:
  `60c3c6fd66edf24f79aff8ae8e0f91a3d01adb2e`
- Publication attestation SHA-256:
  `e8359a049a2926c07309d687c851e9916f239c025630fe9e48ada2a9eabefa22`
- Export inventory tree SHA-256:
  `4a44ae52b1cd936016e653933b61390bfad7eace5674d480ce07838a73b6ba88`

The protected build qualified both AMD64 and ARM64 packages from fresh
extraction, including signed package integrity, exact privileged-profile
inventory, rollback, and runtime checks.

## Release trust

- Release public-key record: `records/software/release-key.pem`
- Canonical DER public-key SHA-256:
  `26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb`
- Raw PEM file SHA-256:
  `7fdb89fd41aa61f6e6120dc5895d82ab84753fa1c3da915268372901905a99ce`
- Release authorization manifest SHA-256:
  `bf274edf7451233bbc82371565cb0a8828bc0899ec3064a1c98dafef806274ff`
- Detached authorization signature SHA-256:
  `de5dff0390e6d3fd30b9d9aba516a8fd192fdb6e6d3e887e69aadf3ea3685266`
- Signed records-directory CID:
  `bafybeiabffabrb345zxeufuqh6kbj7qvyx3aprqe3mq2itn3uzjk72wsga`

The published `release_key_sha256` is the SHA-256 of the canonical DER public
key, not a checksum of the PEM text file.

## Immutable software objects

### Verified bootstrap

- Filename: `bootstrap.sh`
- Size: `10694` bytes
- SHA-256:
  `0a3422aa4b3185dc4405af93de7cdaa8deb3637dda311c94084998b68af26204`
- CID: `bafkreiakgqrkuszrqxoeibnpspphzwvi32zwg7o2geojiccjtc3iv4tcaq`

### Linux AMD64

- Filename:
  `pool-stack-docker-2.0.0-community-rescue-rc.62-linux-amd64.zip`
- Size: `480548999` bytes
- SHA-256:
  `a8b70ddce1c2a63b8391da42716f3110f895cefcd4ed2a793d8e02e37af3fe51`
- CID: `bafybeialnrsij74iiibcmevpbhaac3wurdfxxsftoypywjcxtfsnqjnfhe`

### Linux ARM64

- Filename:
  `pool-stack-docker-2.0.0-community-rescue-rc.62-linux-arm64.zip`
- Size: `456024999` bytes
- SHA-256:
  `766c4a6342d645dd8772b35af0ad781512c848f8c10c97523c9fab45b9ff66fb`
- CID: `bafybeicgihvkl7hoq4sufgskwjlopqr7vlr2zqhppssemrw5bmubhkjxhe`

## Dataset state

RC62 publishes no portable or full-archive dataset. Portable and full-archive
dataset identities, CIDs, manifests, and trust records remain absent. Preserve
compatible data or synchronize normally. A future dataset requires a separate
signed identity and qualification.

## Publication closure

The release-page CID is derived only after this version directory is frozen, so
it is intentionally recorded in the repository-level pin manifest rather than
self-referenced here. Publication requires local CID readback, independent
public seeders, the exact release validator, GitHub Pages readback, and only
then advancement of the stable IPNS name.
