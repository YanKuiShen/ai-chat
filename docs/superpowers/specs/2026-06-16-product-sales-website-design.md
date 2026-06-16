# Product Sales Website Design

Date: 2026-06-16
Owner: Baige
Product: 白歌的AI讨论组 / AI Blender 创作工作台

## Goal

Prepare the product for paid distribution without building a cloud backend. The first commercial offer is a local desktop app for photography post-production, image-based scene planning, Blender modeling, and real-time 3D scene creation.

## Positioning

Primary positioning:

> A local AI Blender creation workstation that turns prompts, references, and scene ideas into Blender-ready 3D workflows.

Website storytelling should first show the basic workspace features that photography post-production users can understand quickly: normal chat, AI discussion / battle mode, workflows, mind maps, photography references, and post-production notes. After that foundation is clear, introduce Smart Agent real-time rendering and Blender modeling as the flagship paid feature.

Do not sell the product as only another general AI chat app. The basic AI workspace is the entry point and trust builder; the defensible paid use case is photography post-production assisted by local Blender modeling, scene building, and 3D real-time rendering.

## Audience

Primary audience:

- Blender hobbyists who want faster scene blocking and automation.
- 3D creators who can use AI-generated Blender scripts as a starting point.
- Photography post-production creators who need backgrounds, lighting references, scene mockups, or CG-assisted composition.
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
- Basic local AI workspace: normal chat, AI discussion, workflows, mind maps, and photography notes.
- One-click 3D modeling workflow.
- Smart Agent real-time rendering panel.
- bmesh / Geometry Nodes template library.
- PolyHaven asset confirmation workflow.
- Hunyuan3D external-service interface for users who self-deploy compatible Hunyuan3D services.
- Installation guide and troubleshooting checklist.

The paid package does not include PS assistant, bundled Hunyuan3D model service, third-party API credits, paid model access, cloud hosting, or guaranteed Blender model output quality. Users bring their own API keys, Blender installation, and any external Hunyuan3D service they choose to connect.

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
   - Headline: AI creation workspace for photography post-production and Blender modeling.
   - Subheadline: normal chat, AI discussion, workflows, photography references, Blender modeling, and real-time rendering in one desktop app.
   - Primary CTA: Download trial / Get macOS version.
   - Secondary CTA: Watch demo / View setup guide.
   - Primary visual: start with `docs/marketing/screenshots/01-home-overview.png`, then feature `docs/marketing/screenshots/06-blender-agent-rendering.png` below the fold.

2. Basic Workspace
   - Show normal chat, AI discussion, workflow builder, mind map notes, and photography post-production project tools.
   - Use `01-home-overview.png`, `02-workflow-builder-clean.png`, and `03-mindmap-notes-clean.png`.

3. Problem
   - AI chat tools are easy to find, but turning photography post-production ideas into usable Blender backgrounds, props, lighting, and 3D scenes still requires repetitive setup, scripting, asset selection, and revision.

4. Flagship Feature
   - Introduce Smart Agent real-time rendering and Blender modeling as the main reasons to buy.
   - Use `06-blender-agent-rendering.png` as the main visual.

5. Workflow
   - Describe the pipeline: idea -> scene summary -> reference generation -> Blender script/Agent -> viewport feedback -> revision.
   - Use `05-one-click-3d-modeling.png` and `06-blender-agent-rendering.png`.

6. Features
   - Local multi-model AI workspace.
   - Normal chat and AI discussion / battle mode.
   - Workflow and mind-map tools as supporting features.
   - Photography post-production reference board and image analysis.
   - One-click Blender modeling pipeline.
   - AI Blender Agent real-time rendering.

7. Pricing
   - Free trial or free basic package.
   - Professional package.
   - Creator support package.

8. Requirements
   - macOS first.
   - Blender required for 3D features.
   - User-provided API key required.
   - PS assistant is not included in the paid sales edition.
   - Hunyuan3D is provided as an external-service interface only; users self-deploy and connect their own compatible service.

9. FAQ
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
- Keep `LICENSE` and `NOTICE` files for Hunyuan3D-related materials if they remain in source archives.
- State that Tencent is not affiliated with, sponsoring, or endorsing this product.
- State that Hunyuan3D is an external-service interface and users must follow the original Hunyuan3D license when self-deploying or using it.
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
- PS assistant entry points are hidden or disabled in the sales edition.
- Hunyuan3D remains as a user-provided external-service interface, not a bundled model service.
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
