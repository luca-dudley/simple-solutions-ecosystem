---
name: supabase-multi-tenant
description: Enforces Supabase multi-tenant RLS, unified auth, and Deno edge function conventions.
---
# Supabase Ecosystem Protocol
1. **Unified Multi-Tenancy**: Every organization has one tenant ID (`organization_id`). Every table across all tools must enforce:
   `auth.jwt() ->> 'organization_id' = organization_id`
2. **Migrations & Functions**:
   - Schema changes go to `supabase/migrations/` using timestamped SQL files.
   - Edge Functions live in `supabase/functions/` and must handle CORS preflights.
3. **Public vs. Protected**: Never expose secret role keys on client files. Client connections only use the public `anon` key.
