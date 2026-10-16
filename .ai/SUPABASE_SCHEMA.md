# Live Supabase Schema Manifest
> **Last Synchronized:** 2026-10-16 19:59:45 UTC
> **Source:** Remote Supabase Instance via pg_dump (Direct Connection)
> **Single Source of Truth for Autonomous Agents:** @architect, @auditor, @closer

---

## 1. Relational Database Schema & Policies (DDL)

```sql
--
-- PostgreSQL database dump
--

\restrict BmbN6tY9gFINmRJdne56Q5SaUYUx23R1nxXXZPqWTaUU4d0sL7gwsS6KaYdP3eE

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: billing_tier; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.billing_tier AS ENUM (
    'bundle',
    'standalone_vault',
    'standalone_conduit',
    'standalone_spray',
    'standalone_packhouse',
    'enterprise'
);


--
-- Name: requisition_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.requisition_status AS ENUM (
    'LOGGED',
    'APPROVED',
    'PO_PLACED',
    'RECEIVED',
    'RECONCILED',
    'CANCELLED'
);


--
-- Name: sync_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sync_status AS ENUM (
    'PENDING',
    'PROCESSED',
    'CONFLICT',
    'REJECTED'
);


--
-- Name: urgency_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.urgency_level AS ENUM (
    'ROUTINE',
    'URGENT',
    'CRITICAL'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'owner',
    'admin',
    'farm_manager',
    'buyer',
    'supervisor',
    'agronomist',
    'auditor',
    'viewer'
);


--
-- Name: check_7day_duplicates(uuid, text[], uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_7day_duplicates(p_site_id uuid, p_search_tokens text[], p_exclude_requisition_id uuid DEFAULT NULL::uuid) RETURNS TABLE(suspect_requisition_id uuid, reference_code character varying, matched_item text, created_at timestamp with time zone, status public.requisition_status)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
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


--
-- Name: custom_access_token_hook(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.custom_access_token_hook(event jsonb) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public'
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


--
-- Name: fn_assign_po_number(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_assign_po_number() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status = 'PO_PLACED' AND (NEW.po_number IS NULL OR TRIM(NEW.po_number) = '') THEN
        NEW.po_number := 'PO-' || TO_CHAR(NOW(), 'YYMM') || '-' || LPAD(nextval('public.po_number_seq')::text, 4, '0');
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: fn_generate_requisition_ref(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_generate_requisition_ref() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.reference_code IS NULL OR TRIM(NEW.reference_code) = '' THEN
        NEW.reference_code := 'REQ-' || TO_CHAR(NOW(), 'YYMM') || '-' || LPAD(nextval('public.requisition_ref_seq')::text, 4, '0');
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: provision_new_tenant(text, text, character varying, text, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.provision_new_tenant(p_company_name text, p_slug text, p_company_code character varying, p_owner_full_name text, p_user_id uuid DEFAULT auth.uid()) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
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


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: companies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.companies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    company_code character varying(6) NOT NULL,
    billing_tier public.billing_tier DEFAULT 'bundle'::public.billing_tier NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    currency character varying(3) DEFAULT 'ZAR'::character varying NOT NULL,
    timezone text DEFAULT 'Africa/Johannesburg'::text NOT NULL,
    partner_id uuid,
    is_subsidized boolean DEFAULT false NOT NULL,
    billing_metadata jsonb DEFAULT '{"status": "active", "provider": "paystack", "plan_code": null, "billing_email": null, "customer_code": null, "billing_interval": "monthly", "next_payment_date": null, "subscription_code": null}'::jsonb NOT NULL,
    settings jsonb DEFAULT '{"default_language": "en", "duplicate_window_days": 7, "auto_approve_threshold_zar": 0.00, "require_supervisor_signature": true, "require_zone_for_requisitions": false}'::jsonb NOT NULL,
    vat_number text,
    postal_address text,
    phone text,
    contact_email text,
    company_stamp_url text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT ck_company_code_format CHECK (((company_code)::text ~ '^[A-Z0-9]{2,6}$'::text))
);


--
-- Name: corporate_partners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.corporate_partners (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    sponsored_crop_pack text NOT NULL,
    logo_url text,
    contact_email text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: partner_grower_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.partner_grower_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    partner_id uuid NOT NULL,
    grower_code text NOT NULL,
    company_name text NOT NULL,
    contact_email text,
    claimed_by_company_id uuid,
    claimed_at timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: partner_portal_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.partner_portal_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    partner_id uuid NOT NULL,
    token text DEFAULT (gen_random_uuid())::text NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '90 days'::interval) NOT NULL,
    revoked_at timestamp with time zone
);


--
-- Name: po_number_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.po_number_seq
    START WITH 5001
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id uuid NOT NULL,
    company_id uuid NOT NULL,
    email text NOT NULL,
    full_name text NOT NULL,
    role public.user_role DEFAULT 'viewer'::public.user_role NOT NULL,
    phone_number character varying(20),
    avatar_url text,
    authorized_site_ids uuid[],
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: requisition_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.requisition_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    requisition_id uuid NOT NULL,
    item_description text NOT NULL,
    normalized_tokens text,
    quantity numeric(10,2) DEFAULT 1.0 NOT NULL,
    unit_of_measure character varying(30) DEFAULT 'units'::character varying NOT NULL,
    part_number character varying(100),
    pastel_item_code character varying(50),
    unit_price_zar numeric(12,2),
    notes text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: requisition_ref_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.requisition_ref_seq
    START WITH 1001
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: requisitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.requisitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    reference_code character varying(32) NOT NULL,
    po_number character varying(32),
    site_id uuid NOT NULL,
    zone_id uuid,
    location_detail text,
    requester_id uuid NOT NULL,
    status public.requisition_status DEFAULT 'LOGGED'::public.requisition_status NOT NULL,
    urgency public.urgency_level DEFAULT 'ROUTINE'::public.urgency_level NOT NULL,
    raw_message_text text,
    audio_url text,
    media_urls text[] DEFAULT '{}'::text[] NOT NULL,
    whatsapp_message_id character varying(128),
    is_duplicate_suspect boolean DEFAULT false NOT NULL,
    duplicate_of_id uuid,
    assigned_buyer_id uuid,
    supplier_name text,
    total_estimated_zar numeric(12,2) DEFAULT 0.00,
    total_actual_zar numeric(12,2),
    notes text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: risk_assessments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_assessments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    site_id uuid NOT NULL,
    zone_id uuid,
    ra_type text NOT NULL,
    title text NOT NULL,
    category text NOT NULL,
    work_area text,
    equipment_identifier text,
    assessment_date date DEFAULT CURRENT_DATE NOT NULL,
    review_due_date date NOT NULL,
    status text DEFAULT 'Active'::text NOT NULL,
    assessor_id uuid,
    assessor_name text NOT NULL,
    assessor_signature text,
    hazards_register jsonb DEFAULT '[]'::jsonb NOT NULL,
    required_ppe jsonb DEFAULT '[]'::jsonb NOT NULL,
    pre_use_checks jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT risk_assessments_ra_type_check CHECK ((ra_type = ANY (ARRAY['baseline'::text, 'issue_based'::text, 'continuous'::text, 'pre_start'::text]))),
    CONSTRAINT risk_assessments_status_check CHECK ((status = ANY (ARRAY['Active'::text, 'Under Review'::text, 'Archived'::text])))
);


--
-- Name: sites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sites (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    name text NOT NULL,
    code character varying(20) NOT NULL,
    location_description text,
    gps_coordinates point,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: sops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sops (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid,
    video_id text,
    title text NOT NULL,
    description text,
    category text DEFAULT 'Agriculture'::text NOT NULL,
    sub_tag text DEFAULT 'General Safety'::text NOT NULL,
    doc_url text NOT NULL,
    version_number character varying(10) DEFAULT '1.0'::character varying NOT NULL,
    curriculum_slug text,
    partner_docs jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: sync_inbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_inbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    client_uuid uuid NOT NULL,
    command_type character varying(64) NOT NULL,
    entity_table character varying(64) NOT NULL,
    entity_id uuid,
    payload jsonb NOT NULL,
    device_id character varying(64),
    submitted_by_profile_id uuid,
    status public.sync_status DEFAULT 'PENDING'::public.sync_status NOT NULL,
    error_message text,
    processed_at timestamp with time zone,
    client_created_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: training_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.training_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    site_id uuid,
    worker_id uuid NOT NULL,
    video_id text NOT NULL,
    completed_at date DEFAULT CURRENT_DATE NOT NULL,
    status text DEFAULT 'Verified'::text NOT NULL,
    training_type text DEFAULT 'Individual'::text NOT NULL,
    batch_session_id uuid,
    supervisor_id uuid,
    worker_snapshot jsonb NOT NULL,
    supervisor_snapshot jsonb NOT NULL,
    signature_url text,
    supervisor_signature_data text,
    worker_signature_data text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT training_records_status_check CHECK ((status = ANY (ARRAY['Verified'::text, 'Archived'::text, 'Flagged'::text]))),
    CONSTRAINT training_records_training_type_check CHECK ((training_type = ANY (ARRAY['Individual'::text, 'Group_Batch'::text])))
);


--
-- Name: zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    site_id uuid NOT NULL,
    name text NOT NULL,
    code character varying(20),
    zone_type text DEFAULT 'orchard'::text NOT NULL,
    crop_variety text,
    hectares numeric(8,2),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT zones_zone_type_check CHECK ((zone_type = ANY (ARRAY['orchard'::text, 'workshop'::text, 'packhouse'::text, 'storage'::text, 'general'::text])))
);


--
-- Name: v_globalgap_qms_evidence; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_globalgap_qms_evidence AS
 SELECT ra.id AS assessment_id,
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
            WHEN (ra.review_due_date < CURRENT_DATE) THEN 'EXPIRED'::text
            WHEN (ra.review_due_date <= (CURRENT_DATE + '30 days'::interval)) THEN 'EXPIRING_SOON'::text
            ELSE 'COMPLIANT'::text
        END AS compliance_status,
    ra.assessor_name,
    ra.hazards_register,
    ra.required_ppe
   FROM (((public.risk_assessments ra
     JOIN public.companies c ON ((c.id = ra.company_id)))
     JOIN public.sites s ON ((s.id = ra.site_id)))
     LEFT JOIN public.zones z ON ((z.id = ra.zone_id)));


--
-- Name: videos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.videos (
    id text NOT NULL,
    company_id uuid,
    title text NOT NULL,
    category text DEFAULT 'Agriculture'::text NOT NULL,
    sub_tag text,
    language text DEFAULT 'English'::text NOT NULL,
    total_seconds integer NOT NULL,
    thumbnail_url text,
    description text,
    objectives jsonb DEFAULT '[]'::jsonb NOT NULL,
    questions jsonb DEFAULT '[]'::jsonb NOT NULL,
    curriculum_slug text,
    streams jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: workers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    company_id uuid NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    employee_number character varying(30),
    id_passport_number text,
    gender text,
    phone_number character varying(20),
    qr_token text DEFAULT ('WKT-'::text || (gen_random_uuid())::text) NOT NULL,
    role_title text NOT NULL,
    default_site_id uuid,
    team_or_orchard text,
    preferred_language character varying(10) DEFAULT 'en'::character varying NOT NULL,
    consent_flags jsonb DEFAULT '{"hazchem_certified": false, "popia_data_processing": true, "medical_fitness_on_file": false}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT workers_gender_check CHECK (((gender IS NULL) OR (gender = ANY (ARRAY['Male'::text, 'Female'::text, 'Other'::text]))))
);


--
-- Name: v_siza_training_compliance; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_siza_training_compliance AS
 SELECT tr.id AS record_id,
    c.id AS company_id,
    c.name AS company_name,
    s.name AS site_name,
    w.id AS worker_id,
    ((w.first_name || ' '::text) || w.last_name) AS worker_full_name,
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
    (tr.supervisor_snapshot ->> 'full_name'::text) AS supervisor_name,
    tr.signature_url AS proof_of_training_url
   FROM ((((public.training_records tr
     JOIN public.companies c ON ((c.id = tr.company_id)))
     LEFT JOIN public.sites s ON ((s.id = tr.site_id)))
     JOIN public.workers w ON ((w.id = tr.worker_id)))
     JOIN public.videos v ON ((v.id = tr.video_id)));


--
-- Name: companies companies_company_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_company_code_key UNIQUE (company_code);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: companies companies_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_slug_key UNIQUE (slug);


--
-- Name: corporate_partners corporate_partners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_partners
    ADD CONSTRAINT corporate_partners_pkey PRIMARY KEY (id);


--
-- Name: corporate_partners corporate_partners_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_partners
    ADD CONSTRAINT corporate_partners_slug_key UNIQUE (slug);


--
-- Name: partner_grower_registry partner_grower_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_grower_registry
    ADD CONSTRAINT partner_grower_registry_pkey PRIMARY KEY (id);


--
-- Name: partner_portal_tokens partner_portal_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_portal_tokens
    ADD CONSTRAINT partner_portal_tokens_pkey PRIMARY KEY (id);


--
-- Name: partner_portal_tokens partner_portal_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_portal_tokens
    ADD CONSTRAINT partner_portal_tokens_token_key UNIQUE (token);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: requisition_items requisition_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisition_items
    ADD CONSTRAINT requisition_items_pkey PRIMARY KEY (id);


--
-- Name: requisitions requisitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_pkey PRIMARY KEY (id);


--
-- Name: requisitions requisitions_po_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_po_number_key UNIQUE (po_number);


--
-- Name: requisitions requisitions_reference_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_reference_code_key UNIQUE (reference_code);


--
-- Name: risk_assessments risk_assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_assessments
    ADD CONSTRAINT risk_assessments_pkey PRIMARY KEY (id);


--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);


--
-- Name: sops sops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sops
    ADD CONSTRAINT sops_pkey PRIMARY KEY (id);


--
-- Name: sync_inbox sync_inbox_client_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_inbox
    ADD CONSTRAINT sync_inbox_client_uuid_key UNIQUE (client_uuid);


--
-- Name: sync_inbox sync_inbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_inbox
    ADD CONSTRAINT sync_inbox_pkey PRIMARY KEY (id);


--
-- Name: training_records training_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_pkey PRIMARY KEY (id);


--
-- Name: partner_grower_registry uq_partner_grower_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_grower_registry
    ADD CONSTRAINT uq_partner_grower_code UNIQUE (partner_id, grower_code);


--
-- Name: sites uq_site_company_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT uq_site_company_code UNIQUE (company_id, code);


--
-- Name: zones uq_zone_site_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT uq_zone_site_code UNIQUE (site_id, code);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: workers workers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workers
    ADD CONSTRAINT workers_pkey PRIMARY KEY (id);


--
-- Name: workers workers_qr_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workers
    ADD CONSTRAINT workers_qr_token_key UNIQUE (qr_token);


--
-- Name: zones zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pkey PRIMARY KEY (id);


--
-- Name: idx_companies_partner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_companies_partner_id ON public.companies USING btree (partner_id) WHERE (partner_id IS NOT NULL);


--
-- Name: idx_companies_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_companies_slug ON public.companies USING btree (slug);


--
-- Name: idx_profiles_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profiles_company ON public.profiles USING btree (company_id);


--
-- Name: idx_profiles_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profiles_role ON public.profiles USING btree (company_id, role);


--
-- Name: idx_requisition_items_req_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_requisition_items_req_id ON public.requisition_items USING btree (requisition_id);


--
-- Name: idx_requisitions_company_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_requisitions_company_status ON public.requisitions USING btree (company_id, status);


--
-- Name: idx_requisitions_requester; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_requisitions_requester ON public.requisitions USING btree (requester_id);


--
-- Name: idx_requisitions_site; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_requisitions_site ON public.requisitions USING btree (site_id);


--
-- Name: idx_risk_assessments_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_risk_assessments_tenant ON public.risk_assessments USING btree (company_id, site_id);


--
-- Name: idx_sites_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sites_company ON public.sites USING btree (company_id);


--
-- Name: idx_sync_inbox_client_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sync_inbox_client_uuid ON public.sync_inbox USING btree (client_uuid);


--
-- Name: idx_sync_inbox_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sync_inbox_pending ON public.sync_inbox USING btree (company_id, status) WHERE (status = 'PENDING'::public.sync_status);


--
-- Name: idx_training_records_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_training_records_date ON public.training_records USING btree (company_id, completed_at DESC);


--
-- Name: idx_training_records_video; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_training_records_video ON public.training_records USING btree (company_id, video_id);


--
-- Name: idx_training_records_worker; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_training_records_worker ON public.training_records USING btree (company_id, worker_id);


--
-- Name: idx_workers_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workers_company ON public.workers USING btree (company_id);


--
-- Name: idx_workers_employee_num; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workers_employee_num ON public.workers USING btree (company_id, employee_number) WHERE (employee_number IS NOT NULL);


--
-- Name: idx_workers_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workers_phone ON public.workers USING btree (company_id, phone_number) WHERE (phone_number IS NOT NULL);


--
-- Name: idx_workers_qr_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workers_qr_token ON public.workers USING btree (qr_token);


--
-- Name: idx_zones_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zones_company ON public.zones USING btree (company_id);


--
-- Name: idx_zones_site; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zones_site ON public.zones USING btree (site_id);


--
-- Name: requisitions trg_assign_po_number; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_assign_po_number BEFORE UPDATE OF status ON public.requisitions FOR EACH ROW EXECUTE FUNCTION public.fn_assign_po_number();


--
-- Name: requisitions trg_generate_requisition_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_generate_requisition_ref BEFORE INSERT ON public.requisitions FOR EACH ROW EXECUTE FUNCTION public.fn_generate_requisition_ref();


--
-- Name: companies companies_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.corporate_partners(id) ON DELETE SET NULL;


--
-- Name: partner_grower_registry partner_grower_registry_claimed_by_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_grower_registry
    ADD CONSTRAINT partner_grower_registry_claimed_by_company_id_fkey FOREIGN KEY (claimed_by_company_id) REFERENCES public.companies(id) ON DELETE SET NULL;


--
-- Name: partner_grower_registry partner_grower_registry_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_grower_registry
    ADD CONSTRAINT partner_grower_registry_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.corporate_partners(id) ON DELETE CASCADE;


--
-- Name: partner_portal_tokens partner_portal_tokens_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_portal_tokens
    ADD CONSTRAINT partner_portal_tokens_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.corporate_partners(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE RESTRICT;


--
-- Name: profiles profiles_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: requisition_items requisition_items_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisition_items
    ADD CONSTRAINT requisition_items_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: requisition_items requisition_items_requisition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisition_items
    ADD CONSTRAINT requisition_items_requisition_id_fkey FOREIGN KEY (requisition_id) REFERENCES public.requisitions(id) ON DELETE CASCADE;


--
-- Name: requisitions requisitions_assigned_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_assigned_buyer_id_fkey FOREIGN KEY (assigned_buyer_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: requisitions requisitions_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: requisitions requisitions_duplicate_of_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_duplicate_of_id_fkey FOREIGN KEY (duplicate_of_id) REFERENCES public.requisitions(id) ON DELETE SET NULL;


--
-- Name: requisitions requisitions_requester_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES public.workers(id) ON DELETE RESTRICT;


--
-- Name: requisitions requisitions_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE RESTRICT;


--
-- Name: requisitions requisitions_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requisitions
    ADD CONSTRAINT requisitions_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: risk_assessments risk_assessments_assessor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_assessments
    ADD CONSTRAINT risk_assessments_assessor_id_fkey FOREIGN KEY (assessor_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: risk_assessments risk_assessments_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_assessments
    ADD CONSTRAINT risk_assessments_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: risk_assessments risk_assessments_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_assessments
    ADD CONSTRAINT risk_assessments_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE;


--
-- Name: risk_assessments risk_assessments_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_assessments
    ADD CONSTRAINT risk_assessments_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: sites sites_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: sops sops_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sops
    ADD CONSTRAINT sops_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: sops sops_video_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sops
    ADD CONSTRAINT sops_video_id_fkey FOREIGN KEY (video_id) REFERENCES public.videos(id) ON DELETE SET NULL;


--
-- Name: sync_inbox sync_inbox_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_inbox
    ADD CONSTRAINT sync_inbox_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: sync_inbox sync_inbox_submitted_by_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_inbox
    ADD CONSTRAINT sync_inbox_submitted_by_profile_id_fkey FOREIGN KEY (submitted_by_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: training_records training_records_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: training_records training_records_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE SET NULL;


--
-- Name: training_records training_records_supervisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_supervisor_id_fkey FOREIGN KEY (supervisor_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: training_records training_records_video_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_video_id_fkey FOREIGN KEY (video_id) REFERENCES public.videos(id) ON DELETE RESTRICT;


--
-- Name: training_records training_records_worker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_worker_id_fkey FOREIGN KEY (worker_id) REFERENCES public.workers(id) ON DELETE RESTRICT;


--
-- Name: videos videos_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: workers workers_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workers
    ADD CONSTRAINT workers_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: workers workers_default_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workers
    ADD CONSTRAINT workers_default_site_id_fkey FOREIGN KEY (default_site_id) REFERENCES public.sites(id) ON DELETE SET NULL;


--
-- Name: zones zones_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: zones zones_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE;


--
-- Name: companies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

--
-- Name: companies companies_admin_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY companies_admin_update ON public.companies FOR UPDATE TO authenticated USING (((id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid) AND (((auth.jwt() -> 'app_metadata'::text) ->> 'role'::text) = ANY (ARRAY['owner'::text, 'admin'::text]))));


--
-- Name: companies companies_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY companies_tenant_isolation ON public.companies FOR SELECT TO authenticated USING ((id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: corporate_partners; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.corporate_partners ENABLE ROW LEVEL SECURITY;

--
-- Name: corporate_partners corporate_partners_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY corporate_partners_public_read ON public.corporate_partners FOR SELECT TO authenticated USING ((is_active = true));


--
-- Name: partner_grower_registry; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.partner_grower_registry ENABLE ROW LEVEL SECURITY;

--
-- Name: partner_grower_registry partner_grower_registry_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY partner_grower_registry_read ON public.partner_grower_registry FOR SELECT TO authenticated USING (((claimed_by_company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid) OR (claimed_by_company_id IS NULL)));


--
-- Name: partner_portal_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.partner_portal_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles profiles_self_or_admin_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY profiles_self_or_admin_write ON public.profiles FOR UPDATE TO authenticated USING (((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid) AND ((id = auth.uid()) OR (((auth.jwt() -> 'app_metadata'::text) ->> 'role'::text) = ANY (ARRAY['owner'::text, 'admin'::text])))));


--
-- Name: profiles profiles_tenant_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY profiles_tenant_read ON public.profiles FOR SELECT TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: requisition_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.requisition_items ENABLE ROW LEVEL SECURITY;

--
-- Name: requisition_items requisition_items_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY requisition_items_tenant_isolation ON public.requisition_items TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: requisitions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.requisitions ENABLE ROW LEVEL SECURITY;

--
-- Name: requisitions requisitions_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY requisitions_tenant_isolation ON public.requisitions TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: risk_assessments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.risk_assessments ENABLE ROW LEVEL SECURITY;

--
-- Name: risk_assessments risk_assessments_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY risk_assessments_tenant_isolation ON public.risk_assessments TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: sites; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sites ENABLE ROW LEVEL SECURITY;

--
-- Name: sites sites_tenant_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sites_tenant_all ON public.sites TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: sops; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sops ENABLE ROW LEVEL SECURITY;

--
-- Name: sops sops_read_global_and_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sops_read_global_and_tenant ON public.sops FOR SELECT TO authenticated USING (((company_id IS NULL) OR (company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)));


--
-- Name: sync_inbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sync_inbox ENABLE ROW LEVEL SECURITY;

--
-- Name: sync_inbox sync_inbox_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sync_inbox_tenant_isolation ON public.sync_inbox TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: training_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.training_records ENABLE ROW LEVEL SECURITY;

--
-- Name: training_records training_records_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY training_records_tenant_isolation ON public.training_records TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: videos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;

--
-- Name: videos videos_read_global_and_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY videos_read_global_and_tenant ON public.videos FOR SELECT TO authenticated USING (((company_id IS NULL) OR (company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)));


--
-- Name: workers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workers ENABLE ROW LEVEL SECURITY;

--
-- Name: workers workers_tenant_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY workers_tenant_all ON public.workers TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- Name: zones; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.zones ENABLE ROW LEVEL SECURITY;

--
-- Name: zones zones_tenant_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY zones_tenant_all ON public.zones TO authenticated USING ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid)) WITH CHECK ((company_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'company_id'::text))::uuid));


--
-- PostgreSQL database dump complete
--

\unrestrict BmbN6tY9gFINmRJdne56Q5SaUYUx23R1nxXXZPqWTaUU4d0sL7gwsS6KaYdP3eE


```
