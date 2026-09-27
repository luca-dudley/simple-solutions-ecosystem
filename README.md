# Simple Solutions Ecosystem

> A modular, offline-first operational software suite for commercial agriculture and heavy-labor enterprises.

## Architecture Overview
- **Core Backend:** Supabase (PostgreSQL, Row-Level Security, Custom JWT Claims, Storage, Edge Functions)
- **Client Architecture:** Offline-first Progressive Web Apps (IndexedDB / Dexie.js)
- **Monorepo Layout:**
  - `apps/vault`: Operations, Training (Vimeo SOPs), and OHS/SIZA compliance sign-offs.
  - `apps/spray-trace`: Digital spray logs, tank mixes, and processor intake exports.
  - `apps/fleet-log`: Asset pre-start checks, diesel bowser tracking, and defect registers.
  - `apps/packhouse-pass`: Intake weights, QC moisture/crack-out run charts, and lot tracing.
  - `packages/db`: Supabase client configurations and database types.
  - `packages/shared-types`: Universal TypeScript interfaces (Sites, Zones, Workers, Assets).
  - `supabase/`: Schema migrations, RLS policies, and Edge Function sync handlers.

## Getting Started
Refer to `/docs` for database DDL specifications, offline sync contracts, and development guidelines.
