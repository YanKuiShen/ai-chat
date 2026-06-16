# Product Sales Website Design

Date: 2026-06-16
Owner: Baige
Product: 白歌的AI讨论组 / AI Blender 创作工作台

## Goal

Prepare the product for paid distribution without building a cloud backend. The first commercial offer is a local desktop app for AI-assisted Blender and 3D scene creation. Basic AI chat features remain useful as onboarding, but the paid value is the Blender/3D workflow.

## Positioning

Primary positioning:

> A local AI Blender creation workstation that turns prompts, references, and scene ideas into Blender-ready 3D workflows.

Do not position the product as a general AI chat app. General chat, multi-model setup, workflows, mind maps, and photography notes are supporting features. The website should lead with the 3D creation workflow because that is the defensible paid use case.

## Audience

Primary audience:

- Blender hobbyists who want faster scene blocking and automation.
- 3D creators who can use AI-generated Blender scripts as a starting point.
- Designers and content creators who want prompt-to-scene workflows without building their own local tooling.

Secondary audience:

- AI power users who want local multi-model workflows and are curious about 3D.

## Offer

The first sales model is a one-time paid download.

Free entry:

- Basic local AI chat and multi-model configuration.
- Basic workflow, mind map, and photography project exploration.
- Public screenshots, demos, and installation docs.

Paid professional package:

- macOS app installer.
- Blender bridge plugin package.
- One-click 3D modeling workflow.
- Smart Agent real-time rendering panel.
- bmesh / Geometry Nodes template library.
- PolyHaven asset confirmation workflow.
- Installation guide and troubleshooting checklist.

The paid package does not include third-party API credits, paid model access, cloud hosting, or guaranteed Blender model output quality. Users bring their own API keys and Blender installation.

## Pricing

Recommended launch price:

- Early bird: RMB 99-149.
- Standard individual license: RMB 199-299.
- Creator support package: RMB 499, including installation help and a short onboarding call or written support.

Keep the initial product simple. Do not launch subscriptions until there is a server-side reason to charge monthly, such as cloud accounts, template updates, hosted rendering, or ongoing support.

## Website Structure

The website should be a single-page product site first, with clear secondary pages for docs and purchase.

Required sections:

1. Hero
   - Headline: local AI Blender creation workstation.
   - Subheadline: prompt/reference/chat history to Blender scene workflow.
   - Primary CTA: Download trial / Get macOS version.
   - Secondary CTA: Watch demo / View setup guide.
   - Primary visual: `docs/marketing/screenshots/06-blender-agent-rendering.png`.

2. Problem
   - AI chat tools are easy to find, but turning ideas into usable 3D scenes still requires repetitive Blender setup, scripting, asset selection, and revision.

3. Workflow
   - Describe the pipeline: idea -> scene summary -> reference generation -> Blender script/Agent -> viewport feedback -> revision.
   - Use `05-one-click-3d-modeling.png` and `06-blender-agent-rendering.png`.

4. Features
   - AI Blender Agent.
   - One-click 3D modeling pipeline.
   - Local multi-model AI workspace.
   - Photography reference board and image analysis.
   - Workflow and mind-map tools as supporting features.

5. Pricing
   - Free trial or free basic package.
   - Professional package.
   - Creator support package.

6. Requirements
   - macOS first.
   - Blender required for 3D features.
   - User-provided API key required.
   - Hunyuan3D-related functionality has territory and usage restrictions.

7. FAQ
   - Is it cloud-based? No.
   - Are API keys included? No.
   - Is generated content guaranteed? No.
   - Does it work without Blender? Basic features yes, 3D features no.
   - Can it be used commercially? User must follow third-party model and asset licenses.

## Purchase And Delivery Flow

No cloud account system is required for launch.

Recommended manual launch flow:

1. Customer pays through a payment link or direct transfer.
2. Customer receives a download link to the DMG and setup docs.
3. Customer installs the app.
4. Customer installs Blender bridge plugin from the app.
5. Customer configures their own API provider.
6. Customer follows the first-scene tutorial.

Recommended later automation:

- Use Gumroad, Lemon Squeezy, Ko-fi, 小报童, 飞书表单 + 网盘, or a similar lightweight storefront to deliver files and updates.

## Legal And Licensing Notes

The product includes third-party code and model-adjacent files. The website and docs must avoid claiming full ownership over third-party components.

Required public notices:

- Include a third-party notices page.
- Keep `LICENSE` and `NOTICE` files for Hunyuan3D-related materials.
- State that Tencent is not affiliated with, sponsoring, or endorsing this product.
- State that Hunyuan3D-related use is restricted outside the allowed territory described by its license.
- Keep MIT license attribution for blender-mcp-derived code.
- State that API providers and AI models are third-party services.

## Screenshots

Current marketing screenshots:

- `docs/marketing/screenshots/06-blender-agent-rendering.png`: best hero visual.
- `docs/marketing/screenshots/05-one-click-3d-modeling.png`: workflow section visual.
- `docs/marketing/screenshots/04-photography-tools-clean.png`: secondary feature visual.
- `docs/marketing/screenshots/02-workflow-builder-clean.png`: supporting workflow visual.
- `docs/marketing/screenshots/03-mindmap-notes-clean.png`: supporting productivity visual.

Before publishing, review screenshots for private provider names, local paths, and text that may confuse buyers.

## Launch Gates

The product is not ready for paid public launch until these gates are satisfied:

- A buyer can install the app from a clean DMG.
- A buyer can install the Blender plugin with written instructions.
- A buyer can configure an API key without seeing the developer's private configuration.
- A buyer can complete one tutorial scene.
- The website clearly says API keys and model costs are not included.
- The website clearly says Blender is required for 3D features.
- Third-party notices are present.
- A refund/support policy exists.
- A download delivery method exists.

## Scope Exclusions

Do not build these for the first paid launch:

- User accounts.
- Cloud sync.
- Subscription billing.
- Hosted model inference.
- License server.
- Team management.
- Web app version of the product.

These can be revisited after paid demand is proven.

