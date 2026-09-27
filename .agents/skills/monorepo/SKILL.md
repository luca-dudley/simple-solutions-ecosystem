---
name: ecosystem-monorepo
description: Manages cross-tool boundaries, shared assets, and architectural conventions across portal and tools.
---
# Ecosystem Monorepo Guidelines
1. **Directory Boundary**:
   - `portal/`: Unified management dashboard, auth hub, and organization settings.
   - `tools/`: Independent operational apps (`fleet-log`, `packhouse-pass`, `spray-trace`, `vault`). Tools must remain loosely coupled.
   - `packages/`: Shared data contracts (`db`), shared types (`shared-types`), and reusable CSS/visual tokens (`ui`).
2. **Asset Sharing**: Reusable logos and icons live in `packages/ui/assets/` or `portal/assets/`. Never duplicate identical assets across individual tool subfolders.
3. **Vanilla / Zero-Build Runtime**: Preserve static HTML5, ES6 modules, and Tailwind CSS patterns unless a specific package build step is explicitly specified.
