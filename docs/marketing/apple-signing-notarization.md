# Apple Signing And Notarization Guide

This guide is for preparing 白歌的AI讨论组 for broad public paid macOS distribution.

## Why This Matters

The current unsigned or ad-hoc signed build can be used for controlled manual delivery, but macOS Gatekeeper will warn or block on first launch. A broad public paid launch should use:

- Developer ID Application signing.
- Hardened Runtime.
- Apple notarization.
- Stapled notarization ticket.

## One-Time Requirements

Prepare these before making a fully public release:

- Active Apple Developer Program membership.
- Xcode or Xcode Command Line Tools.
- `Developer ID Application` certificate.
- Apple notarization credentials.

For notarization credentials, use one of these approaches:

- Apple ID: `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`.
- App Store Connect API key: `APPLE_API_KEY`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER`, `APPLE_TEAM_ID`.
- Local notarytool keychain profile: `APPLE_KEYCHAIN_PROFILE`, `APPLE_TEAM_ID`.

For electron-builder certificate signing, use either:

- A valid `Developer ID Application` certificate installed in the local macOS keychain.
- Or `CSC_LINK` plus `CSC_KEY_PASSWORD`.

Never commit `.p12`, `.p8`, passwords, app-specific passwords, API keys, or exported keychain files.

## Current Project Preparation

The project includes:

- `npm run check:mac-signing`
- `build/entitlements.mac.plist`
- `build/entitlements.mac.inherit.plist`
- `npm run report:release`

The entitlements files are present for the future notarized build. Notarization is not enabled by default yet, because enabling it before credentials exist would make local release builds fail.

## Preflight

Run:

```bash
npm run check:mac-signing
```

Warnings mean the machine is not ready for a fully public notarized build. Typical missing items:

- No `Developer ID Application` certificate found.
- No `CSC_LINK` / `CSC_KEY_PASSWORD`.
- No Apple notarization credentials.
- `build.mac.notarize` not enabled yet.

## Enable Fully Public Signing

After credentials are available, update `package.json` under `build.mac`:

```json
{
  "notarize": true,
  "hardenedRuntime": true,
  "entitlements": "build/entitlements.mac.plist",
  "entitlementsInherit": "build/entitlements.mac.inherit.plist"
}
```

Keep the existing `target`, `artifactName`, `icon`, and `category` settings.

## Build Flow

From a clean release worktree:

```bash
npm run check:mac-signing
npm run check:release:strict
npm run build:addon
npm run build:mac
npm run build:buyer-kit
npm run report:release
```

The final `RELEASE_REPORT.md` should show:

- `buyer kit manifest has no warnings`
- `production dependency audit has 0 vulnerabilities`
- `Gatekeeper assessment` accepted for both arm64 and x64 apps
- release result `PASS`

## Verify Manually

Run:

```bash
codesign --verify --deep --strict --verbose=2 "dist/mac-arm64/白歌的AI讨论组.app"
codesign --verify --deep --strict --verbose=2 "dist/mac/白歌的AI讨论组.app"
spctl --assess --type execute --verbose "dist/mac-arm64/白歌的AI讨论组.app"
spctl --assess --type execute --verbose "dist/mac/白歌的AI讨论组.app"
xcrun stapler validate "dist/mac-arm64/白歌的AI讨论组.app"
xcrun stapler validate "dist/mac/白歌的AI讨论组.app"
```

For a fully public build, `spctl` should accept the app and `stapler validate` should pass.
