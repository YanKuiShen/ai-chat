# Legal And Risk Checklist

This is a product risk checklist, not legal advice.

## Required Before Public Sale

- Add a root product license or commercial terms for original project code.
- Add a third-party notices page.
- Keep Hunyuan3D `LICENSE` and `NOTICE` files with any Hunyuan-related distribution.
- Confirm PS assistant is hidden and disabled in the sales build.
- Confirm Hunyuan3D is presented as an external-service interface, not as a bundled model service.
- Keep MIT attribution for blender-mcp-derived code.
- State that Tencent is not affiliated with, sponsoring, or endorsing the product.
- State that API providers and models are third-party services.
- State that users bring their own API keys and pay their own model usage costs.
- State that generated outputs are the user's responsibility.
- State that 3D quality is not guaranteed.
- State that Blender is required for Blender/3D features.

## Hunyuan3D Notes

The sales edition keeps a Hunyuan3D external-service interface, but does not bundle Hunyuan3D model service, model weights, official access, or compute. If users self-deploy or connect a compatible service, they must follow the original Hunyuan3D license.

The Hunyuan3D license in this repo includes important restrictions:

- Territory excludes the European Union, United Kingdom, and South Korea.
- Commercial use above the license threshold may require Tencent approval.
- Users must follow the acceptable use policy.
- Hunyuan3D outputs/results must not be used to improve other AI models except as allowed by the license.
- Distribution must include the required license and notice text.

Commercial website copy must not imply:

- Tencent endorsement.
- unrestricted global availability of Hunyuan3D-related functionality.
- unrestricted commercial output rights.
- bundled Hunyuan3D hosting, model weights, official service access, or compute.

## Screenshot Review

Before public posting, review every screenshot for:

- API provider names.
- API keys or partial keys.
- Local file paths.
- Private project names.
- User data.
- Internal-only wording such as "学习交流" if it conflicts with paid positioning.

Current screenshots do not show API keys, but some show provider labels and local paths. They are acceptable for internal planning but should be cleaned or cropped before paid ads.

## Refund Policy Draft

Suggested simple policy:

> 数字产品发货后原则上不支持无理由退款。若软件无法在支持的 macOS 版本上启动，且在 7 天内配合排查仍无法解决，可申请退款。第三方 API、Blender、模型费用和生成结果质量不属于退款范围。

## Support Boundary

State clearly:

- Support covers installation and documented workflow.
- Support does not cover third-party API outages.
- Support does not cover all Blender scripting customization.
- Support does not guarantee a specific artistic result.
