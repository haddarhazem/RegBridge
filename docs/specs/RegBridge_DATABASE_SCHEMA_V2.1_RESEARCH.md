# RegBridge — Schéma PostgreSQL métier cible V2.1 — Research

**Version :** 2.1  
**Date :** 11 août 2026  
**Statut :** cible de conception à implémenter par migrations Alembic

## 1. Principes

- PostgreSQL 15, SQLAlchemy 2.x asynchrone, Alembic et pgvector sont conservés.
- Les fichiers binaires restent dans un stockage objet chiffré ; PostgreSQL conserve les métadonnées, versions, droits et résultats.
- Qdrant reste le magasin vectoriel du corpus réglementaire externe ; pgvector sert aux correspondances sémantiques métier.
- L’authentification est déléguée à un fournisseur OIDC/OAuth2 ; aucun mot de passe en clair ou hash de mot de passe n’est requis dans cette couche métier.
- Les conversations sont persistées uniquement pour les utilisateurs authentifiés.
- Les sorties IA sont structurées, versionnées, sourcées et vérifiables.
- Le document scientifique intégral reste dans le stockage objet et ne devient jamais un corpus public interrogeable par défaut.
- Le matching recherche-startup utilise uniquement des métadonnées et snapshots approuvés par le chercheur.
- Tous les horodatages techniques sont en `TIMESTAMPTZ`; toutes les clés primaires sont des UUID.

## 2. Principales corrections par rapport au schéma initial et à la cible V2.0

1. `startup_member` n’est plus un rôle global : la relation équipe/projet est portée par `project_members`.
2. Ajout de la gestion des fichiers, versions et traitements : `documents`, `document_versions`, `document_processing_jobs`.
3. Ajout des conversations authentifiées et de la traçabilité IA.
4. Normalisation du score de maturité conformité par référentiel et contrôle.
5. Suppression du domaine actif Patent Guidance, non aligné avec la proposition de valeur centrale de RegBridge.
6. Refonte du domaine Research autour de trois niveaux distincts : document intégral contrôlé, extraction interne sourcée et publication approuvée destinée à la découverte.
7. Suppression de `possible_applications` comme champ libre généré : seules les applications explicitement mentionnées par les auteurs peuvent être extraites.
8. Le matching recherche-startup compare des besoins confirmés à un snapshot de publication approuvé ; il ne génère aucune nouvelle application ou opportunité.
9. Le matching investisseur V1 reste un rapport LLM préliminaire ; les scores avancés demeurent optionnels.
10. Séparation explicite des données publiques, partagées et privées.

## 3. Extensions requises

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
```

## 4. Domaine — Identity & Access

### `users` — Modifiée

Compte applicatif et préférences générales. Les secrets d'authentification restent chez le fournisseur d'identité.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `email` | `VARCHAR(320)` | UNIQUE, NOT NULL |
| `first_name` | `VARCHAR(120)` | NULL |
| `last_name` | `VARCHAR(120)` | NULL |
| `language` | `VARCHAR(10)` | NOT NULL, défaut fr |
| `country_code` | `VARCHAR(2)` | NOT NULL, défaut FR |
| `status` | `VARCHAR(30)` | NOT NULL, défaut active |
| `last_login_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- status IN (active, suspended, deleted)

**Index :**
- UNIQUE lower(email)

### `user_identities` — Nouvelle

Association entre un utilisateur métier et une identité OIDC/OAuth2 externe.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NOT NULL, CASCADE |
| `provider` | `VARCHAR(80)` | NOT NULL |
| `provider_subject` | `VARCHAR(255)` | NOT NULL |
| `email_at_provider` | `VARCHAR(320)` | NULL |
| `email_verified_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(provider, provider_subject)

**Index :**
- INDEX user_id

### `user_consents` — Nouvelle

Preuve versionnée des consentements et acceptations nécessaires.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NOT NULL, CASCADE |
| `consent_type` | `VARCHAR(50)` | NOT NULL |
| `document_version` | `VARCHAR(40)` | NOT NULL |
| `granted` | `BOOLEAN` | NOT NULL |
| `recorded_at` | `TIMESTAMPTZ` | NOT NULL |
| `metadata` | `JSONB` | NOT NULL, défaut {} |

**Contraintes :**
- UNIQUE(user_id, consent_type, document_version)

### `roles` — Modifiée

Référentiel des rôles globaux. L'appartenance à une startup est gérée par project_members.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `code` | `VARCHAR(50)` | UNIQUE, NOT NULL |
| `description` | `TEXT` | NULL |

**Notes de conception :**
- Seed cible : entrepreneur, investor, researcher, research_center, admin.
- Le visiteur anonyme n'est pas persisté comme rôle.

### `user_roles` — Conservée

Association plusieurs-à-plusieurs entre utilisateurs et rôles globaux.

| Colonne | Type | Règles |
|---|---|---|
| `user_id` | `UUID` | PK, FK users.id, CASCADE |
| `role_id` | `UUID` | PK, FK roles.id, CASCADE |
| `assigned_at` | `TIMESTAMPTZ` | NOT NULL |

## 5. Domaine — Projects

### `projects` — Modifiée

Une idée, une startup en création ou une startup existante.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `owner_user_id` | `UUID` | FK users.id, NOT NULL |
| `project_type` | `VARCHAR(40)` | NOT NULL |
| `display_name` | `VARCHAR(255)` | NULL |
| `raw_description` | `TEXT` | NOT NULL |
| `user_goal` | `TEXT` | NULL |
| `current_progress` | `VARCHAR(80)` | NULL |
| `country_code` | `VARCHAR(2)` | NOT NULL, défaut FR |
| `target_market` | `VARCHAR(120)` | NOT NULL, défaut France |
| `language` | `VARCHAR(10)` | NOT NULL, défaut fr |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut private |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- project_type IN (idea, startup_in_creation, existing_startup)
- visibility IN (private, authenticated, public)

**Index :**
- INDEX owner_user_id
- INDEX project_type

### `project_members` — Nouvelle

Membres et droits d'une équipe sur un projet ou une startup.

| Colonne | Type | Règles |
|---|---|---|
| `project_id` | `UUID` | PK, FK projects.id, CASCADE |
| `user_id` | `UUID` | PK, FK users.id, CASCADE |
| `member_role` | `VARCHAR(30)` | NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut active |
| `invited_by_user_id` | `UUID` | FK users.id, NULL |
| `joined_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- member_role IN (owner, founder, admin, member, viewer)
- status IN (invited, active, revoked)

**Index :**
- INDEX user_id
- INDEX project_id, status

**Notes de conception :**
- Le propriétaire doit aussi avoir une ligne project_members avec member_role=owner.

### `project_access_grants` — Nouvelle

Partage explicite de données privées ou contrôlées avec un utilisateur ou un investisseur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `grantee_user_id` | `UUID` | FK users.id, NULL |
| `grantee_investor_profile_id` | `UUID` | FK investor_profiles.id, NULL |
| `scope` | `JSONB` | NOT NULL, défaut [] |
| `granted_by_user_id` | `UUID` | FK users.id, NOT NULL |
| `expires_at` | `TIMESTAMPTZ` | NULL |
| `revoked_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- Exactement un grantee doit être renseigné

**Index :**
- INDEX project_id
- INDEX grantee_user_id

### `project_public_profiles` — Nouvelle

Projection contrôlée des informations visibles publiquement ou par les utilisateurs authentifiés.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, UNIQUE, NOT NULL, CASCADE |
| `public_name` | `VARCHAR(255)` | NULL |
| `public_summary` | `TEXT` | NULL |
| `sector` | `VARCHAR(120)` | NULL |
| `technologies` | `JSONB` | NOT NULL, défaut [] |
| `website_url` | `TEXT` | NULL |
| `logo_document_id` | `UUID` | FK documents.id, NULL |
| `funding_visibility` | `VARCHAR(30)` | NOT NULL, défaut private |
| `compliance_visibility` | `VARCHAR(30)` | NOT NULL, défaut private |
| `published_at` | `TIMESTAMPTZ` | NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Notes de conception :**
- Les contrats, conversations et preuves détaillées de conformité ne sont jamais exposés par cette table.

### `project_profiles` — Modifiée

Profil structuré factuel généré puis confirmé à partir de la description du projet.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, UNIQUE, NOT NULL, CASCADE |
| `problem_statement` | `TEXT` | NULL |
| `solution_summary` | `TEXT` | NULL |
| `value_proposition` | `TEXT` | NULL |
| `sector` | `VARCHAR(120)` | NULL |
| `subsectors` | `JSONB` | NOT NULL, défaut [] |
| `customer_segments` | `JSONB` | NOT NULL, défaut [] |
| `target_users` | `JSONB` | NOT NULL, défaut [] |
| `keywords` | `JSONB` | NOT NULL, défaut [] |
| `technologies` | `JSONB` | NOT NULL, défaut [] |
| `inferred_maturity` | `VARCHAR(80)` | NULL |
| `profile_summary` | `TEXT` | NULL |
| `profile_embedding` | `VECTOR(n)` | NULL |
| `profile_version` | `INTEGER` | NOT NULL, défaut 1 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Index :**
- HNSW profile_embedding vector_cosine_ops

**Notes de conception :**
- Les champs suggested_business_model et suggested_revenue_model sont retirés du profil afin de respecter le périmètre : orientation réglementaire, pas coaching business automatique.

### `project_field_values` — Conservée

Provenance, confiance et validation humaine de chaque champ structuré.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `field_name` | `VARCHAR(150)` | NOT NULL |
| `value` | `JSONB` | NOT NULL |
| `source_type` | `VARCHAR(40)` | NOT NULL |
| `validation_status` | `VARCHAR(40)` | NOT NULL |
| `confidence` | `NUMERIC(5,4)` | NULL |
| `generated_by_agent` | `VARCHAR(80)` | NULL |
| `source_reference` | `JSONB` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, field_name)
- source_type IN (user_provided, agent_generated, agent_inferred, imported, verified_source)
- validation_status IN (pending_confirmation, user_confirmed, user_modified, rejected, verified)

### `project_legal_profiles` — Conservée

Informations juridiques fournies ou vérifiées. Les identifiants officiels ne sont jamais inventés par un agent.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, UNIQUE, NOT NULL, CASCADE |
| `is_registered` | `BOOLEAN` | NOT NULL, défaut false |
| `legal_name` | `VARCHAR(255)` | NULL |
| `legal_form` | `VARCHAR(120)` | NULL |
| `registration_number` | `VARCHAR(120)` | NULL |
| `siren` | `VARCHAR(9)` | NULL |
| `siret` | `VARCHAR(14)` | NULL |
| `vat_number` | `VARCHAR(40)` | NULL |
| `naf_code` | `VARCHAR(10)` | NULL |
| `registration_date` | `DATE` | NULL |
| `registered_address` | `JSONB` | NULL |
| `legal_representative` | `JSONB` | NULL |
| `verification_status` | `VARCHAR(30)` | NOT NULL, défaut unverified |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Index :**
- INDEX siren
- INDEX siret

### `project_business_profiles` — Modifiée

Données business factuelles nécessaires au matching et au pitch deck. Une donnée inconnue reste NULL.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, UNIQUE, NOT NULL, CASCADE |
| `business_model` | `TEXT` | NULL |
| `revenue_model` | `TEXT` | NULL |
| `customer_type` | `VARCHAR(80)` | NULL |
| `team_size` | `INTEGER` | NULL |
| `employee_count` | `INTEGER` | NULL |
| `has_prototype` | `BOOLEAN` | NULL |
| `has_users` | `BOOLEAN` | NULL |
| `has_customers` | `BOOLEAN` | NULL |
| `customer_count` | `INTEGER` | NULL |
| `has_revenue` | `BOOLEAN` | NULL |
| `annual_revenue` | `NUMERIC(18,2)` | NULL |
| `funding_needed` | `NUMERIC(18,2)` | NULL |
| `funding_currency` | `VARCHAR(3)` | NULL, défaut EUR |
| `funding_instrument` | `VARCHAR(80)` | NULL |
| `stage` | `VARCHAR(80)` | NULL |
| `traction_metrics` | `JSONB` | NOT NULL, défaut {} |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Notes de conception :**
- Le Pitch Deck Agent ne peut utiliser comme faits que des valeurs confirmées ou explicitement marquées comme hypothèses.

## 6. Domaine — Documents

### `documents` — Nouvelle

Métadonnées des fichiers importés ou générés. Le binaire reste dans un object storage chiffré.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `owner_user_id` | `UUID` | FK users.id, NOT NULL |
| `project_id` | `UUID` | FK projects.id, NULL, CASCADE |
| `title` | `VARCHAR(255)` | NOT NULL |
| `document_type` | `VARCHAR(80)` | NOT NULL |
| `classification` | `VARCHAR(40)` | NOT NULL, défaut confidential |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut private |
| `processing_status` | `VARCHAR(30)` | NOT NULL, défaut uploaded |
| `current_version_id` | `UUID` | FK document_versions.id, NULL, DEFERRABLE |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |
| `deleted_at` | `TIMESTAMPTZ` | NULL |

**Contraintes :**
- classification IN (public, internal, confidential, highly_confidential)
- visibility IN (private, project_members, shared, public)
- processing_status IN (uploaded, queued, processing, ready, failed, quarantined)

**Index :**
- INDEX owner_user_id
- INDEX project_id
- INDEX document_type

### `document_versions` — Nouvelle

Version immuable d'un fichier avec intégrité, stockage et extraction.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `document_id` | `UUID` | FK documents.id, NOT NULL, CASCADE |
| `version_number` | `INTEGER` | NOT NULL |
| `original_filename` | `VARCHAR(500)` | NOT NULL |
| `storage_key` | `TEXT` | UNIQUE, NOT NULL |
| `mime_type` | `VARCHAR(150)` | NOT NULL |
| `size_bytes` | `BIGINT` | NOT NULL |
| `sha256` | `CHAR(64)` | NOT NULL |
| `malware_scan_status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `extracted_text_location` | `TEXT` | NULL |
| `extraction_metadata` | `JSONB` | NOT NULL, défaut {} |
| `uploaded_by_user_id` | `UUID` | FK users.id, NOT NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(document_id, version_number)

**Index :**
- INDEX sha256

### `document_processing_jobs` — Nouvelle

Suivi idempotent des traitements asynchrones d'un document.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `document_version_id` | `UUID` | FK document_versions.id, NOT NULL, CASCADE |
| `job_type` | `VARCHAR(50)` | NOT NULL |
| `idempotency_key` | `VARCHAR(200)` | UNIQUE, NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL |
| `attempt_count` | `INTEGER` | NOT NULL, défaut 0 |
| `error_message` | `TEXT` | NULL |
| `started_at` | `TIMESTAMPTZ` | NULL |
| `completed_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- job_type IN (extract_text, classify, embed, analyze_contract, index_research, generate_pitch)
- status IN (queued, running, succeeded, failed, cancelled)

## 7. Domaine — Contracts

### `contract_analyses` — Nouvelle

Version d'analyse d'un contrat sans modification automatique du document.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `document_version_id` | `UUID` | FK document_versions.id, NOT NULL |
| `analysis_version` | `INTEGER` | NOT NULL |
| `contract_type` | `VARCHAR(100)` | NULL |
| `overall_risk_level` | `VARCHAR(30)` | NULL |
| `summary` | `TEXT` | NULL |
| `recommendations` | `JSONB` | NOT NULL, défaut [] |
| `missing_context` | `JSONB` | NOT NULL, défaut [] |
| `verification_status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(document_version_id, analysis_version)
- overall_risk_level IN (low, medium, high, critical, unknown)

**Index :**
- INDEX project_id
- INDEX document_version_id

### `contract_clauses` — Nouvelle

Clauses détectées, risques, recommandations et sources associées.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `contract_analysis_id` | `UUID` | FK contract_analyses.id, NOT NULL, CASCADE |
| `clause_order` | `INTEGER` | NOT NULL |
| `clause_type` | `VARCHAR(120)` | NULL |
| `heading` | `TEXT` | NULL |
| `extracted_text` | `TEXT` | NOT NULL |
| `risk_level` | `VARCHAR(30)` | NOT NULL, défaut unknown |
| `finding` | `TEXT` | NULL |
| `recommendation` | `TEXT` | NULL |
| `source_refs` | `JSONB` | NOT NULL, défaut [] |
| `confidence` | `NUMERIC(5,4)` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(contract_analysis_id, clause_order)

## 8. Domaine — Regulatory

### `regulatory_assessments` — Modifiée

Évaluations réglementaires versionnées d'un projet, avec instantané des sources et validation.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `assessment_version` | `INTEGER` | NOT NULL |
| `jurisdiction` | `VARCHAR(20)` | NOT NULL, défaut FR |
| `product_category` | `VARCHAR(120)` | NULL |
| `regulated_activities` | `JSONB` | NOT NULL, défaut [] |
| `applicable_regulatory_domains` | `JSONB` | NOT NULL, défaut [] |
| `applicable_regulations` | `JSONB` | NOT NULL, défaut [] |
| `required_registrations` | `JSONB` | NOT NULL, défaut [] |
| `required_authorizations` | `JSONB` | NOT NULL, défaut [] |
| `required_certifications` | `JSONB` | NOT NULL, défaut [] |
| `compliance_obligations` | `JSONB` | NOT NULL, défaut [] |
| `regulatory_risks` | `JSONB` | NOT NULL, défaut [] |
| `missing_information` | `JSONB` | NOT NULL, défaut [] |
| `recommended_actions` | `JSONB` | NOT NULL, défaut [] |
| `compliance_checklist` | `JSONB` | NOT NULL, défaut [] |
| `readiness_level` | `VARCHAR(40)` | NULL |
| `confidence` | `NUMERIC(5,4)` | NULL |
| `requires_human_validation` | `BOOLEAN` | NOT NULL, défaut true |
| `knowledge_snapshot` | `JSONB` | NOT NULL, défaut {} |
| `verification_status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, assessment_version)

**Index :**
- INDEX project_id, generated_at DESC

### `roadmap_steps` — Modifiée

Étapes ordonnées d'une roadmap de lancement ou de conformité.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `roadmap_type` | `VARCHAR(40)` | NOT NULL, défaut launch |
| `category` | `VARCHAR(60)` | NOT NULL |
| `title` | `VARCHAR(255)` | NOT NULL |
| `description` | `TEXT` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut not_started |
| `priority` | `INTEGER` | NOT NULL, défaut 0 |
| `due_date` | `DATE` | NULL |
| `depends_on_step_id` | `UUID` | FK roadmap_steps.id, NULL |
| `generated_by_agent` | `VARCHAR(80)` | NULL |
| `source_refs` | `JSONB` | NOT NULL, défaut [] |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- roadmap_type IN (launch, regulatory, compliance)
- status IN (not_started, in_progress, blocked, completed, not_applicable)

**Index :**
- INDEX project_id, roadmap_type, status

## 9. Domaine — Regulatory Watch

### `regulatory_updates` — Nouvelle

Événement réglementaire ou documentaire détecté dans une source officielle.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `knowledge_document_id` | `UUID` | FK knowledge_documents.id, NULL |
| `jurisdiction` | `VARCHAR(20)` | NOT NULL, défaut FR |
| `domain` | `VARCHAR(120)` | NULL |
| `title` | `TEXT` | NOT NULL |
| `summary` | `TEXT` | NULL |
| `change_type` | `VARCHAR(40)` | NOT NULL |
| `effective_date` | `DATE` | NULL |
| `published_at` | `TIMESTAMPTZ` | NULL |
| `detected_at` | `TIMESTAMPTZ` | NOT NULL |
| `source_snapshot` | `JSONB` | NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut detected |

**Contraintes :**
- change_type IN (new, amended, repealed, guidance, announcement)
- status IN (detected, reviewed, published, ignored)

**Index :**
- INDEX domain
- INDEX detected_at DESC

### `regulatory_watch_subscriptions` — Nouvelle

Préférences de veille d'un projet, dérivées ou confirmées par l'utilisateur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `domains` | `JSONB` | NOT NULL, défaut [] |
| `keywords` | `JSONB` | NOT NULL, défaut [] |
| `jurisdictions` | `JSONB` | NOT NULL, défaut [FR, EU] |
| `active` | `BOOLEAN` | NOT NULL, défaut true |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id)

### `project_regulatory_impacts` — Nouvelle

Analyse de pertinence et d'impact d'une mise à jour réglementaire pour un projet.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `regulatory_update_id` | `UUID` | FK regulatory_updates.id, NOT NULL, CASCADE |
| `relevance_level` | `VARCHAR(30)` | NOT NULL |
| `impact_level` | `VARCHAR(30)` | NOT NULL |
| `explanation` | `TEXT` | NULL |
| `recommended_actions` | `JSONB` | NOT NULL, défaut [] |
| `status` | `VARCHAR(30)` | NOT NULL, défaut unread |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, regulatory_update_id)
- status IN (unread, reviewed, actioned, dismissed)

**Index :**
- INDEX project_id, status

### `notifications` — Nouvelle

Notifications applicatives destinées aux utilisateurs authentifiés.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NOT NULL, CASCADE |
| `notification_type` | `VARCHAR(60)` | NOT NULL |
| `title` | `VARCHAR(255)` | NOT NULL |
| `body` | `TEXT` | NULL |
| `payload` | `JSONB` | NOT NULL, défaut {} |
| `read_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Index :**
- INDEX user_id, read_at, created_at DESC

## 10. Domaine — Compliance

### `compliance_frameworks` — Nouvelle

Référentiels versionnés de conformité : RGPD, AI Act, ISO/IEC 27001, ISO/IEC 42001, etc.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `code` | `VARCHAR(80)` | NOT NULL |
| `name` | `VARCHAR(255)` | NOT NULL |
| `version` | `VARCHAR(80)` | NOT NULL |
| `framework_type` | `VARCHAR(30)` | NOT NULL |
| `jurisdiction` | `VARCHAR(20)` | NULL |
| `official_source_url` | `TEXT` | NULL |
| `active` | `BOOLEAN` | NOT NULL, défaut true |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(code, version)
- framework_type IN (regulation, standard, certification_scheme, internal_baseline)

### `compliance_controls` — Nouvelle

Exigences ou contrôles atomiques d'un référentiel.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `framework_id` | `UUID` | FK compliance_frameworks.id, NOT NULL, CASCADE |
| `control_code` | `VARCHAR(120)` | NOT NULL |
| `title` | `TEXT` | NOT NULL |
| `description` | `TEXT` | NULL |
| `weight` | `NUMERIC(8,4)` | NOT NULL, défaut 1 |
| `mandatory` | `BOOLEAN` | NOT NULL, défaut true |
| `evidence_requirements` | `JSONB` | NOT NULL, défaut [] |
| `source_refs` | `JSONB` | NOT NULL, défaut [] |
| `active` | `BOOLEAN` | NOT NULL, défaut true |

**Contraintes :**
- UNIQUE(framework_id, control_code)

**Index :**
- INDEX framework_id

### `compliance_assessments` — Nouvelle

Évaluation versionnée d'un projet pour un référentiel précis.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `framework_id` | `UUID` | FK compliance_frameworks.id, NOT NULL |
| `assessment_version` | `INTEGER` | NOT NULL |
| `overall_score` | `NUMERIC(5,2)` | NULL |
| `maturity_level` | `VARCHAR(40)` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut draft |
| `score_method_version` | `VARCHAR(50)` | NOT NULL |
| `evidence_coverage` | `NUMERIC(5,2)` | NULL |
| `requires_human_validation` | `BOOLEAN` | NOT NULL, défaut true |
| `summary` | `TEXT` | NULL |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, framework_id, assessment_version)
- overall_score BETWEEN 0 AND 100
- status IN (draft, generated, verified, superseded)

**Index :**
- INDEX project_id, framework_id, generated_at DESC

**Notes de conception :**
- Le score mesure la maturité et les preuves disponibles ; il ne constitue ni une certification ni une garantie juridique.

### `compliance_control_results` — Nouvelle

Résultat explicable pour chaque contrôle évalué.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `assessment_id` | `UUID` | FK compliance_assessments.id, NOT NULL, CASCADE |
| `control_id` | `UUID` | FK compliance_controls.id, NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL |
| `score` | `NUMERIC(5,2)` | NULL |
| `confidence` | `NUMERIC(5,4)` | NULL |
| `rationale` | `TEXT` | NULL |
| `gaps` | `JSONB` | NOT NULL, défaut [] |
| `recommended_actions` | `JSONB` | NOT NULL, défaut [] |
| `source_refs` | `JSONB` | NOT NULL, défaut [] |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(assessment_id, control_id)
- status IN (not_assessed, compliant, partially_compliant, non_compliant, not_applicable, insufficient_evidence)

### `compliance_evidence` — Nouvelle

Preuve rattachée à un résultat de contrôle avec statut de validation.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `control_result_id` | `UUID` | FK compliance_control_results.id, NOT NULL, CASCADE |
| `document_version_id` | `UUID` | FK document_versions.id, NULL |
| `evidence_type` | `VARCHAR(50)` | NOT NULL |
| `description` | `TEXT` | NULL |
| `validation_status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `provided_by_user_id` | `UUID` | FK users.id, NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- validation_status IN (pending, accepted, rejected, expired)

## 11. Domaine — Investment

### `investor_profiles` — Modifiée

Profil d'investisseur, thèse et critères structurés.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NULL |
| `organization_name` | `VARCHAR(255)` | NOT NULL |
| `investor_type` | `VARCHAR(80)` | NOT NULL |
| `description` | `TEXT` | NULL |
| `investment_thesis` | `TEXT` | NULL |
| `preferred_sectors` | `JSONB` | NOT NULL, défaut [] |
| `preferred_subsectors` | `JSONB` | NOT NULL, défaut [] |
| `preferred_business_models` | `JSONB` | NOT NULL, défaut [] |
| `preferred_maturity_levels` | `JSONB` | NOT NULL, défaut [] |
| `preferred_countries` | `JSONB` | NOT NULL, défaut [FR] |
| `preferred_technologies` | `JSONB` | NOT NULL, défaut [] |
| `minimum_ticket` | `NUMERIC(18,2)` | NULL |
| `maximum_ticket` | `NUMERIC(18,2)` | NULL |
| `currency` | `VARCHAR(3)` | NOT NULL, défaut EUR |
| `requires_registered_company` | `BOOLEAN` | NULL |
| `requires_prototype` | `BOOLEAN` | NULL |
| `requires_revenue` | `BOOLEAN` | NULL |
| `accepts_regulated_industries` | `BOOLEAN` | NULL |
| `risk_tolerance` | `VARCHAR(40)` | NULL |
| `profile_embedding` | `VECTOR(n)` | NULL |
| `active` | `BOOLEAN` | NOT NULL, défaut true |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Index :**
- HNSW profile_embedding vector_cosine_ops
- INDEX active

### `investor_matches` — Modifiée

Rapport préliminaire de correspondance entre projet et investisseur, d'abord fondé sur des données structurées et un appel LLM.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `investor_id` | `UUID` | FK investor_profiles.id, NOT NULL, CASCADE |
| `match_version` | `INTEGER` | NOT NULL |
| `match_method` | `VARCHAR(40)` | NOT NULL, défaut llm_preliminary |
| `match_strength` | `VARCHAR(30)` | NULL |
| `overall_score` | `NUMERIC(5,4)` | NULL |
| `semantic_score` | `NUMERIC(5,4)` | NULL |
| `sector_score` | `NUMERIC(5,4)` | NULL |
| `geography_score` | `NUMERIC(5,4)` | NULL |
| `maturity_score` | `NUMERIC(5,4)` | NULL |
| `ticket_score` | `NUMERIC(5,4)` | NULL |
| `compliance_maturity_score` | `NUMERIC(5,4)` | NULL |
| `match_reasons` | `JSONB` | NOT NULL, défaut [] |
| `warnings` | `JSONB` | NOT NULL, défaut [] |
| `report` | `JSONB` | NOT NULL, défaut {} |
| `input_snapshot` | `JSONB` | NOT NULL |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, investor_id, match_version)
- match_method IN (llm_preliminary, rules, semantic, hybrid)
- match_strength IN (weak, moderate, strong, unknown)

**Notes de conception :**
- Les scores composantes sont optionnels en V1. Le rapport explique au minimum secteur, stade, géographie, technologie, ticket et points d'attention.

### `investment_opportunities` — Nouvelle

Appels à projets, opportunités ou programmes publiés par un investisseur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `investor_profile_id` | `UUID` | FK investor_profiles.id, NOT NULL, CASCADE |
| `title` | `VARCHAR(255)` | NOT NULL |
| `description` | `TEXT` | NOT NULL |
| `opportunity_type` | `VARCHAR(60)` | NOT NULL |
| `criteria` | `JSONB` | NOT NULL, défaut {} |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut authenticated |
| `status` | `VARCHAR(30)` | NOT NULL, défaut draft |
| `application_deadline` | `TIMESTAMPTZ` | NULL |
| `published_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- status IN (draft, published, closed, archived)

### `opportunity_applications` — Nouvelle

Manifestation d'intérêt d'un projet pour une opportunité.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `opportunity_id` | `UUID` | FK investment_opportunities.id, NOT NULL, CASCADE |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `submitted_by_user_id` | `UUID` | FK users.id, NOT NULL |
| `message` | `TEXT` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut submitted |
| `submitted_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(opportunity_id, project_id)
- status IN (draft, submitted, reviewing, accepted, rejected, withdrawn)

### `ecosystem_events` — Nouvelle

Événements et hackathons publiés par un investisseur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `organizer_user_id` | `UUID` | FK users.id, NOT NULL |
| `investor_profile_id` | `UUID` | FK investor_profiles.id, NULL |
| `event_type` | `VARCHAR(40)` | NOT NULL |
| `title` | `VARCHAR(255)` | NOT NULL |
| `description` | `TEXT` | NULL |
| `location_type` | `VARCHAR(30)` | NOT NULL |
| `location_details` | `JSONB` | NOT NULL, défaut {} |
| `starts_at` | `TIMESTAMPTZ` | NOT NULL |
| `ends_at` | `TIMESTAMPTZ` | NOT NULL |
| `registration_url` | `TEXT` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut draft |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- event_type IN (event, hackathon, webinar, call_for_projects)
- location_type IN (online, onsite, hybrid)

### `event_registrations` — Nouvelle

Inscription d'un utilisateur ou d'un projet à un événement.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK ecosystem_events.id, NOT NULL, CASCADE |
| `user_id` | `UUID` | FK users.id, NOT NULL, CASCADE |
| `project_id` | `UUID` | FK projects.id, NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut registered |
| `registered_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(event_id, user_id, project_id)

### `pitch_decks` — Nouvelle

Présentation générée pour un projet et adaptée à un investisseur donné.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `investor_profile_id` | `UUID` | FK investor_profiles.id, NULL |
| `generated_by_user_id` | `UUID` | FK users.id, NOT NULL |
| `version` | `INTEGER` | NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut draft |
| `content` | `JSONB` | NOT NULL |
| `generated_document_id` | `UUID` | FK documents.id, NULL |
| `input_snapshot` | `JSONB` | NOT NULL |
| `verification_status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, investor_profile_id, version)

**Notes de conception :**
- Le générateur doit refuser d'inventer traction, clients, chiffre d'affaires, équipe, partenariats ou métriques absentes des données confirmées.

## 12. Domaine — Network

### `contact_requests` — Nouvelle

Demande de mise en relation, sans transaction financière dans la plateforme.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `requester_user_id` | `UUID` | FK users.id, NOT NULL |
| `source_project_id` | `UUID` | FK projects.id, NULL |
| `target_type` | `VARCHAR(40)` | NOT NULL |
| `target_id` | `UUID` | NOT NULL |
| `message` | `TEXT` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `responded_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- target_type IN (project, investor_profile, researcher_profile, research_output)
- status IN (pending, accepted, declined, cancelled)

## 13. Domaine — Research

### `researcher_profiles` — Modifiée

Profil d'un chercheur ou d'un centre de recherche. Ce profil décrit l'acteur qui publie et valide les métadonnées de découverte.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NULL |
| `profile_type` | `VARCHAR(30)` | NOT NULL |
| `display_name` | `VARCHAR(255)` | NOT NULL |
| `institution_name` | `VARCHAR(255)` | NULL |
| `laboratory_name` | `VARCHAR(255)` | NULL |
| `biography` | `TEXT` | NULL |
| `research_domains` | `JSONB` | NOT NULL, défaut [] |
| `country_code` | `VARCHAR(2)` | NOT NULL, défaut FR |
| `website` | `TEXT` | NULL |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut authenticated |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- profile_type IN (researcher, research_center)
- visibility IN (private, authenticated, public)

### `research_outputs` — Modifiée

Travail scientifique déposé par un chercheur. Cette table contient les métadonnées bibliographiques, les déclarations de droits et la politique d'accès ; elle ne contient pas d'application inventée par l'IA.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `researcher_profile_id` | `UUID` | FK researcher_profiles.id, NOT NULL, CASCADE |
| `primary_document_id` | `UUID` | FK documents.id, NULL |
| `output_type` | `VARCHAR(40)` | NOT NULL, défaut paper |
| `title` | `VARCHAR(500)` | NOT NULL |
| `author_abstract` | `TEXT` | NULL, résumé fourni par l'auteur ou l'éditeur |
| `raw_description` | `TEXT` | NULL |
| `authors` | `JSONB` | NOT NULL, défaut [] |
| `publication_date` | `DATE` | NULL |
| `external_identifier` | `VARCHAR(255)` | NULL, DOI ou identifiant équivalent |
| `external_publication_url` | `TEXT` | NULL |
| `rights_holder` | `TEXT` | NULL, déclaré ou vérifié, jamais inféré |
| `copyright_notice` | `TEXT` | NULL |
| `license_code` | `VARCHAR(80)` | NULL |
| `rights_status` | `VARCHAR(30)` | NOT NULL, défaut unverified |
| `full_text_access_policy` | `VARCHAR(30)` | NOT NULL, défaut request_required |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut private |
| `status` | `VARCHAR(30)` | NOT NULL, défaut draft |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- output_type IN (paper, report, thesis, dataset, method, prototype, other)
- rights_status IN (unverified, user_declared, verified, disputed)
- full_text_access_policy IN (private, request_required, external_link_only, public_by_license)
- visibility IN (private, authenticated_metadata, public_metadata)
- status IN (draft, processing, pending_author_review, published, archived)

**Index :**
- INDEX researcher_profile_id
- INDEX publication_date
- INDEX status, visibility

**Notes de conception :**
- Le fichier intégral est géré par `documents` et `document_versions` dans le stockage objet chiffré.
- `rights_holder`, `license_code` et la politique d'accès proviennent du chercheur ou d'une source vérifiée ; le Research Agent ne les déduit pas.

### `research_output_extractions` — Nouvelle

Sortie structurée et versionnée du Research Agent pour une version précise du papier. Tous les champs doivent être soutenus par une `evidence_map` et soumis à la validation de l'auteur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `research_output_id` | `UUID` | FK research_outputs.id, NOT NULL, CASCADE |
| `document_version_id` | `UUID` | FK document_versions.id, NOT NULL |
| `extraction_version` | `INTEGER` | NOT NULL |
| `public_abstract` | `TEXT` | NULL, brouillon d'Abstract RegBridge |
| `scientific_domain` | `VARCHAR(255)` | NULL |
| `subdomains` | `JSONB` | NOT NULL, défaut [] |
| `research_problem` | `TEXT` | NULL |
| `research_objective` | `TEXT` | NULL |
| `methods_explicitly_mentioned` | `JSONB` | NOT NULL, défaut [] |
| `technologies_explicitly_mentioned` | `JSONB` | NOT NULL, défaut [] |
| `reported_results` | `JSONB` | NOT NULL, défaut [] |
| `applications_explicitly_mentioned` | `JSONB` | NOT NULL, défaut [] |
| `keywords` | `JSONB` | NOT NULL, défaut [] |
| `limitations_explicitly_mentioned` | `JSONB` | NOT NULL, défaut [] |
| `evidence_map` | `JSONB` | NOT NULL, défaut {} |
| `validation_status` | `VARCHAR(40)` | NOT NULL, défaut pending_author_review |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `approved_by_user_id` | `UUID` | FK users.id, NULL |
| `approved_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(research_output_id, extraction_version)
- validation_status IN (pending_author_review, author_approved, author_modified, rejected, superseded)

**Notes de conception :**
- `applications_explicitly_mentioned` reste `[]` lorsqu'aucune application n'est nommée dans le document.
- Chaque élément de liste et chaque résultat doit posséder un localisateur vérifiable dans `evidence_map`.
- Cette table est interne ; elle ne constitue pas automatiquement une publication publique.

### `research_output_publications` — Nouvelle

Snapshot approuvé utilisé pour les écrans de découverte et le matching. Il ne doit contenir que les informations validées par le chercheur.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `research_output_id` | `UUID` | FK research_outputs.id, NOT NULL, CASCADE |
| `extraction_id` | `UUID` | FK research_output_extractions.id, NOT NULL |
| `publication_version` | `INTEGER` | NOT NULL |
| `abstract_regbridge` | `TEXT` | NOT NULL |
| `approved_snapshot` | `JSONB` | NOT NULL |
| `attribution_text` | `TEXT` | NOT NULL |
| `license_display` | `VARCHAR(120)` | NULL |
| `visibility` | `VARCHAR(30)` | NOT NULL, défaut authenticated |
| `metadata_embedding` | `VECTOR(n)` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut published |
| `published_by_user_id` | `UUID` | FK users.id, NOT NULL |
| `published_at` | `TIMESTAMPTZ` | NOT NULL |
| `withdrawn_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(research_output_id, publication_version)
- visibility IN (authenticated, public)
- status IN (published, withdrawn, superseded)

**Index :**
- HNSW metadata_embedding vector_cosine_ops
- INDEX status, visibility, published_at DESC

**Notes de conception :**
- `approved_snapshot` contient notamment domaine, sous-domaines, problématique, objectif, méthodes, technologies, résultats généraux, applications explicitement citées, mots-clés et limitations autorisées.
- Aucun passage détaillé permettant de reproduire la recherche ne doit être indexé dans le vecteur de découverte.

### `research_project_matches` — Modifiée

Correspondance versionnée entre les besoins confirmés d'un projet entrepreneurial et une publication approuvée.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` | FK projects.id, NOT NULL, CASCADE |
| `research_output_publication_id` | `UUID` | FK research_output_publications.id, NOT NULL, CASCADE |
| `match_version` | `INTEGER` | NOT NULL |
| `match_strength` | `VARCHAR(20)` | NOT NULL, défaut unknown |
| `semantic_score` | `NUMERIC(5,4)` | NULL |
| `domain_score` | `NUMERIC(5,4)` | NULL |
| `technology_score` | `NUMERIC(5,4)` | NULL |
| `need_alignment_score` | `NUMERIC(5,4)` | NULL |
| `matched_dimensions` | `JSONB` | NOT NULL, défaut [] |
| `match_reasons` | `JSONB` | NOT NULL, défaut [] |
| `warnings` | `JSONB` | NOT NULL, défaut [] |
| `input_snapshot` | `JSONB` | NOT NULL |
| `agent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(project_id, research_output_publication_id, match_version)
- match_strength IN (weak, moderate, strong, unknown)

**Notes de conception :**
- Chaque raison doit relier un champ confirmé du besoin startup à un champ du snapshot approuvé.
- Le match ne crée ni nouvelle application, ni recommandation scientifique, ni droit d'accès au texte intégral.

### `research_access_requests` — Nouvelle

Demande distincte de contact, d'accès au document scientifique ou de collaboration. La décision du chercheur ne transfère aucun droit de propriété intellectuelle.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `research_output_id` | `UUID` | FK research_outputs.id, NOT NULL, CASCADE |
| `requester_user_id` | `UUID` | FK users.id, NOT NULL |
| `requester_project_id` | `UUID` | FK projects.id, NULL |
| `research_project_match_id` | `UUID` | FK research_project_matches.id, NULL |
| `request_type` | `VARCHAR(30)` | NOT NULL |
| `declared_need` | `TEXT` | NULL |
| `purpose` | `TEXT` | NULL |
| `message` | `TEXT` | NULL |
| `requested_scope` | `JSONB` | NOT NULL, défaut {} |
| `approved_scope` | `JSONB` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut pending |
| `expires_at` | `TIMESTAMPTZ` | NULL |
| `decided_by_user_id` | `UUID` | FK users.id, NULL |
| `decided_at` | `TIMESTAMPTZ` | NULL |
| `revoked_at` | `TIMESTAMPTZ` | NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- request_type IN (contact, full_text_access, collaboration)
- status IN (pending, accepted, partially_accepted, declined, expired, revoked, cancelled)

**Index :**
- INDEX research_output_id, status
- INDEX requester_project_id, created_at DESC

**Notes de conception :**
- L'acceptation peut créer un accès limité et expirant, mais ne vaut ni licence d'exploitation ni cession de droits.
- Les accords contractuels éventuels restent hors de ce schéma initial et hors du périmètre transactionnel de RegBridge.

### Héritage Patent Guidance — Déprécié

Les tables historiques `patent_projects` et `patent_guidance_steps`, si elles existent déjà dans un environnement, passent en lecture seule pendant la migration. Aucun nouvel endpoint ni nouveau traitement ne doit y écrire. Après vérification de l'absence de dépendance, elles sont archivées puis supprimées dans une migration ultérieure. Elles ne font pas partie des 50 tables de la cible V2.1.

## 14. Domaine — AI & Conversations

### `conversation_threads` — Nouvelle

Historique persistant des conversations des utilisateurs authentifiés.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK users.id, NOT NULL, CASCADE |
| `title` | `VARCHAR(255)` | NULL |
| `subject_type` | `VARCHAR(40)` | NULL |
| `subject_id` | `UUID` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut active |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |
| `archived_at` | `TIMESTAMPTZ` | NULL |

**Contraintes :**
- status IN (active, archived, deleted)

**Index :**
- INDEX user_id, updated_at DESC

**Notes de conception :**
- Les visiteurs non authentifiés n'ont pas d'historique persistant.

### `conversation_messages` — Nouvelle

Messages d'une conversation, avec statut et contenu structuré optionnel.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `thread_id` | `UUID` | FK conversation_threads.id, NOT NULL, CASCADE |
| `role` | `VARCHAR(20)` | NOT NULL |
| `content` | `TEXT` | NOT NULL |
| `content_json` | `JSONB` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL, défaut completed |
| `parent_message_id` | `UUID` | FK conversation_messages.id, NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- role IN (user, assistant, system, tool)
- status IN (pending, completed, failed, redacted)

**Index :**
- INDEX thread_id, created_at

### `agent_runs` — Modifiée

Journal de chaque exécution d'agent ou étape d'orchestration, avec entrées/sorties structurées.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `request_id` | `UUID` | NOT NULL; corrélation partagée entre les runs d'une même requête |
| `parent_run_id` | `UUID` | FK agent_runs.id, NULL |
| `user_id` | `UUID` | FK users.id, NULL |
| `message_id` | `UUID` | FK conversation_messages.id, NULL |
| `agent_name` | `VARCHAR(80)` | NOT NULL |
| `capability` | `VARCHAR(100)` | NOT NULL |
| `subject_type` | `VARCHAR(50)` | NULL |
| `subject_id` | `UUID` | NULL |
| `request_payload` | `JSONB` | NOT NULL |
| `response_payload` | `JSONB` | NULL |
| `model_metadata` | `JSONB` | NOT NULL, défaut {} |
| `prompt_version` | `VARCHAR(80)` | NULL |
| `status` | `VARCHAR(30)` | NOT NULL |
| `error_code` | `VARCHAR(80)` | NULL |
| `error_message` | `TEXT` | NULL |
| `started_at` | `TIMESTAMPTZ` | NOT NULL |
| `completed_at` | `TIMESTAMPTZ` | NULL |

**Contraintes :**
- status IN (queued, running, succeeded, failed, cancelled)

**Index :**
- INDEX request_id
- INDEX parent_run_id
- INDEX agent_name, capability
- INDEX subject_type, subject_id
- INDEX user_id, started_at DESC

**Notes de conception :**
- subject_type/subject_id deviennent NULL pour permettre les questions générales anonymes.

## 15. Domaine — Knowledge & RAG

### `knowledge_documents` — Nouvelle

Métadonnées de gouvernance des documents indexés dans Qdrant.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `external_id` | `VARCHAR(255)` | NULL |
| `publisher` | `VARCHAR(255)` | NOT NULL |
| `title` | `TEXT` | NOT NULL |
| `canonical_url` | `TEXT` | NOT NULL |
| `document_type` | `VARCHAR(80)` | NULL |
| `jurisdiction` | `VARCHAR(20)` | NULL |
| `publication_date` | `DATE` | NULL |
| `last_updated_date` | `DATE` | NULL |
| `retrieved_at` | `TIMESTAMPTZ` | NOT NULL |
| `content_hash` | `CHAR(64)` | NOT NULL |
| `qdrant_collection` | `VARCHAR(255)` | NOT NULL |
| `qdrant_document_id` | `VARCHAR(255)` | NOT NULL |
| `active` | `BOOLEAN` | NOT NULL, défaut true |
| `supersedes_document_id` | `UUID` | FK knowledge_documents.id, NULL |

**Contraintes :**
- UNIQUE(qdrant_collection, qdrant_document_id, content_hash)

**Index :**
- INDEX publisher
- INDEX jurisdiction
- INDEX active

**Notes de conception :**
- Les sources initiales sont data.gouv.fr, Bpifrance et CNIL ; le modèle accepte d'autres sources officielles.

### `agent_run_sources` — Nouvelle

Sources précises utilisées par un agent pour soutenir une affirmation.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `agent_run_id` | `UUID` | FK agent_runs.id, NOT NULL, CASCADE |
| `knowledge_document_id` | `UUID` | FK knowledge_documents.id, NULL |
| `source_title` | `TEXT` | NOT NULL |
| `source_publisher` | `VARCHAR(255)` | NOT NULL |
| `source_url` | `TEXT` | NOT NULL |
| `chunk_id` | `VARCHAR(255)` | NULL |
| `passage_locator` | `JSONB` | NOT NULL, défaut {} |
| `quoted_excerpt_hash` | `CHAR(64)` | NULL |
| `relevance_score` | `NUMERIC(5,4)` | NULL |
| `retrieved_at` | `TIMESTAMPTZ` | NOT NULL |

**Index :**
- INDEX agent_run_id
- INDEX knowledge_document_id

## 16. Domaine — AI Verification

### `response_verifications` — Nouvelle

Résultat d'une vérification de réponse avant restitution ou publication.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `agent_run_id` | `UUID` | FK agent_runs.id, NOT NULL, CASCADE |
| `verification_version` | `INTEGER` | NOT NULL |
| `grounding_status` | `VARCHAR(20)` | NOT NULL |
| `citation_status` | `VARCHAR(20)` | NOT NULL |
| `consistency_status` | `VARCHAR(20)` | NOT NULL |
| `scope_status` | `VARCHAR(20)` | NOT NULL |
| `safety_status` | `VARCHAR(20)` | NOT NULL |
| `verdict` | `VARCHAR(20)` | NOT NULL |
| `details` | `JSONB` | NOT NULL, défaut {} |
| `verified_by` | `VARCHAR(80)` | NOT NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- UNIQUE(agent_run_id, verification_version)
- Chaque statut IN (pass, warn, fail, not_applicable)
- verdict IN (pass, pass_with_warnings, block)

**Index :**
- INDEX agent_run_id

## 17. Domaine — Audit

### `audit_logs` — Nouvelle

Journal append-only des actions sensibles et des changements de droits ou de visibilité.

| Colonne | Type | Règles |
|---|---|---|
| `id` | `UUID` | PK |
| `actor_user_id` | `UUID` | FK users.id, NULL |
| `actor_type` | `VARCHAR(30)` | NOT NULL |
| `action` | `VARCHAR(120)` | NOT NULL |
| `resource_type` | `VARCHAR(80)` | NOT NULL |
| `resource_id` | `UUID` | NULL |
| `project_id` | `UUID` | FK projects.id, NULL |
| `request_id` | `UUID` | NULL |
| `ip_hash` | `CHAR(64)` | NULL |
| `metadata` | `JSONB` | NOT NULL, défaut {} |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

**Contraintes :**
- actor_type IN (anonymous, user, system, admin)

**Index :**
- INDEX resource_type, resource_id
- INDEX project_id, created_at DESC
- INDEX actor_user_id, created_at DESC

## Relations principales

```text
users --< user_identities
users --< user_roles >-- roles
users --< project_members >-- projects
projects -- project_profiles / project_legal_profiles / project_business_profiles / project_public_profiles
projects --< documents --< document_versions --< contract_analyses --< contract_clauses
projects --< regulatory_assessments / roadmap_steps / project_regulatory_impacts
compliance_frameworks --< compliance_controls
projects --< compliance_assessments --< compliance_control_results --< compliance_evidence
projects --< investor_matches >-- investor_profiles
investor_profiles --< investment_opportunities --< opportunity_applications >-- projects
researcher_profiles --< research_outputs --< research_output_extractions --< research_output_publications
projects --< research_project_matches >-- research_output_publications
research_outputs --< research_access_requests >-- projects / users
users --< conversation_threads --< conversation_messages --< agent_runs
agent_runs --< agent_run_sources >-- knowledge_documents
agent_runs --< response_verifications
```

## Règles de suppression

- Les jointures et enfants purement métier utilisent généralement `ON DELETE CASCADE`.
- Les preuves d’audit ne sont jamais supprimées en cascade ; elles peuvent être pseudonymisées selon la politique de rétention.
- Les documents utilisent une suppression logique (`deleted_at`) avant purge contrôlée du stockage objet.
- Les évaluations et rapports historiques sont conservés et marqués `superseded` plutôt qu’écrasés.

## Stratégie de migration depuis le schéma initial

1. Créer les nouvelles tables sans supprimer les tables existantes.
2. Ajouter `status` à `users`, `visibility` à `projects` et les colonnes de version/validation.
3. Backfiller `project_members` depuis `projects.owner_user_id` avec le rôle `owner`.
4. Mapper `idea_owner` vers `entrepreneur`; conserver temporairement `startup_member` pour compatibilité puis migrer vers `project_members`.
5. Introduire `documents` et migrer `research_outputs.document_location` vers `primary_document_id` lorsque les fichiers sont disponibles.
6. Créer `research_output_extractions`, migrer uniquement les champs explicitement justifiables et laisser `applications_explicitly_mentioned=[]` en l'absence de mention textuelle.
7. Créer `research_output_publications`; aucune extraction historique ne devient publique sans validation explicite du chercheur.
8. Recréer les matches recherche-projet contre un snapshot approuvé et supprimer la dépendance aux champs `possible_applications` ou `application_score` non traçables.
9. Créer `research_access_requests` et appliquer l'accès au texte intégral par autorisation limitée et auditable.
10. Désactiver les nouvelles écritures dans les tables Patent Guidance historiques, les conserver temporairement pour audit puis planifier leur archivage/suppression.
11. Renommer la sémantique `regulatory_score` en `compliance_maturity_score` dans `investor_matches`.
12. Déployer conversations, sources et vérifications avant d'activer l'historique utilisateur.
13. Auditer les stores utilisant `startup_profiles` et `user_entitlements` avant dépréciation; aucune suppression directe.

## Contrats applicatifs

- Les repositories sont les seuls composants autorisés à exécuter l’accès SQL.
- Les `ContextBuilder` projettent uniquement les champs nécessaires à un agent.
- Les agents reçoivent des modèles Pydantic validés, jamais des instances SQLAlchemy.
- Chaque sortie d’agent susceptible de contenir une affirmation réglementaire expose `findings`, `recommendations`, `sources`, `confidence`, `limitations` et `verification`.
- Les champs provenant d’un agent restent distingués des champs confirmés par l’utilisateur grâce à `project_field_values`.
- Pour Research, toute information extraite possède un localisateur dans `evidence_map`; aucune application absente du papier ne peut être créée.
- Seuls les snapshots `author_approved` ou `author_modified` peuvent alimenter `research_output_publications` et le matching.
