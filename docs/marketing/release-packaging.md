# Release Packaging Checklist

This checklist is for preparing a paid sales build of 白歌的AI讨论组.

## Positioning

Sales edition positioning:

- Audience: photography post-production creators, Blender modeling users, and 3D scene creators.
- Main flow: basic AI workspace first, then Blender Agent real-time rendering.
- Included: normal chat, AI discussion, workflows, mind maps, photography references, Blender bridge, one-click 3D modeling, Agent real-time rendering, Hunyuan3D external-service interface.
- Excluded: PS assistant, bundled Hunyuan3D model service, API keys, third-party model fees, cloud hosting, cloud storage.

## Preflight

Run the non-strict release check during preparation:

```bash
npm run check:release
```

This check verifies:

- sales build package whitelist does not include local runtime data;
- Hunyuan3D service files are not bundled in `build.files`;
- PS bridge does not auto-start in sales mode;
- Hunyuan3D remains an external-service interface;
- landing page image and document paths resolve;
- high-confidence secret patterns are absent from release-facing files;
- `server.js` passes syntax check.

Run the strict check immediately before building a buyer DMG:

```bash
npm run check:release:strict
```

Strict mode requires a clean git worktree. If `data/asset_index.json` is dirty, either confirm it is runtime-only and reset it intentionally, or build from a clean clone.

## Build Steps

1. Confirm `data/configs.json` and `data/sessions.json` are not staged or included.
2. Build the Blender bridge plugin:

```bash
npm run build:addon
```

3. Run strict release check:

```bash
npm run check:release:strict
```

4. Build macOS DMGs:

```bash
npm run build:mac
```

5. Review `dist/` output:

- Apple Silicon DMG: `白歌的AI讨论组-3.7.0-arm64.dmg`
- Intel DMG: `白歌的AI讨论组-3.7.0-x64.dmg`

6. Upload DMGs and buyer docs to the chosen delivery folder.

Or generate a structured buyer delivery folder:

```bash
npm run build:buyer-kit
```

The buyer kit is written to `dist/delivery/ai-chat-buyer-kit-<version>/`. If DMGs already exist in `dist/`, they are copied into `installers/`; otherwise the generated manifest records a warning so you know installers still need to be built. The script also warns when existing DMGs are older than current source files, which means they should not be used for final delivery.

The buyer kit also writes `CHECKSUMS.txt` with SHA256 values for copied DMG installers. Send this file with paid deliveries so buyers can verify that the download completed correctly.

After generating the buyer kit, write a release evidence report:

```bash
npm run report:release
```

The report is written to `dist/delivery/ai-chat-buyer-kit-<version>/RELEASE_REPORT.md`. It checks the actual DMGs and buyer kit, including SHA256 values, DMG verification, buyer-kit warnings, high-confidence secret patterns, packaged app contents, production dependency audit, and macOS signing/Gatekeeper status.

## Buyer Delivery Bundle

Minimum delivery bundle:

- Apple Silicon DMG.
- Intel DMG.
- `CHECKSUMS.txt`
- `buyer-docs/INSTALL.md`
- `buyer-docs/FIRST_SCENE_TUTORIAL.md`
- `buyer-docs/THIRD_PARTY_NOTICES.md`
- `buyer-docs/REFUND_AND_SUPPORT.md`
- `buyer-docs/DELIVERY_MESSAGE.md`
- `RELEASE_REPORT.md` for internal release records.

Optional sales assets:

- Static landing page: `docs/marketing/site/index.html`
- Screenshots: `docs/marketing/screenshots/`
- Pricing copy: `docs/marketing/pricing-and-offer.md`

Generated bundle:

- `dist/delivery/ai-chat-buyer-kit-<version>/`

## Manual Smoke Test

Before sending a build to buyers:

1. Install the DMG on a clean macOS user account or test machine.
2. Start the app with no existing local config.
3. Confirm no private API provider appears.
4. Confirm PS assistant is not visible in the sales UI.
5. Confirm Hunyuan3D appears only as an external-service interface.
6. Add a test API provider.
7. Install the Blender bridge plugin.
8. Click Blender connection test.
9. Complete the first-scene tutorial.

## Signing And Notarization

For early manual delivery, unsigned or ad-hoc signed DMGs can be tested by users who understand macOS Gatekeeper prompts. For public paid distribution, build with Apple Developer ID signing and Apple notarization before publishing widely.

Current project status to check after each release build:

```bash
codesign --verify --deep --strict --verbose=2 "dist/mac-arm64/白歌的AI讨论组.app"
codesign --verify --deep --strict --verbose=2 "dist/mac/白歌的AI讨论组.app"
spctl --assess --type execute --verbose "dist/mac-arm64/白歌的AI讨论组.app"
spctl --assess --type execute --verbose "dist/mac/白歌的AI讨论组.app"
```

If signing is not configured, electron-builder may skip signing or fall back to ad-hoc signing. Do not describe that build as fully trusted or notarized.

Before a fully public launch:

1. Join the Apple Developer Program.
2. Create or install a `Developer ID Application` certificate.
3. Configure electron-builder signing credentials, usually with `CSC_LINK` and `CSC_KEY_PASSWORD`, or by installing the certificate in the local macOS keychain.
4. Configure notarization credentials such as Apple ID, app-specific password, and team ID according to the current electron-builder and Apple documentation.
5. Rebuild both arm64 and x64 DMGs.
6. Verify both apps with `codesign` and `spctl`.
7. Rebuild the buyer kit and confirm `MANIFEST.json` has no warnings.

## Notes

- The sales package does not include API keys.
- The sales package does not include Hunyuan3D hosting, model weights, or compute.
- Users who connect Hunyuan3D-compatible services are responsible for their own deployment and license compliance.
- Generated output quality is not guaranteed and depends on the model, prompt, Blender environment, and third-party services.
