# Security Policy

## Do Not Commit Private Data

This project is designed to run locally. Keep these files and folders private:

- `.env`, `.env.*`
- `data/configs.json`
- `data/sessions.json`
- `data/chat.db*`
- `data/asset_index.json`
- `data/realtime_workflows/`
- `3d/Hunyuan3D-2-weights/`
- `3d/Hunyuan3D-2mini-weights/`
- build outputs, logs, caches, and local virtual environments

The repository includes `.env.example` only as a safe template. Put real API keys,
private base URLs, cookies, user sessions, local workflow records, and model
weights in ignored local files only.

## Reporting

If you find a security issue, please avoid posting secrets or exploit details in
public issues. Contact the maintainer first, then open a sanitized issue once the
risk is understood.
