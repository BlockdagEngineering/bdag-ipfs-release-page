# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.30`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.30-page-v2/`

Large software and dataset artifacts are not stored in Git. The release page
records immutable IPFS CIDs, GitHub software fallbacks, byte sizes, SHA-256
values, signing-key fingerprints, and canonical chain checkpoints.

RC30 software and portable v27 data are independent artifacts. Portable data
is published as three verified IPFS parts; the separately qualified full
archive dataset remains pending. All documented `curl` downloads force IPv4
and HTTP/1.1 for reliable public-gateway transfer. Generated commands fetch
signed records from a separate immutable IPFS directory, so they also work
when the setup page is opened through a service-worker gateway.
