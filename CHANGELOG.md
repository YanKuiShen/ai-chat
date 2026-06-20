# Changelog

## Current - 2026-06-20

This repository now keeps only the current public release notes in Git. Older
release handoff files, roadmap notes, superseded design specs, and the full
historical changelog are kept locally by the maintainer and are intentionally
ignored by the repository.

### Changed

- Prepared the project for public GitHub release.
- Added README open-source notes, a realtime-render workflow screenshot, and a
  compact Mermaid workflow diagram.
- Realtime-render workflow now uses the colored reference image directly for the
  Hunyuan and AI branches; the white-matte node is no longer part of the public
  workflow description.
- Local Codex mode can replace paid API-key nodes for realtime-render text,
  vision, image, and Blender-code steps.
- Hunyuan runtime controls include resource probing and uncapped timeout limits
  based on the user setting.

### Security

- `.env`, app config, sessions, local databases, realtime run ledgers, asset
  indexes, model weights, caches, and build outputs are excluded from Git.
- Hunyuan weight folders and local PolyHaven asset indexes were removed from the
  tracked tree; they remain local-only runtime data.

### Verification

- `npm run check:realtime-workflow`
- `node -c server.js`
- `node -c scripts/check-realtime-workflow.js`
