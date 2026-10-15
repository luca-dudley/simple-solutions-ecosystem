-- ============================================================================
-- Simple Solutions Ecosystem: Unified Production Database Architecture
-- Migration: 20261015000000_unified_core_foundation.sql
-- Architecture Specification: docs/architecture/UNIFIED_DATABASE_ARCHITECTURE.md
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 1. Custom Types & Enumerations
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE public.billing_tier AS ENUM (
        'bundle',                 -- Full Site Bundle (The Vault + Spray Trace + Conduit + Packhouse Pass)
        'standalone_vault',       -- The Vault (OHS & Training Compliance Core)
        'standalone_conduit',     -- Supply Conduit (WhatsApp Procurement)
        'standalone_spray',       -- Spray Trace V1 (Act 36 Chemical Traceability)
        'standalone_packhouse',   -- Packhouse Pass (Weighbridge & QC Intake)
        'enterprise'              -- Bespoke Custom Workflows & Multi-Site Estates
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE public.user_role AS ENUM (
        'owner',          -- Primary account holder; full billing & administrative authority
        'admin',          -- Estate manager / operational controller
        'farm_manager',   -- Site supervisor / production director
        'buyer',          -- Procurement officer managing PO placement & quotes
        'supervisor',     -- Field supervisor verifying training, pre-starts & requisitions
        'agronomist',     -- Technical compliance & chemical advisor (Spray Trace)
        'auditor',        -- Read-only statutory auditor (SIZA / GLOBALG.A.P. inspection role)
        'viewer'          -- Read-only dashboard viewer
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE public.requisition_status AS ENUM (
        'LOGGED',       -- Received via WhatsApp ingest or mobile outbox
        'APPROVED',     -- Manager tapped approval
        'PO_PLACED',    -- PO generated and transmitted to supplier
        'RECEIVED',     -- Delivered to site; delivery slip photographed
        'RECONCILED',   -- Invoice matched with delivery slip
        'CANCELLED'     -- Rejected or duplicate
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE public.urgency_level AS ENUM (
        'ROUTINE',
        'URGENT',
        'CRITICAL'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE public.sync_status AS ENUM (
        'PENDING',
        'PROCESSED',
        'CONFLICT',
        'REJECTED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Sequences
-- ----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.requisition_ref_seq START WITH 1001;
CREATE SEQUENCE IF NOT EXISTS public.po_number_seq START WITH 5001;

-- ----------------------------------------------------------------------------
-- 3. Core Multi-Tenant Foundation (Hub Plane)
-- ----------------------------------------------------------------------------

-- 3.1 Corporate Partners (Subsidizers / Processors)
CREATE TABLE IF NOT EXISTS public.corporate_partners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    sponsored_crop_pack TEXT NOT NULL,
    logo_url TEXT,
    contact_email TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3.2 Companies (Tenant Master Entity)
CREATE TABLE IF NOT EXISTS public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    company_code VARCHAR(6) UNIQUE NOT NULL,
    billing_tier public.billing_tier NOT NULL DEFAULT 'bundle',
    is_active BOOLEAN NOT NULL DEFAULT true,
    currency VARCHAR(3) NOT NULL DEFAULT 'ZAR',
    timezone TEXT NOT NULL DEFAULT 'Africa/Johannesburg',
    
    -- Corporate Partner Subsidy Linkage
    partner_id UUID REFERENCES public.corporate_partners(id) ON DELETE SET NULL,
    is_subsidized BOOLEAN NOT NULL DEFAULT false,
    
    -- Billing Metadata (Encapsulated JSONB)
    billing_metadata JSONB NOT NULL DEFAULT '{
        "provider": "paystack",
        "customer_code": null,
        "subscription_code": null,
        "plan_code": null,
        "billing_email": null,
        "status": "active",
        "next_payment_date": null,
        "billing_interval": "monthly"
    }'::jsonb,
    
    -- Operational Tenancy Settings
    settings JSONB NOT NULL DEFAULT '{
        "require_zone_for_requisitions": false,
        "duplicate_window_days": 7,
        "auto_approve_threshold_zar": 0.00,
        "require_supervisor_signature": true,
        "default_language": "en"
    }'::jsonb,
    
    -- Statutory & Commercial Identity
    vat_number TEXT,
    postal_address TEXT,
    phone TEXT,
    contact_email TEXT,
    company_stamp_url TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    CONSTRAINT ck_company_code_format CHECK (company_code ~ '^[A-Z0-9]{2,6}$')
);

CREATE INDEX IF NOT EXISTS idx_companies_slug ON public.companies(slug);
CREATE INDEX IF NOT EXISTS idx_companies_partner_id ON public.companies(partner_id) WHERE partner_id IS NOT NULL;

-- 3.3 Partner Grower Registry & Tokens
CREATE TABLE IF NOT EXISTS public.partner_grower_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES public.corporate_partners(id) ON DELETE CASCADE,
    grower_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    contact_email TEXT,
    claimed_by_company_id UUID REFERENCES public.companies(id) ON DELETE SET NULL,
    claimed_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    CONSTRAINT uq_partner_grower_code UNIQUE (partner_id, grower_code)
);

CREATE TABLE IF NOT EXISTS public.partner_portal_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES public.corporate_partners(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL DEFAULT (gen_random_uuid())::text,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + '90 days'::interval),
    revoked_at TIMESTAMPTZ
);

-- 3.4 Physical Sites (Farms, Packhouses, Facilities)
CREATE TABLE IF NOT EXISTS public.sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code VARCHAR(20) NOT NULL,
    location_description TEXT,
    gps_coordinates POINT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    CONSTRAINT uq_site_company_code UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_sites_company ON public.sites(company_id);

-- 3.5 Granular Zones (Blocks, Cold Rooms, Bays)
CREATE TABLE IF NOT EXISTS public.zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE, -- Denormalized for zero-join RLS
    site_id UUID NOT NULL REFERENCES public.sites(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code VARCHAR(20),
    zone_type TEXT NOT NULL DEFAULT 'orchard' CHECK (zone_type IN ('orchard', 'workshop', 'packhouse', 'storage', 'general')),
    crop_variety TEXT,
    hectares NUMERIC(8,2),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    CONSTRAINT uq_zone_site_code UNIQUE (site_id, code)
);

CREATE INDEX IF NOT EXISTS idx_zones_company ON public.zones(company_id);
CREATE INDEX IF NOT EXISTS idx_zones_site ON public.zones(site_id);

-- 3.6 Authenticated Control-Plane Profiles
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role public.user_role NOT NULL DEFAULT 'viewer',
    phone_number VARCHAR(20),
    avatar_url TEXT,
    authorized_site_ids UUID[] DEFAULT NULL, -- NULL = all tenant sites authorized
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_profiles_company ON public.profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(company_id, role);

-- 3.7 Universal Frontline Labor (Workers Directory)
CREATE TABLE IF NOT EXISTS public.workers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    employee_number VARCHAR(30),
    id_passport_number TEXT,
    gender TEXT CHECK (gender IS NULL OR gender IN ('Male', 'Female', 'Other')),
    
    -- Omnichannel Attribution Identifiers
    phone_number VARCHAR(20),              -- Normalized E.164 for WhatsApp Procurement
    qr_token TEXT UNIQUE NOT NULL DEFAULT ('WKT-' || gen_random_uuid()::text), -- Physical badge scanning
    
    -- Operational Context
    role_title TEXT NOT NULL,
    default_site_id UUID REFERENCES public.sites(id) ON DELETE SET NULL,
    team_or_orchard TEXT,
    preferred_language VARCHAR(10) NOT NULL DEFAULT 'en',
    
    -- Compliance & Statutory Consent Flags
    consent_flags JSONB NOT NULL DEFAULT '{
        "popia_data_processing": true,
        "medical_fitness_on_file": false,
        "hazchem_certified": false
    }'::jsonb,
    
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_workers_company ON public.workers(company_id);
CREATE INDEX IF NOT EXISTS idx_workers_phone ON public.workers(company_id, phone_number) WHERE phone_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_workers_employee_num ON public.workers(company_id, employee_number) WHERE employee_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_workers_qr_token ON public.workers(qr_token);

-- ----------------------------------------------------------------------------
-- 4. Spoke 1: The Vault (OHS & Compliance Plane)
-- ----------------------------------------------------------------------------

-- 4.1 Curriculum Videos (Global Library + Tenant Proprietary)
CREATE TABLE IF NOT EXISTS public.videos (
    id TEXT PRIMARY KEY,
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE, -- NULL = Global Library
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Agriculture',
    sub_tag TEXT,
    language TEXT NOT NULL DEFAULT 'English',
    total_seconds INTEGER NOT NULL,
    thumbnail_url TEXT,
    description TEXT,
    objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    curriculum_slug TEXT,
    streams JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4.2 Standard Operating Procedures (SOPs)
CREATE TABLE IF NOT EXISTS public.sops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE, -- NULL = Global Template
    video_id TEXT REFERENCES public.videos(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'Agriculture',
    sub_tag TEXT NOT NULL DEFAULT 'General Safety',
    doc_url TEXT NOT NULL,
    version_number VARCHAR(10) NOT NULL DEFAULT '1.0',
    curriculum_slug TEXT,
    partner_docs JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4.3 Training Records (Cryptographic Competency Proof)
CREATE TABLE IF NOT EXISTS public.training_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    site_id UUID REFERENCES public.sites(id) ON DELETE SET NULL,
    worker_id UUID NOT NULL REFERENCES public.workers(id) ON DELETE RESTRICT,
    video_id TEXT NOT NULL REFERENCES public.videos(id) ON DELETE RESTRICT,
    
    -- Verification Attribution
    completed_at DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'Verified' CHECK (status IN ('Verified', 'Archived', 'Flagged')),
    training_type TEXT NOT NULL DEFAULT 'Individual' CHECK (training_type IN ('Individual', 'Group_Batch')),
    batch_session_id UUID,
    supervisor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    
    -- Immutable Snapshot Data
    worker_snapshot JSONB NOT NULL,
    supervisor_snapshot JSONB NOT NULL,
    
    -- Cryptographic Signature Assets
    signature_url TEXT,
    supervisor_signature_data TEXT,
    worker_signature_data TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_training_records_worker ON public.training_records(company_id, worker_id);
CREATE INDEX IF NOT EXISTS idx_training_records_video ON public.training_records(company_id, video_id);
CREATE INDEX IF NOT EXISTS idx_training_records_date ON public.training_records(company_id, completed_at DESC);

-- 4.4 Risk Assessments (Unified Statutory Baseline & Issue Register)
CREATE TABLE IF NOT EXISTS public.risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES public.sites(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES public.zones(id) ON DELETE SET NULL,
    
    ra_type TEXT NOT NULL CHECK (ra_type IN ('baseline', 'issue_based', 'continuous', 'pre_start')),
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    work_area TEXT,
    equipment_identifier TEXT,
    
    -- Statutory Assessment Timeline
    assessment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    review_due_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Under Review', 'Archived')),
    
    -- Statutory Sign-Off Attribution
    assessor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    assessor_name TEXT NOT NULL,
    assessor_signature TEXT,
    
    -- Structured Risk Registers
    hazards_register JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_ppe JSONB NOT NULL DEFAULT '[]'::jsonb,
    pre_use_checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_tenant ON public.risk_assessments(company_id, site_id);

-- ----------------------------------------------------------------------------
-- 5. Spoke 2: Supply Conduit (Procurement & Requisitions Plane)
-- ----------------------------------------------------------------------------

-- 5.1 Requisitions
CREATE TABLE IF NOT EXISTS public.requisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    reference_code VARCHAR(32) UNIQUE NOT NULL,
    po_number VARCHAR(32) UNIQUE,
    
    -- Frontline Spatial Context
    site_id UUID NOT NULL REFERENCES public.sites(id) ON DELETE RESTRICT,
    zone_id UUID REFERENCES public.zones(id) ON DELETE SET NULL,
    location_detail TEXT,
    
    -- Universal Frontline Requester (Workers Table Link)
    requester_id UUID NOT NULL REFERENCES public.workers(id) ON DELETE RESTRICT,
    
    -- Workflow Status & Priority
    status public.requisition_status NOT NULL DEFAULT 'LOGGED',
    urgency public.urgency_level NOT NULL DEFAULT 'ROUTINE',
    
    -- Omnichannel Input Assets
    raw_message_text TEXT,
    audio_url TEXT,
    media_urls TEXT[] NOT NULL DEFAULT '{}'::text[],
    whatsapp_message_id VARCHAR(128),
    
    -- Duplicate Detection Engine
    is_duplicate_suspect BOOLEAN NOT NULL DEFAULT false,
    duplicate_of_id UUID REFERENCES public.requisitions(id) ON DELETE SET NULL,
    
    -- Purchasing & Commercials
    assigned_buyer_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    supplier_name TEXT,
    total_estimated_zar NUMERIC(12,2) DEFAULT 0.00,
    total_actual_zar NUMERIC(12,2),
    notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_requisitions_company_status ON public.requisitions(company_id, status);
CREATE INDEX IF NOT EXISTS idx_requisitions_site ON public.requisitions(site_id);
CREATE INDEX IF NOT EXISTS idx_requisitions_requester ON public.requisitions(requester_id);

-- 5.2 Requisition Items
CREATE TABLE IF NOT EXISTS public.requisition_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE, -- Denormalized for zero-join RLS
    requisition_id UUID NOT NULL REFERENCES public.requisitions(id) ON DELETE CASCADE,
    item_description TEXT NOT NULL,
    normalized_tokens TEXT,
    quantity NUMERIC(10,2) NOT NULL DEFAULT 1.0,
    unit_of_measure VARCHAR(30) NOT NULL DEFAULT 'units',
    part_number VARCHAR(100),
    pastel_item_code VARCHAR(50),
    unit_price_zar NUMERIC(12,2),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_requisition_items_req_id ON public.requisition_items(requisition_id);

-- ----------------------------------------------------------------------------
-- 6. Offline-First Synchronization Plane (Dexie.js Outbox)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.sync_inbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    client_uuid UUID UNIQUE NOT NULL,      -- Idempotency key generated client-side
    command_type VARCHAR(64) NOT NULL,    -- e.g., 'training.record.create', 'requisition.create'
    entity_table VARCHAR(64) NOT NULL,    -- Target table name
    entity_id UUID,                       -- Resolved server entity ID after execution
    
    payload JSONB NOT NULL,               -- Full transactional command payload
    device_id VARCHAR(64),
    submitted_by_profile_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    
    status public.sync_status NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    processed_at TIMESTAMPTZ,
    client_created_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_sync_inbox_pending ON public.sync_inbox(company_id, status) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_sync_inbox_client_uuid ON public.sync_inbox(client_uuid);

-- ----------------------------------------------------------------------------
-- 7. Functions, Sequences & Triggers
-- ----------------------------------------------------------------------------

-- 7.1 Auto-generate Requisition Reference Code (REQ-YYMM-XXXX)
CREATE OR REPLACE FUNCTION public.fn_generate_requisition_ref()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.reference_code IS NULL OR TRIM(NEW.reference_code) = '' THEN
        NEW.reference_code := 'REQ-' || TO_CHAR(NOW(), 'YYMM') || '-' || LPAD(nextval('public.requisition_ref_seq')::text, 4, '0');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_generate_requisition_ref ON public.requisitions;
CREATE TRIGGER trg_generate_requisition_ref
    BEFORE INSERT ON public.requisitions
    FOR EACH ROW EXECUTE FUNCTION public.fn_generate_requisition_ref();

-- 7.2 Auto-assign PO Number on PO_PLACED Status (PO-YYMM-XXXX)
CREATE OR REPLACE FUNCTION public.fn_assign_po_number()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = 'PO_PLACED' AND (NEW.po_number IS NULL OR TRIM(NEW.po_number) = '') THEN
        NEW.po_number := 'PO-' || TO_CHAR(NOW(), 'YYMM') || '-' || LPAD(nextval('public.po_number_seq')::text, 4, '0');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_assign_po_number ON public.requisitions;
CREATE TRIGGER trg_assign_po_number
    BEFORE UPDATE OF status ON public.requisitions
    FOR EACH ROW EXECUTE FUNCTION public.fn_assign_po_number();

-- 7.3 7-Day Duplicate Detection Routine
CREATE OR REPLACE FUNCTION public.check_7day_duplicates(
    p_site_id UUID,
    p_search_tokens TEXT[],
    p_exclude_requisition_id UUID DEFAULT NULL
) 
RETURNS TABLE (
    suspect_requisition_id UUID,
    reference_code VARCHAR,
    matched_item TEXT,
    created_at TIMESTAMPTZ,
    status public.requisition_status
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
DECLARE
    filtered_tokens TEXT[];
BEGIN
    SELECT ARRAY_AGG(LOWER(TRIM(t))) INTO filtered_tokens
    FROM unnest(p_search_tokens) t
    WHERE LOWER(TRIM(t)) NOT IN (
        'pvc', 'steel', 'plastic', 'fitting', 'joint', 'roll', 'rolls', 'tape',
        'meter', 'meters', 'unit', 'units', 'box', 'boxes', 'bottle', 'bottles',
        'pipe', 'pipes', 'piece', 'pieces', 'size', 'standard', 'heavy', 'duty',
        'and', 'the', 'for', 'with', 'item', 'items', 'bags', 'pack', 'need',
        'urgent', 'urgently', 'please', 'line', 'routine', 'spares', 'parts'
    )
    AND LENGTH(TRIM(t)) >= 4;

    IF filtered_tokens IS NULL OR ARRAY_LENGTH(filtered_tokens, 1) = 0 THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT 
        r.id AS suspect_requisition_id,
        r.reference_code,
        ri.item_description AS matched_item,
        r.created_at,
        r.status
    FROM public.requisitions r
    JOIN public.requisition_items ri ON ri.requisition_id = r.id
    WHERE r.site_id = p_site_id
      AND r.created_at >= (NOW() - INTERVAL '7 days')
      AND r.status != 'CANCELLED'
      AND (p_exclude_requisition_id IS NULL OR r.id != p_exclude_requisition_id)
      AND EXISTS (
          SELECT 1 FROM unnest(filtered_tokens) token
          WHERE ri.item_description ILIKE '%' || token || '%'
      )
    ORDER BY r.created_at DESC
    LIMIT 5;
END;
$$;

-- 7.4 Supabase Auth Custom Access Token Hook
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event JSONB)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    claims JSONB;
    v_company_id UUID;
    v_role TEXT;
    v_site_ids UUID[];
    v_is_active BOOLEAN;
BEGIN
    SELECT company_id, role::text, authorized_site_ids, is_active
    INTO v_company_id, v_role, v_site_ids, v_is_active
    FROM public.profiles
    WHERE id = (event->>'user_id')::uuid;

    claims := event->'claims';

    IF v_is_active IS NOT TRUE OR v_company_id IS NULL THEN
        claims := jsonb_set(claims, '{app_metadata, company_id}', 'null'::jsonb);
        claims := jsonb_set(claims, '{app_metadata, role}', '"unassigned"'::jsonb);
    ELSE
        claims := jsonb_set(claims, '{app_metadata, company_id}', to_jsonb(v_company_id::text));
        claims := jsonb_set(claims, '{app_metadata, role}', to_jsonb(v_role));
        
        IF v_site_ids IS NOT NULL THEN
            claims := jsonb_set(claims, '{app_metadata, site_ids}', to_jsonb(v_site_ids));
        ELSE
            claims := jsonb_set(claims, '{app_metadata, site_ids}', '[]'::jsonb);
        END IF;
    END IF;

    event := jsonb_set(event, '{claims}', claims);
    RETURN event;
END;
$$;

GRANT EXECUTE ON FUNCTION public.custom_access_token_hook(JSONB) TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(JSONB) FROM authenticated, anon, public;

-- 7.5 Atomic Onboarding Bootstrap Function (provision_new_tenant)
CREATE OR REPLACE FUNCTION public.provision_new_tenant(
    p_company_name TEXT,
    p_slug TEXT,
    p_company_code VARCHAR,
    p_owner_full_name TEXT,
    p_user_id UUID DEFAULT auth.uid()
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
    v_email TEXT;
    v_company_id UUID;
BEGIN
    v_user_id := COALESCE(p_user_id, auth.uid());
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'provision_new_tenant: Cannot provision tenant without an authenticated user context or explicit user_id';
    END IF;

    -- Retrieve owner email from auth.users
    SELECT email INTO v_email FROM auth.users WHERE id = v_user_id;
    IF v_email IS NULL THEN
        RAISE EXCEPTION 'provision_new_tenant: No user found in auth.users for id %', v_user_id;
    END IF;

    -- 1. Create company
    INSERT INTO public.companies (
        name,
        slug,
        company_code,
        billing_tier,
        is_active
    ) VALUES (
        p_company_name,
        LOWER(TRIM(p_slug)),
        UPPER(TRIM(p_company_code)),
        'bundle',
        true
    )
    RETURNING id INTO v_company_id;

    -- 2. Create or update owner profile
    INSERT INTO public.profiles (
        id,
        company_id,
        email,
        full_name,
        role,
        is_active
    ) VALUES (
        v_user_id,
        v_company_id,
        v_email,
        p_owner_full_name,
        'owner',
        true
    )
    ON CONFLICT (id) DO UPDATE SET
        company_id = EXCLUDED.company_id,
        full_name = EXCLUDED.full_name,
        role = 'owner',
        is_active = true,
        updated_at = now();

    -- Return provisioning result
    RETURN jsonb_build_object(
        'success', true,
        'company_id', v_company_id,
        'company_code', UPPER(TRIM(p_company_code)),
        'profile_id', v_user_id,
        'role', 'owner'
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.provision_new_tenant(TEXT, TEXT, VARCHAR, TEXT, UUID) TO authenticated, service_role;

-- ----------------------------------------------------------------------------
-- 8. Statutory Export Views
-- ----------------------------------------------------------------------------

-- 8.1 SIZA Social Compliance Training Register View
CREATE OR REPLACE VIEW public.v_siza_training_compliance AS
SELECT 
    tr.id AS record_id,
    c.id AS company_id,
    c.name AS company_name,
    s.name AS site_name,
    w.id AS worker_id,
    w.first_name || ' ' || w.last_name AS worker_full_name,
    w.employee_number,
    w.id_passport_number,
    w.gender,
    w.role_title AS worker_role,
    v.id AS module_slug,
    v.title AS module_title,
    v.category AS module_category,
    tr.completed_at,
    tr.training_type,
    tr.status AS verification_status,
    tr.supervisor_snapshot->>'full_name' AS supervisor_name,
    tr.signature_url AS proof_of_training_url
FROM public.training_records tr
JOIN public.companies c ON c.id = tr.company_id
LEFT JOIN public.sites s ON s.id = tr.site_id
JOIN public.workers w ON w.id = tr.worker_id
JOIN public.videos v ON v.id = tr.video_id;

-- 8.2 GLOBALG.A.P. IFA v6 Health & Safety Risk Register View
CREATE OR REPLACE VIEW public.v_globalgap_qms_evidence AS
SELECT
    ra.id AS assessment_id,
    c.id AS company_id,
    c.name AS company_name,
    s.name AS site_name,
    z.name AS zone_or_block_name,
    ra.ra_type,
    ra.title AS assessment_title,
    ra.category AS statutory_category,
    ra.work_area,
    ra.assessment_date,
    ra.review_due_date,
    CASE 
        WHEN ra.review_due_date < CURRENT_DATE THEN 'EXPIRED'
        WHEN ra.review_due_date <= (CURRENT_DATE + INTERVAL '30 days') THEN 'EXPIRING_SOON'
        ELSE 'COMPLIANT'
    END AS compliance_status,
    ra.assessor_name,
    ra.hazards_register,
    ra.required_ppe
FROM public.risk_assessments ra
JOIN public.companies c ON c.id = ra.company_id
JOIN public.sites s ON s.id = ra.site_id
LEFT JOIN public.zones z ON z.id = ra.zone_id;

-- ----------------------------------------------------------------------------
-- 9. Row Level Security (RLS) - Zero-Recursion Standard
-- ----------------------------------------------------------------------------

-- Enable RLS across all operational tables
ALTER TABLE public.corporate_partners ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partner_grower_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partner_portal_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sops ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requisitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requisition_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_inbox ENABLE ROW LEVEL SECURITY;

-- 9.1 Corporate Partners & Tokens
DROP POLICY IF EXISTS "corporate_partners_public_read" ON public.corporate_partners;
CREATE POLICY "corporate_partners_public_read" ON public.corporate_partners
    FOR SELECT TO authenticated USING (is_active = true);

DROP POLICY IF EXISTS "partner_grower_registry_read" ON public.partner_grower_registry;
CREATE POLICY "partner_grower_registry_read" ON public.partner_grower_registry
    FOR SELECT TO authenticated
    USING (
        claimed_by_company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid
        OR claimed_by_company_id IS NULL
    );

-- 9.2 Companies
DROP POLICY IF EXISTS "companies_tenant_isolation" ON public.companies;
CREATE POLICY "companies_tenant_isolation" ON public.companies
    FOR SELECT TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "companies_admin_update" ON public.companies;
CREATE POLICY "companies_admin_update" ON public.companies
    FOR UPDATE TO authenticated
    USING (
        id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid 
        AND (auth.jwt() -> 'app_metadata' ->> 'role') IN ('owner', 'admin')
    );

-- 9.3 Profiles
DROP POLICY IF EXISTS "profiles_tenant_read" ON public.profiles;
CREATE POLICY "profiles_tenant_read" ON public.profiles
    FOR SELECT TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "profiles_self_or_admin_write" ON public.profiles;
CREATE POLICY "profiles_self_or_admin_write" ON public.profiles
    FOR UPDATE TO authenticated
    USING (
        company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid
        AND (id = auth.uid() OR (auth.jwt() -> 'app_metadata' ->> 'role') IN ('owner', 'admin'))
    );

-- 9.4 Sites & Zones
DROP POLICY IF EXISTS "sites_tenant_all" ON public.sites;
CREATE POLICY "sites_tenant_all" ON public.sites
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "zones_tenant_all" ON public.zones;
CREATE POLICY "zones_tenant_all" ON public.zones
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- 9.5 Workers
DROP POLICY IF EXISTS "workers_tenant_all" ON public.workers;
CREATE POLICY "workers_tenant_all" ON public.workers
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- 9.6 Videos & SOPs
DROP POLICY IF EXISTS "videos_read_global_and_tenant" ON public.videos;
CREATE POLICY "videos_read_global_and_tenant" ON public.videos
    FOR SELECT TO authenticated
    USING (company_id IS NULL OR company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "sops_read_global_and_tenant" ON public.sops;
CREATE POLICY "sops_read_global_and_tenant" ON public.sops
    FOR SELECT TO authenticated
    USING (company_id IS NULL OR company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- 9.7 Training Records & Risk Assessments
DROP POLICY IF EXISTS "training_records_tenant_isolation" ON public.training_records;
CREATE POLICY "training_records_tenant_isolation" ON public.training_records
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "risk_assessments_tenant_isolation" ON public.risk_assessments;
CREATE POLICY "risk_assessments_tenant_isolation" ON public.risk_assessments
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- 9.8 Requisitions & Items
DROP POLICY IF EXISTS "requisitions_tenant_isolation" ON public.requisitions;
CREATE POLICY "requisitions_tenant_isolation" ON public.requisitions
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "requisition_items_tenant_isolation" ON public.requisition_items;
CREATE POLICY "requisition_items_tenant_isolation" ON public.requisition_items
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- 9.9 Sync Inbox
DROP POLICY IF EXISTS "sync_inbox_tenant_isolation" ON public.sync_inbox;
CREATE POLICY "sync_inbox_tenant_isolation" ON public.sync_inbox
    FOR ALL TO authenticated
    USING (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid)
    WITH CHECK (company_id = (auth.jwt() -> 'app_metadata' ->> 'company_id')::uuid);

-- ----------------------------------------------------------------------------
-- 10. Storage Topology & Policies
-- ----------------------------------------------------------------------------

-- Insert Buckets
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES 
    ('vault-media', 'vault-media', false, 52428800, NULL),     -- 50MB limit
    ('conduit-docs', 'conduit-docs', false, 52428800, NULL),   -- 50MB limit
    ('public-assets', 'public-assets', true, 10485760, NULL)   -- 10MB limit
ON CONFLICT (id) DO UPDATE SET
    public = EXCLUDED.public;

-- Storage RLS Policies
DROP POLICY IF EXISTS "vault_media_tenant_isolation" ON storage.objects;
CREATE POLICY "vault_media_tenant_isolation"
ON storage.objects FOR ALL TO authenticated
USING (
    bucket_id = 'vault-media'
    AND (storage.foldername(name))[1] = (auth.jwt() -> 'app_metadata' ->> 'company_id')
)
WITH CHECK (
    bucket_id = 'vault-media'
    AND (storage.foldername(name))[1] = (auth.jwt() -> 'app_metadata' ->> 'company_id')
);

DROP POLICY IF EXISTS "conduit_docs_tenant_isolation" ON storage.objects;
CREATE POLICY "conduit_docs_tenant_isolation"
ON storage.objects FOR ALL TO authenticated
USING (
    bucket_id = 'conduit-docs'
    AND (storage.foldername(name))[1] = (auth.jwt() -> 'app_metadata' ->> 'company_id')
)
WITH CHECK (
    bucket_id = 'conduit-docs'
    AND (storage.foldername(name))[1] = (auth.jwt() -> 'app_metadata' ->> 'company_id')
);

DROP POLICY IF EXISTS "public_assets_view" ON storage.objects;
CREATE POLICY "public_assets_view"
ON storage.objects FOR SELECT TO public
USING (bucket_id = 'public-assets');

DROP POLICY IF EXISTS "public_assets_tenant_write" ON storage.objects;
CREATE POLICY "public_assets_tenant_write"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = 'public-assets'
    AND (storage.foldername(name))[2] = (auth.jwt() -> 'app_metadata' ->> 'company_id')
);
