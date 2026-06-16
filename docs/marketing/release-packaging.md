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

## Buyer Delivery Bundle

Minimum delivery bundle:

- Apple Silicon DMG.
- Intel DMG.
- `buyer-docs/INSTALL.md`
- `buyer-docs/FIRST_SCENE_TUTORIAL.md`
- `buyer-docs/THIRD_PARTY_NOTICES.md`
- `buyer-docs/REFUND_AND_SUPPORT.md`
- `buyer-docs/DELIVERY_MESSAGE.md`

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

## Notes

- The sales package does not include API keys.
- The sales package does not include Hunyuan3D hosting, model weights, or compute.
- Users who connect Hunyuan3D-compatible services are responsible for their own deployment and license compliance.
- Generated output quality is not guaranteed and depends on the model, prompt, Blender environment, and third-party services.
