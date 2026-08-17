Offline BlockDAG community rescue RC32 from one signed four-repository source lock.

RC32 is the RC30 full-archive/public-RPC hotfix qualification candidate. It retains RC30 restore compatibility and packages the latest live-proven node, pool, and dashboard revisions. The earlier signed RC31 qualification artifacts and their rejected dataset-canary path are not reused. Signed dataset policy, live historical boundaries, the governed checkpoint, and the required fresh-peer floor remain mandatory. Mining profiles always wait for full producer-safe currentness before activation.

The node now waits for a committed EVM head through bounded canonical mutations instead of causing transient public-RPC failures. Full-archive activation fails closed unless EVM archive retention is configured and getArchiveStatus confirms it live; the removed native --archival flag is rejected.

The full-archive profile uses bounded node-side request limits and requires an independently configured edge proxy, TLS, abuse controls, monitoring, and restart recovery. The release does not encode emergency operator access or any trusted consensus endpoint.

Software and canonical dataset artifacts remain independent. Authenticate the release key fingerprint and signed manifests before installation.
