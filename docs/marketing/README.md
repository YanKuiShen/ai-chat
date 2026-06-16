# Marketing Preparation

This folder contains the launch materials for selling the product as a local AI creation workspace for photography post-production and Blender modeling, with Blender real-time rendering as the flagship paid feature.

Key files:

- `site/index.html`: static landing page prototype that can be opened locally or hosted on any static site service.
- `website-copy.md`: landing page copy and page structure.
- `pricing-and-offer.md`: version packaging, pricing, and what is included.
- `release-packaging.md`: preflight checks and paid DMG packaging flow.
- `sales-delivery-flow.md`: how to sell and deliver without a cloud backend.
- `legal-and-risk-checklist.md`: licensing, notices, and commercial risk checks.
- `launch-checklist.md`: practical checklist before public paid launch.
- `screenshot-index.md`: current product screenshots for website and sales pages.

Primary product position:

> Local AI workspace for photography post-production and Blender modeling. Basic AI chat is onboarding; paid value is AI-assisted scene planning, Blender modeling, and real-time 3D rendering.

Sales narrative:

1. Show the basic workspace first: normal chat, AI discussion, workflows, mind maps, and photography notes.
2. Then introduce the flagship feature: Smart Agent real-time rendering for Blender.
3. The sales edition excludes PS assistant.
4. Hunyuan3D remains as an external-service interface; users self-deploy and connect their own compatible service.

Useful commands:

- `npm run check:release`: run non-strict sales readiness checks.
- `npm run check:release:strict`: run strict checks before making a buyer build.
- `npm run build:buyer-kit`: assemble buyer docs, landing page, screenshots, and any existing DMGs into `dist/delivery/`.
