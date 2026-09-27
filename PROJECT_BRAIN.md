# Simple Solutions: The Ecosystem Master Brain

## 1. System Overview & Vision

### 1.1 Platform Identity & Purpose
- **Platform Name**: Simple Solutions: The Ecosystem
- **Purpose**: Unified multi-tenant operational suite purpose-built for commercial agriculture, packhouses, logistics, and heavy-labor industrial operations.
- **Core Philosophy**: Replace bloated, complex ERP software with small, fast, frontline-usable field workflows operating on a shared, unified operational engine. The platform feels less like an ERP and more like a collection of purpose-built, offline-capable field tools sitting on a common operational foundation.
- **Operating Context**: Engineered specifically for demanding frontline environments characterized by intermittent or non-existent connectivity (2G/EDGE or offline fields), large non-desk shift workforces, high physical asset velocity, and rigorous statutory compliance demands (GLOBALG.A.P. IFA v6, SIZA, Act 36 of 1947).

### 1.2 Master Strategic Thesis
| Decision Domain | Blueprint Position | Strategic & Compounding Rationale |
| :--- | :--- | :--- |
| **Beachhead Market** | KwaZulu-Natal (KZN) commercial macadamia and banana estates. | High geographic relationship density compresses trust cycles, speeds peer referrals, and lowers deployment friction. |
| **Installed Base Wedge** | **The Vault** (live production system). | Already operational; captures reusable master data (companies, sites, zones, workers, profiles) foundational to all spokes. |
| **Identity Architecture** | **Profiles** for authenticated control-plane staff; **Workers** for frontline field labor. | Eliminates per-seat license taxes and login friction for hundreds of field hands; provides clear supervisory attribution. |
| **Offline Data Model** | **JSON-first transactional outbox sync**; decoupled background attachment queue. | High-priority compliance and operational records sync instantly over poor connectivity without stalling behind heavy photos. |
| **Spray Trace GTM** | **Trojan Horse processor-funded dual portal**. | Anchor agricultural processors/exporters (e.g., Coastal Macadamia) fund and onboard 30–80 supplying growers in single corporate deals. |
| **Module Expansion** | The Vault $\rightarrow$ Spray Trace V1 $\rightarrow$ Discovery-led Fleet & Packhouse $\rightarrow$ Converged Suite. | Disciplined sequencing: build deep spokes only where validated by high-frequency customer pain points. |
| **Pricing & Packaging** | **R2,250 / site / month** flat domestic bundle with unlimited operational users and workers. | Aligns commercial cost directly to operating units rather than penalizing headcount in labor-heavy operations. |

### 1.3 Hub-and-Spoke Ecosystem Model
The platform operates as a centralized master hub that maintains tenancy, authorization, master registries, sync infrastructure, and billing, while projecting operational workflows into lightweight, modular spokes:

```
+-------------------------------- SIMPLE SOLUTIONS HUB ---------------------------------+
| Tenants | Auth Profiles | Workers | Sites | Zones | Assets | Audit Trail Spine        |
| Offline Sync Engine | Media Storage | RBAC Claims | Reports | Notifications | Billing |
+------------------------------------------+--------------------------------------------+
                                           |
            +------------------------------+-----------------------------+
            |                              |                             |
      +-----v------+                 +-----v------+                +-----v------+
      | THE VAULT  |                 | SPRAY TRACE|                | FLEET LOG  |
      | Training   |                 | V1 RECORD  |                | & FUEL     |
      | Compliance |                 | CAPTURE    |                | ALLOCATION |
      +------------+                 +-----+------+                +------------+
                                           |
                                     +-----v------+                +------------+
                                     | PROCESSOR  |                | PACKHOUSE  |
                                     | PORTAL &   |                | PASS       |
                                     | SUPPLIER   |                | INTAKE/QC  |
                                     | NETWORK    |                +-----^------+
                                     +------------+                      |
                                           |                             |
                                           +-----------------------------+
```

### 1.4 Core Architectural & Operational Tenets

#### 1. Worker vs. Profile Identity Split
- **Authenticated Profiles (`profiles`)**: Reserved exclusively for control-plane users (Owners, Admins, Farm Managers, Agronomists, Supervisors, Auditors, Viewers). Profiles hold Supabase Auth accounts (`auth.users`), log in with credentials, and carry JWT custom claims (`company_id`, `role`, authorized `site_ids`).
- **Frontline Workers (`workers`)**: General laborers, tractor drivers, spray operators, and packhouse sorters **never** hold Supabase Auth accounts, do not log in, and do not consume seat licenses. They exist as lightweight entity records attributed to operational events via physical QR badge scanning or supervisor selection. Every frontline transaction captures an authenticated supervisor profile as the verifying/signing party.

#### 2. Offline-First PWA Data Engine
- **Client Storage Engine**: Client-side Dexie.js (IndexedDB) storing working datasets, transactional command outbox, and attachment queues.
- **Decoupled Sync Queue Architecture**:
  1. *JSON Outbox*: Fast transactional command records (`client_uuid`, `command_type`, `entity_table`, `payload`) submit via Edge Function over 2G/EDGE networks immediately upon connectivity.
  2. *Attachment Queue*: Photos, signed PDFs, and media are queued separately in IndexedDB and uploaded via signed Supabase Storage URLs only when strong bandwidth is confirmed. Media upload retries in the background never block compliance record persistence.
- **Idempotency Guarantee**: All client operations generate a client-side UUIDv4 (`client_uuid`). Retries or reconnects are strictly idempotent; duplicate UUIDs return original results without creating ghost rows.
- **Four-State Transaction Standard**: Field interfaces expose only four clear sync states:
  1. *Saved Locally* (Queued in IndexedDB outbox).
  2. *Syncing* (Active network push).
  3. *Synced* (Server-confirmed and written).
  4. *Action Required* (Validation rejection or conflict needing supervisor attention).

#### 3. The 30-Second Transaction Standard
Every frontline operational interaction is designed to execute on a single mobile screen in under 30 seconds with minimal free-text typing:
- **Worker Acknowledgement**: Scan worker QR badge $\rightarrow$ display SOP summary $\rightarrow$ worker acknowledges $\rightarrow$ supervisor verifies $\rightarrow$ immediate save.
- **Spray Record**: Select pre-loaded Site $\rightarrow$ select Zone/Block $\rightarrow$ pick authorized Chemical $\rightarrow$ input volume/quantity $\rightarrow$ select Operator $\rightarrow$ save.
- **Pre-Start Inspection**: Scan asset QR $\rightarrow$ complete binary checklist (pass/fail) $\rightarrow$ critical defect flag triggers instant asset restriction $\rightarrow$ submit.
- **Fuel Issue**: Select Tank $\rightarrow$ scan Asset $\rightarrow$ input meter reading and dispensed liters $\rightarrow$ immutable ledger entry logged.
- **Bin Intake**: Scan bin barcode $\rightarrow$ record gross/tare scale weight $\rightarrow$ link origin site/block $\rightarrow$ print/assign intake lot.

#### 4. Anti-Per-Seat, Flat Site Commercial Model
- Traditional SaaS per-seat pricing fails in agriculture and heavy industry because estates employ hundreds of seasonal laborers. Pricing per seat creates a perverse incentive to exclude frontline workers from digital records.
- **Domestic Commercial Packaging**: Flat **R2,250 / site / month** for the complete ecosystem suite with unlimited workers, unlimited assets, and unlimited operational users.
- **International Tier**: Flat **US$249+ / AUD$299+ / site / month**.
- **Processor-Funded Model**: Dual-portal setup where agricultural processors fund network access for supplying growers to secure standardized compliance data.

### 1.5 Target Personas & Market Segmentation
| Industry Segment | Primary Buyer | Daily Field Operator | Core Operational Pain Points | Primary Success Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **Commercial Farm** | Estate GM / Farm Owner | Production Supervisor / Compliance Officer | Lost paper records, training evidence gaps, audit panic, unverified field work. | $>95\%$ routine workflow capture; $<2$ hours audit pack preparation. |
| **Agronomy & Production** | Head Agronomist / Technical Lead | Spray Supervisor / Chemical Operator | Paper spray sheets, withholding period infractions, processor export friction. | $100\%$ chemical application traceability; zero export shipment rejections. |
| **Packhouse & Processing** | Packhouse General Manager | Intake Clerk / Quality Control Sorter | Intake bottlenecks, manual lot-to-pallet transcription errors, recall vulnerability. | Complete tree-to-pallet traceability; zero spreadsheet stitching. |
| **Logistics & Fleet** | Fleet / Workshop Manager | Tractor Driver / Workshop Mechanic | Missed pre-starts, unmetered diesel shrinkage, unexpected breakdowns, untracked repairs. | $>95\%$ pre-start compliance; reduced unallocated fuel variance to $<1.5\%$. |
| **Manufacturing & Processing** | Plant Operations Manager | Shift Foreman / Line Operator | Paper checksheets, unverified tool calibration, delayed maintenance ticket escalations. | $100\%$ digitised shift safety checks; audited corrective action closures. |
| **Heavy Construction** | Safety Manager / Ops Director | Site Supervisor / Safety Representative | Toolbox talk attendance records, plant pre-inspections, subcontractor compliance. | Verified digital sign-offs; instant cross-site safety audit packs. |

### 1.6 Land-and-Expand Migration Strategy
The platform expands within an enterprise across six predictable stages, continuously compounding the master data foundation:
1. **Stage 1: The Vault (Wedge)**: Company and sites registered; managers invited; SOPs loaded via Vimeo; initial statutory checklists run. *Master Data Captured*: `companies`, `sites`, `profiles`, module settings.
2. **Stage 2: Worker Directory**: Labor force imported from payroll CSVs once; privacy-preserving QR tokens issued; zero worker logins required. *Master Data Captured*: `workers` (`employee_code`, `full_name`, `preferred_language`, `worker_group`, `consent_flags`).
3. **Stage 3: Spray Trace V1**: Agronomic spoke toggled on; historical spray logs ingested; farm linked to downstream processor network. *Master Data Captured*: `zones` (spatial GIS blocks), `spray_applications`, `spray_product_library`, `spray_supplier_links`.
4. **Stage 4: Fleet Log & Fuel Track**: Machinery and fuel tanks activated against established sites and worker operators. *Master Data Captured*: `assets`, `fuel_tanks`, `asset_inspections`, `fuel_events`, `asset_defects`.
5. **Stage 5: Packhouse Pass**: Traceability extended to processing intake; linking orchard blocks to bins, lots, and pallets. *Master Data Captured*: `intake_records`, `quality_tests`, `pack_lots`, `pallets`, `dispatches`.
6. **Stage 6: Converged Ecosystem**: Unified operations cockpit enabled; cross-tool executive dashboards, automated consolidated audit packs, unified Paystack billing. *Master Data Captured*: Cross-module audit spine, consolidated compliance index.

## 2. Directory & Application Map

### 2.1 Monorepo Structure & Operational Mapping
The repository is structured as a zero-build, modular monorepo where the central `portal/` provides administrative governance and shared services, while individual `tools/` operate as decoupled, offline-capable micro-applications:

```
simple-solutions-ecosystem/
├── portal/                          # Central Hub: Administration, Auth, Worker Registry & Billing
│   ├── index.html                   # Public landing page & application launcher
│   ├── dashboard/                   # Unified operations cockpit & cross-tool analytics
│   ├── admin/                       # Tenant admin: company setup, site/zone management, module toggles, Paystack billing
│   └── assets/                      # Shared portal styling, icons, and client scripts
├── tools/                           # Modular operational spokes (decoupled micro-apps)
│   ├── vault/                       # LIVE CORE: Operations, Training & Compliance
│   │   ├── docs/                    # Standard Operating Procedures & compliance specifications
│   │   └── assets/                  # Vault-specific client logic, Vimeo embed player, checklist UI
│   ├── spray-trace/                 # UPCOMING (M1-M4): Agronomic compliance & processor network
│   │   └── assets/                  # Offline spray form, GIS block selector, processor export mapper
│   ├── fleet-log/                   # DISCOVERY-LED: Machinery pre-starts, fuel ledger & maintenance
│   │   └── assets/                  # Pre-start forms, tank dip calculator, defect ticketing UI
│   └── packhouse-pass/              # DISCOVERY-LED: Intake scanning, QC testing & lot traceability
│       └── assets/                  # Bin barcode reader, QC sample forms, pallet dispatch builder
├── packages/                        # Shared contracts, database schemas & design tokens
│   ├── db/                          # Master DDL schemas, migration manifests, and database views
│   ├── shared-types/                # TypeScript interface definitions (profiles, workers, sync contracts)
│   └── ui/                          # Mobile-first Tailwind tokens, QR scanners, and sync status badges
├── supabase/                        # Unified backend infrastructure
│   ├── migrations/                  # Timestamped multi-tenant PostgreSQL migrations with RLS
│   └── functions/                   # Deno Edge Functions (sync_inbox, processor_bridge, audit_pack)
├── scripts/                         # Operational automation (schema synchronization, seed scripts)
├── .agents/                         # Autonomous engineering personas and domain skills
├── AGENTS.md                        # Master agent behavioral rules and instructions
└── PROJECT_BRAIN.md                 # Primary architectural source of truth
```

### 2.2 Tool Specification: The Vault (Live Core — Operations, Training & Compliance)
The Vault is the operational foundation of the ecosystem. It provides continuous training delivery, SOP version governance, and audit-ready verification trails without requiring field labor to interact with complex administrative software.

#### 1. Core Architecture & Vimeo Integration
- **Media Delivery Layer**: Vimeo Enterprise/Pro provides video streaming, transcode optimization, and multi-language captions.
- **Authoritative Compliance Engine**: Simple Solutions retains strict custody over all compliance metadata: SOP code, title, version lineages, worker assignments, digital completion receipts, and cryptographic verification hashes.

#### 2. Functional Delivery Pipeline
| UI Surface / Capability | Key Operational Fields | Core Validation Rules | Deterministic Audit Output |
| :--- | :--- | :--- | :--- |
| **Training Library** | SOP code, title, Vimeo asset ID, version number, effective date, target worker groups, site scope, document owner. | Enforce version code uniqueness; effective date $\le$ current date; supervisor sign-off required. | Controlled SOP Register & Version History log. |
| **Worker Assignment** | Worker ID, SOP/training asset ID, deadline date, site ID, assigning manager profile ID. | Worker must be active (`active = true`) and within authorized site scope. | Outstanding Training Matrix & Skills Gap report. |
| **Completion Verification** | Worker ID, SOP version, completion timestamp, supervising verifier profile, device metadata, `client_uuid`, evidence hash. | Verifier must hold authenticated supervisor+ role; transaction is strictly idempotent (duplicate-safe). | Statutory Training Completion Register with supervisor sign-off. |
| **Digital Checklists** | Checklist template ID, criterion ID, pass/fail/na status, mandatory defect comments, photo attachments. | Required criteria cannot be bypassed; negative answers require comment or photo evidence. | Audit-ready Checklist Evidence Pack with non-conformance flags. |
| **Worker QR Scanning** | Worker token string, scan action type, site ID, scan timestamp, verifier profile ID. | Token validated against active tenant cache; token expiration verified; tenant boundary strictly isolated. | Field Verification & Attendance Trail. |
| **Digital Signatures** | Signer entity (Worker or Profile), entity reference, signature capture method (touch/stylus), timestamp, record SHA-256 hash. | Append-only storage; signature cannot be altered; corrections create a linked superseding event. | Legally defensible Signature Register. |

#### 3. Near-Term Hardening & Single-Click Audit Packs
- **Privacy-Preserving Worker QR Badges**: Workers carry physical or laminated QR badges containing an opaque cryptographic token (`worker_qr_tokens`). The QR payload **never contains PII** (no names, ID numbers, or contact details). The token resolves strictly on the server or authenticated local cache to a worker ID within the authorized tenant.
- **Automated Audit Pack Engine**: Generates a deterministic directory structure and human-readable PDF index compiling all evidentiary documentation required for certification audits (specifically targeting **GLOBALG.A.P. IFA v6** and **SIZA** social standards):
```
AUDIT-PACK/
├── manifest.json                    # Cryptographic hash manifest of all enclosed records
├── index.pdf                        # Human-readable executive summary and certification index
├── 01_company/                      # Company profile, site registers, organogram, role matrix
├── 02_people_training/              # Worker registers, training completion matrix, signature trails
├── 03_sops_compliance/              # Active SOP register, completed checklist runs, corrective actions
├── 04_spray_trace/                  # Zone/orchard register, Act 36 application logs, processor slips
├── 05_fleet/                        # Asset register, daily pre-start inspections, defect registers
├── 06_packhouse/                    # Intake records, QC test logs, batch lineage, dispatch manifests
└── 07_audit_trail/                  # Immutable audit log entries, sync history, exception reports
```

### 2.3 Tool Specification: Spray Trace V1 (Upcoming — 2-4 Month Execution Window)
Spray Trace V1 is an agronomic compliance and record-capture solution engineered specifically for high-risk export crops (macadamias, bananas, citrus, avocado). It solves the burden of field spray log generation and exporter reporting.

#### 1. Scope Boundary & South African Act 36 Compliance
- **V1 Scope Boundary**: Spray Trace V1 is strictly a **record-capture, verification, and distribution tool**. It intentionally defers complex tank-mix calculators and dynamic multi-destination MRL (Maximum Residue Limit) engines to later versions.
- **Statutory Boundary (Act 36 of 1947)**: All agricultural remedies applied in South Africa are regulated under Act 36 of 1947. Spray Trace manages chemical registrations, active ingredients, standard application rates, and withholding period thresholds as controlled master reference data (`spray_product_library`). The software enforces record completeness and policy validation without prescribing agronomic recipes, ensuring professional agronomists retain full statutory responsibility.

#### 2. V1 Capability & Build Decisions
| V1 Feature Capability | Build Status | Strategic & Operational Rationale |
| :--- | :--- | :--- |
| **Offline Field Spray Form** | **Build Now** | Essential field behavior: spray operators and supervisors must record applications in remote blocks with zero mobile signal. |
| **Historical Block Spray Log** | **Build Now** | Ingests spreadsheet histories to make the platform immediately useful for seasonal auditing from day one. |
| **Zone/Block Spatial Reference** | **Build Now (Lightweight)** | Simple PostGIS boundaries or block identifiers for reliable site-zone mapping and spatial lineage. |
| **Authorized Chemical Library** | **Build Now** | Master tenant library referencing Act 36 registration numbers, withholding intervals, and dosage limits. |
| **Processor CSV Export Profiles** | **Build Now** | One-click export formatted to exact commercial processor schemas (the economic driver for processor adoption). |
| **Dynamic Destination MRL Engine** | **Deferred (V2)** | Destination-market regulations shift frequently; requires dedicated agronomy data feeds not essential for V1 records. |
| **Complex Tank-Mix Calculator** | **Deferred (V2)** | Introduces high legal and formulation liability; deferred until field data capture is fully stabilized. |

#### 3. Trojan Horse Dual-Portal Architecture & Data Routing
Spray Trace utilizes an enterprise dual-portal model to overcome the friction of selling to individual commercial farms:
1. **Farm Entrance (Supplier PWA)**: Used by farm managers and spray supervisors. Pre-loads authorized chemical libraries, blocks, and workers. Allows instant offline recording with zero login barriers for operators.
2. **Exporter / Processor Master Dashboard**: Used by central processor compliance officers (e.g., Coastal Macadamia). Provides real-time visibility over all supplying farms, highlighting missing submissions, pending withholding periods, or compliance anomalies.
3. **Cross-Tenant RLS & Data Protection**:
   - Supplier farm tables (`spray_applications`) are strictly isolated by Row-Level Security.
   - The processor browser **never** queries supplier databases directly.
   - An Edge Function checks the active supplier agreement (`spray_supplier_links`) and projects validated summary rows (`spray_processor_submissions` storing `export_row` JSON) into the processor's tenant space.

```
[ Farm Tenant: Spray Operator ]
              │ (Offline Field Record)
              ▼
    spray_applications  ─────────┐
    (Strict Supplier RLS)         │
                                  ▼
                    [ Edge Function Link Validator ]
                    • Validates active supplier relationship
                    • Verifies Act 36 data completeness
                    • Projects sanitized export row
                                  │
                                  ▼
[ Processor Tenant: Compliance ] ◀┘
    spray_processor_submissions (export_row JSON)
              │
              ▼ (1-Click Deterministic Export)
    [ Processor-Formatted CSV / Audit Log ]
```

#### 4. Processor-Funded Commercial Model
- **Setup Fee**: R5,000 – R10,000 one-time (planning anchor: R7,500) covering network mapping, supplier onboarding, and CSV schema configuration.
- **Tier 1 (0–50 Linked Farms)**: R5,500 – R8,000 / month (planning anchor: R7,500 / month).
- **Tier 2 (51–150 Linked Farms)**: R10,000 – R15,000 / month (planning anchor: R12,500 / month).
- **Variable Supplier Usage**: R120 – R150 / farm / month (planning anchor: R135 / farm / month).

#### 5. V1 Six-Step Field Operational Workflow
| Step | Operator Field Action | Server-Side Validation Rule | Stored Operational Evidence |
| :---: | :--- | :--- | :--- |
| **1. Import History** | Upload historical spray spreadsheets via CSV wizard. | Validate column mapping, date ranges, and Act 36 chemical names against library. | Batch import record with source row lineage hash. |
| **2. New Record** | Select Site $\rightarrow$ Block/Zone $\rightarrow$ Product $\rightarrow$ Date $\rightarrow$ Worker $\rightarrow$ Liters. | Validate active site-zone linkage, valid operator assignment, and positive dosage. | Draft application event with client-generated `client_uuid`. |
| **3. Offline Save** | Tap "Save Application" while in remote orchard. | Client Dexie.js accepts write immediately; sets status to `queued`. | Local outbox record in IndexedDB; no network required. |
| **4. Cloud Sync** | Device reconnects to Wi-Fi/cellular network. | Atomic Edge Function transaction; verifies tenant boundaries and writes audit trail. | Immutable database record in `spray_applications` with sync receipt. |
| **5. Processor Route** | Automatic background projection trigger. | Validates processor-grower link; generates sanitized `export_row` JSON payload. | Record created in processor tenant `spray_processor_submissions`. |
| **6. Exporter Output**| Processor compliance officer filters by supplier/date and clicks "Export". | Generates deterministic CSV with fixed column ordering and cryptographic export hash. | Downloaded CSV export file + export audit event log. |

### 2.4 Tool Specification: Fleet Log & Fuel Track (Discovery-Led Spoke)
Fleet Log & Fuel Track digitizes machinery operations and bulk fuel distribution across commercial estates, addressing heavy paper loss, unmetered diesel shrinkage, and machinery neglect.

#### Operational Workflows & System Escalations
| Operational Workflow | Primary Input Fields | System State & Generated Output | Failure & Escalation Path |
| :--- | :--- | :--- | :--- |
| **Daily Pre-Start Inspection** | Asset QR scan, operator worker ID, current hour/km meter reading, binary checklist responses, fault photos. | Recorded inspection event; status badge updated (`active` or `restricted`). | Critical failure triggers immediate asset restriction (`status = 'restricted'`) and opens defect ticket. |
| **Fuel Dispensing Ledger** | Source tank ID, receiving asset ID, authorized worker ID, dispensed volume (L), hour meter, timestamp. | Immutable ledger entry in `fuel_events`; updates asset fuel consumption profile. | Variance exceeding site threshold ($>10\%$ consumption variance) flags supervisor inspection alert. |
| **Bulk Tank Dip Reconciliation**| Storage tank ID, physical dipstick reading (cm/mm), calibration chart volume lookup, timestamp. | Dip record logged in `fuel_events`; computes physical vs. theoretical book stock balance. | Unexplained negative discrepancy exceeding tolerance triggers immediate diesel shrinkage investigation. |
| **Service & Maintenance** | Asset ID, maintenance tier (50h, 250h, 500h, 1000h), service due meter/date, parts replaced, vendor invoice. | Service log updated; preventive maintenance intervals reset for next cycle. | Overdue service triggers persistent visual warning on manager dashboard and restricted status if ignored. |
| **Defect Lifecycle Management** | Asset ID, fault severity (`critical`, `major`, `minor`), fault description, component location, photo evidence, assignee. | Defect ticket logged in `asset_defects`; assigned to maintenance mechanic. | Critical defects restrict asset operation until formal repair sign-off by workshop manager. |

### 2.5 Tool Specification: Packhouse Pass (Discovery-Led Spoke)
Packhouse Pass provides an unbroken physical-to-digital chain of custody from orchard bin intake through grading, quality testing, cold chain staging, and container dispatch.

#### Five-Stage Intake-to-Dispatch Traceability Pipeline
```
[ 1. Bin Intake ] ──▶ [ 2. Quality Testing ] ──▶ [ 3. Grading & Pack ] ──▶ [ 4. Palletization ] ──▶ [ 5. Dispatch ]
  Bin Barcode           Sample Draw               Input Lot ──▶ Packs       SSCC Pallet Tag       Container Manifest
  Gross/Tare/Net        Brix, Moisture, SKR       Grade / Sizing            Carton/Bag Count      Seal & Port Clear
```

| Pipeline Stage | Capture Fields & Telemetry | Traceability & Ledger Output |
| :--- | :--- | :--- |
| **Stage 1: Bin Intake** | Physical bin barcode scan, supplier ID, source farm site, harvest orchard block/zone, commodity cultivar, gross weight, tare weight, net fruit weight, intake timestamp. | Links physical orchard harvest directly to internal `intake_records`. |
| **Stage 2: Quality Testing** | Intake lot sample ID, test category (internal quality, brix, moisture content %, pressure, visual defect %, sound kernel recovery [SKR] for macadamias), measured values, calibrated instrument ID, testing technician worker ID. | Quality certification linked to source batch; determines grade eligibility and grower payment grade. |
| **Stage 3: Grading & Pack** | Source intake lot IDs, grading run ID, packing line ID, fruit size distribution, pack grade classification, recovery yield %, reject bin weight, line supervisor worker ID. | Translates raw intake lots into graded output inventory (`pack_lots`). |
| **Stage 4: Palletization** | Unique Pallet ID / SSCC barcode, output pack lot reference, product SKU, carton/bag count, total gross/net weight, cold storage bay / staging location. | Creates standardized pallet record (`pallets`) ready for commercial distribution. |
| **Stage 5: Container Dispatch** | Shipping load ID, transport vehicle registration, driver worker ID, attached pallet IDs, customer sales order, destination port and country, container security seal number, departure timestamp. | Immutable dispatch dossier (`dispatches`); generates complete backward trace from export pallet back to orchard block. |

### 2.6 Cross-Tool Authorization & Role-Based Access Control (RBAC)
Every operational module enforces explicit boundaries across user roles:
| Module Code | Target Domain | Read Access | Write / Capture Access | Approval / Verification Access | Administrative Governance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CORE` | Portal & Hub | Permitted tenant data | Admin roles | Owner / Admin | Owner |
| `VAULT` | Compliance & Training | Assigned profiles & workers | Supervisor+ profile | Manager / Agronomist+ | Admin+ |
| `WORKER` | People Registry | Permitted tenant data | Supervisor+ (no worker login) | Manager / Supervisor | Admin+ |
| `SPRAY` | Spray Trace | Site application logs | Supervisor+ profile | Manager / Agronomist | Admin+ |
| `FLEET` | Fleet & Fuel | Equipment & fuel logs | Driver / Operator (via Supervisor) | Workshop Manager | Admin+ |
| `PACK` | Packhouse Pass | Intake & packing logs | QC / Intake Clerk | Packhouse Manager | Admin+ |

### 2.7 Cross-Tool Data Contracts & Conflict Resolution
To maintain database integrity across offline PWA devices, all tools adhere to uniform data exchange contracts and conflict handling rules:

#### 1. Standard Offline Command Contract
```json
{
  "client_uuid": "c39b8627-c104-4c4d-b6a9-8f3f8fcae12a",
  "command_type": "spray.application.create",
  "entity_table": "spray_applications",
  "entity_id": null,
  "payload": {
    "site_id": "8f8b8a5e-2f22-4412-b13c-7df039a89632",
    "zone_id": "4e76a6cf-82e0-47b2-bd74-e3f9a74e502b",
    "worker_id": "18cfd6f8-cb6c-4876-b631-0c3ff411a7a2",
    "applied_at": "2026-09-27T06:30:00Z",
    "actual_quantity": 450.5,
    "quantity_unit": "litres"
  },
  "dependency_client_uuids": [],
  "created_at": "2026-09-27T06:35:12Z"
}
```

#### 2. Conflict Resolution Matrix
| Concurrency Scenario | Automated Resolution Rule | Operational Action Required |
| :--- | :--- | :--- |
| **Duplicate Command** | First accepted `client_uuid` persists; retries return original result idempotently. | None; transparent to client. |
| **Stale Master Record** | Server master data (`workers`, `sites`, `products`) is authoritative; refreshes local cache. | Prompt operator only if transaction invalid under new master data. |
| **Negative Stock Event** | Reject transaction where inventory policy forbids negative balance; emit sync exception. | Storekeeper or supervisor resolves physical stock variance. |
| **Concurrent Compliance Records** | Append both distinct UUID events into database; never overwrite historical compliance rows. | Compliance officer reviews audit trail during scheduled sign-off. |
| **Media Attachment Failure** | Parent transactional JSON record remains committed; attachment queue retries independently. | User notified only if evidence attachment fails after maximum retry limit. |
| **Zone Geometry Updates** | Historical application logs retain historical `zone_version_id`; new coordinates increment version. | GIS administrator manages zone version lifecycle. |

## 3. Core Architectural Boundaries & Constraints
- **Multi-Tenant Isolation**: All database operations MUST filter strictly by `company_id` (or `organization_id`). Every tenant-owned row enforces RLS against JWT app_metadata (`company_id`, `role`, authorized `site_ids`). Cross-tenant access (e.g. processor dashboard) MUST use server-side projections via Edge Functions, never direct cross-tenant queries.
- **Worker vs. Profile Identity Boundary**: Control-plane users (`profiles`) hold Supabase Auth accounts and JWT claims. Frontline staff (`workers`) never authenticate directly; they are attributed via QR badge scans or supervisor verification.
- **Zero-Build Vanilla Delivery**: Keep static portal and operational tools purely Vanilla HTML5, ES6 modules, and Tailwind CSS unless an isolated sub-package explicitly specifies a build step.
- **Offline-First Resilience**: Mobile tools must operate fully offline using client-side IndexedDB (Dexie.js). High-priority transactional JSON commands sync via an outbox over 2G/EDGE networks; heavy binary attachments queue separately and upload in the background over strong connectivity.
- **Loosely Coupled Micro-Apps**: Tools must function independently while reading shared user identity, active site context, and permissions from the unified portal session.

## 4. Third-Party Integrations
- **Supabase**: PostgreSQL database (with PostGIS and RLS), multi-tenant Auth, Storage buckets (evidence photos, documents), and Deno Edge Functions (sync outbox handler, processor projection bridge, audit-pack generator).
- **Vimeo**: Secure streaming media delivery layer for Standard Operating Procedures (SOPs) and training videos in The Vault; Simple Solutions manages authoritative version metadata, worker assignments, and cryptographic completion receipts.
- **Paystack**: Consolidated platform billing and modular tool licensing supporting flat site-tier subscriptions (R2,250/site/month domestic bundle).
- **Cloudflare Pages / Hosting**: Unified routing or subdomain delegation for portal and individual tools.

## 5. Active Database & Schema Status
- Canonical multi-tenant schema definitions tracked in `packages/db/` and `supabase/migrations/`, synchronized via `./scripts/sync_schema.sh`.
- Primary master tables: `companies`, `sites`, `zones`, `zone_versions`, `profiles`, `workers`, `worker_qr_tokens`, `site_profile_access`, `company_modules`, `audit_events`, `sync_inbox`, `attachments`.
- Module tables: The Vault (`training_assets`, `training_assignments`, `training_completions`, `checklist_templates`, `checklist_runs`, `checklist_answers`, `signature_events`), Spray Trace (`spray_product_library`, `spray_plans`, `spray_applications`, `spray_application_products`, `agro_stock_locations`, `agro_stock_ledger`, `spray_processor_networks`, `spray_supplier_links`, `spray_processor_submissions`), Fleet Log (`assets`, `asset_meter_events`, `fuel_tanks`, `fuel_events`, `asset_inspections`, `asset_defects`, `asset_service_jobs`), Packhouse Pass (`intake_records`, `quality_tests`, `pack_lots`, `pallets`, `dispatches`, `dispatch_pallets`).
- **Legacy Ingest Mapping & Migration Plan**:
  - Full legacy schema analysis and migration blueprint documented in [`docs/MIGRATION_PLAN.md`](file:///home/luca/dev/simple-solutions-ecosystem/docs/MIGRATION_PLAN.md).
  - Legacy `the-vault-web` schema (18 tables, 1 view) mapped to the Ecosystem master schema.
  - Key architectural transformation: Extraction of free-text workers from legacy `training_records` into the first-class `workers` directory and issuance of privacy-preserving `worker_qr_tokens`.
  - Supabase Auth Custom Access Token Hook (`auth.custom_access_token_hook`) specified to inject `company_id`, `role`, and `site_ids` into JWT claims, eliminating nested subqueries and error `42P17`.
  - Legacy storage buckets (`sops`: 109 documents, `thumbnails`: 106 SVGs) mapped to tenant-isolated storage paths.

## 6. Changelog & Current State
- **2026-09-27**: Completed legacy ingest analysis of `/legacy` codebase and database exports (`the-vault-web`). Generated comprehensive migration plan in [`docs/MIGRATION_PLAN.md`](file:///home/luca/dev/simple-solutions-ecosystem/docs/MIGRATION_PLAN.md) covering entity transformations, two-tier identity enforcement, custom JWT claims hook, decoupled module layout, and 6-phase milestone sign-off roadmap.
- **2026-09-27**: Section 1 and Section 2 fully updated to incorporate the exact feature specifications, operational workflows, product concepts, and architectural definitions from The Ecosystem master blueprint (worker-vs-profile split, offline-first PWA sync, Trojan Horse dual-portal Spray Trace, discovery-led Fleet and Packhouse spokes, and automated audit-pack standards).
- **2026-09-27**: Monorepo scaffolding initialized. Persona agents (`@architect`, `@auditor`, `@closer`) and domain skills (`monorepo`, `supabase`, `responsive-ui`) deployed.

