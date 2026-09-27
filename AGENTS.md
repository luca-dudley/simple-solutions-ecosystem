# Master Agent Instructions

1. **Context Initialization**: Always load and reference `PROJECT_BRAIN.md` as the primary architectural source of truth before planning or modifying code.
2. **Domain Skills**: Consult `.agents/skills/` when dealing with multi-tenant boundaries (`supabase`), monorepo structure (`monorepo`), or styling tokens (`responsive-ui`).
3. **Session Wrap-Up**: Prompt the developer to run `agy --agent closer` at the end of each session to keep `PROJECT_BRAIN.md` aligned with git changes.
