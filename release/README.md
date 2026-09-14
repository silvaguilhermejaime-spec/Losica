# Complete Losica 0.29 release

This directory stores the exact `losica-0.29-causal-with-external-sources.zip`
release as 33 ordered parts. The split avoids per-request transfer limits while
preserving the archive byte for byte.

The archive includes the generated causal language and the mechanically
normalized 289,480-record external-source catalog. Source attribution and
usage terms are recorded in `external_sources/NOTICE.md` inside the archive.

Reconstruct and verify it with:

```bash
python tools/reconstruct_release.py
```

The expected archive SHA-256 is recorded in `release/SHA256SUMS`. GitHub
Actions also reconstructs and publishes the verified ZIP as the
`losica-complete-release` workflow artifact.
