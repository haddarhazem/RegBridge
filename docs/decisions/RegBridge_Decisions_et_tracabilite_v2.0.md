# RegBridge — Journal des décisions et traçabilité

**Version :** 2.0  
**Date :** 11 août 2026  
**Statut :** décisions produit, Research et techniques consolidées

## 1. Changement structurant de la version 2.0

La version 2.0 retire le Patent Agent du périmètre fonctionnel actif. Cette fonctionnalité ne servait pas directement la proposition de valeur principale du domaine recherche, qui consiste à rapprocher des besoins réels de startups et des travaux scientifiques publiés sous le contrôle de leurs auteurs.

Le domaine Research est désormais fondé sur le flux suivant :

```text
papier scientifique autorisé
→ extraction des seules informations explicitement présentes
→ Abstract RegBridge de découverte
→ validation ou modification par le chercheur
→ publication d'un snapshot approuvé
→ matching avec les besoins confirmés d'une startup
→ demande distincte de contact, d'accès ou de collaboration
```

Le document scientifique intégral ne devient pas un service gratuit d'information et n'est jamais exposé automatiquement par le matching.

## 2. Décisions fonctionnelles

| ID | Décision | Statut | Conséquence |
|---|---|---|---|
| DEC-001 | RegBridge vise un écosystème complet et cohérent autour de la réglementation, la conformité, l'investissement et la valorisation contrôlée de la recherche. | Validée | Les modules entrepreneur, startup, investisseur, recherche, conformité et plateforme GenAI restent dans la cible. |
| DEC-002 | Les acteurs sont : visiteur, entrepreneur, startup, investisseur, chercheur/centre de recherche et administrateur technique limité. | Validée | Les accès et parcours sont définis par acteur. |
| DEC-003 | Le visiteur non authentifié peut poser des questions générales au Regulatory Agent et consulter les Abstracts RegBridge publiés. | Validée | Aucun historique persistant, import de document ou accès au texte scientifique intégral pour le visiteur. |
| DEC-004 | L'assistant entrepreneur oriente sur les démarches juridiques, administratives et réglementaires en France. | Validée | Il ne restructure pas automatiquement le business ou l'idée. |
| DEC-005 | Le Contract Agent analyse et recommande mais ne modifie jamais automatiquement un contrat. | Validée | Toute modification reste une action humaine hors du moteur d'analyse. |
| DEC-006 | Le score startup est un « Compliance Maturity Score » explicable par référentiel et preuves. | Validée | Ce score n'est ni une certification officielle ni une garantie juridique. |
| DEC-007 | Le matching investisseur V1 est un rapport LLM préliminaire basé sur des données structurées. | Validée | Les scores avancés et le moteur hybride sont reportés. |
| DEC-008 | RegBridge ne réalise aucune transaction d'investissement. | Validée | La plateforme facilite la découverte, l'explication et la mise en relation. |
| DEC-009 | Le Pitch Deck Agent adapte une présentation à un investisseur spécifique. | Validée | Il ne doit inventer aucun fait, métrique, client, revenu ou partenariat. |
| DEC-010 | Le Patent Agent explique les étapes d'une démarche brevet. | Remplacée par DEC-014 | Cette décision V1.0 n'est plus active. Les éventuelles tables historiques passent en lecture seule avant archivage. |
| DEC-011 | Le modèle économique cible est freemium. | Validée | La facturation et les plans ne sont pas implémentés dans la première livraison ; les services développés sont accessibles après connexion. |
| DEC-012 | Le réseau, les événements et les matchings sont présents sous une forme essentielle dans la première version. | Validée | Les fonctions sociales avancées restent futures. |
| DEC-013 | Il n'y a pas d'administration/modération avancée dans la première livraison. | Validée | Un rôle technique admin peut exister pour l'exploitation. |
| DEC-014 | Le Patent Agent est supprimé du périmètre fonctionnel actif. | Validée | Le catalogue actif devient Regulatory, Contract, Investment, Research et Pitch Deck. |
| DEC-015 | La valeur du domaine Research est la découverte contrôlée et la collaboration recherche-startup, non l'assistance au brevet. | Validée | Les Epics, parcours, APIs, tables et tests sont recentrés sur le papier, les besoins startup, l'accès et la collaboration. |
| DEC-016 | Le document scientifique intégral reste privé ou soumis à une politique d'accès déclarée par le chercheur. | Validée | Le document complet n'est pas indexé comme corpus public et n'est pas automatiquement disponible après un match. |
| DEC-017 | L'Abstract RegBridge est une fiche de découverte générale, non un substitut au papier. | Validée | Il ne doit pas contenir de procédure détaillée, de paramètres sensibles ou de contenu suffisant pour reproduire la recherche. |
| DEC-018 | Le chercheur valide, modifie ou rejette les métadonnées générées avant toute publication et tout matching. | Validée | Aucun snapshot `pending_author_review` n'est visible ni utilisable pour le matching. |
| DEC-019 | Le matching recherche-startup n'accorde aucun droit de propriété intellectuelle, aucune licence et aucun accès automatique. | Validée | Une demande de contact, d'accès ou de collaboration constitue un objet métier séparé, limité, révocable et audité. |

## 3. Décisions propres au Research Agent

| ID | Décision | Statut | Conséquence |
|---|---|---|---|
| DEC-RES-001 | Le Research Agent extrait uniquement des informations explicitement présentes dans la version autorisée du papier. | Validée | Chaque champ extrait possède une preuve ou un localisateur dans `evidence_map`. |
| DEC-RES-002 | Le Research Agent ne génère ni nouvelle application, ni invention, ni opportunité commerciale, ni extension scientifique. | Validée | Une information absente reste absente ; `applications_explicitly_mentioned` vaut `[]` lorsqu'aucune application n'est mentionnée. |
| DEC-RES-003 | Les champs cibles sont : domaine, sous-domaines, problématique, objectif, méthodes mentionnées, technologies mentionnées, résultats rapportés, applications explicitement citées, mots-clés et limitations mentionnées. | Validée | Le contrat Pydantic et le schéma PostgreSQL utilisent ces catégories fermées. |
| DEC-RES-004 | L'Abstract RegBridge est paraphrasé, général et soumis à validation auteur. | Validée | Il sert à comprendre le sujet et à motiver une prise de contact, sans reproduire le texte ni dévoiler le savoir-faire. |
| DEC-RES-005 | Les droits, licences et détenteurs sont déclarés par l'utilisateur ou issus d'une source vérifiée, jamais inférés par l'IA. | Validée | Les champs `rights_holder`, `license_code`, `rights_status` et `full_text_access_policy` conservent leur provenance. |
| DEC-RES-006 | Le matching utilise uniquement un `research_output_publication` approuvé et un snapshot confirmé du besoin startup. | Validée | Le papier intégral et l'extraction interne ne sont pas fournis au moteur de matching. |
| DEC-RES-007 | Chaque raison de matching relie deux champs existants : besoin startup et métadonnée approuvée du papier. | Validée | L'explication ne peut pas introduire une nouvelle application ou un raisonnement sans preuve. |
| DEC-RES-008 | Le chercheur contrôle les demandes de contact, d'accès et de collaboration. | Validée | Une réponse acceptée peut être limitée dans le temps et le périmètre, puis révoquée. |
| DEC-RES-009 | Une collaboration acceptée n'est pas une licence d'exploitation. | Validée | Les accords contractuels et transferts de droits restent hors du périmètre transactionnel initial de RegBridge. |

## 4. Décisions GenAI et RAG

| ID | Décision | Statut | Conséquence |
|---|---|---|---|
| DEC-AI-001 | Une requête passe par un orchestrateur qui sélectionne un à plusieurs agents. | Validée | Les agents sont des responsabilités logiques, pas obligatoirement des microservices. |
| DEC-AI-002 | Agents actifs : Regulatory, Contract, Investment, Research et Pitch Deck. | Validée | Le Patent Agent est retiré des prompts, routes, capacités et métriques actives. |
| DEC-AI-003 | Les agents consomment le RAG, les outils, PostgreSQL et les documents autorisés. | Validée | Le contexte transmis est filtré par un `ContextBuilder`. |
| DEC-AI-004 | Les sorties d'agents sont structurées avant agrégation. | Validée | Format attendu : constats, risques, actions, sources, confiance et limites. |
| DEC-AI-005 | Une réponse sensible passe par une vérification de grounding, citations, cohérence, périmètre et droits. | Validée | Une réponse peut être bloquée si elle n'est pas suffisamment fondée. |
| DEC-AI-006 | Toute affirmation réglementaire doit indiquer la source précise utilisée. | Validée | Titre, éditeur, URL, date et localisateur de passage doivent être disponibles. |
| DEC-AI-007 | Le corpus initial officiel provient de data.gouv.fr, Bpifrance et CNIL dans Qdrant. | Validée | Le registre `knowledge_documents` gouverne les versions et métadonnées. |
| DEC-AI-008 | Les papiers utilisateurs ne rejoignent pas le corpus réglementaire Qdrant. | Validée | Le texte scientifique intégral reste dans le stockage objet ; seuls les snapshots approuvés peuvent produire un embedding métier dans pgvector. |
| DEC-AI-009 | La vérification Research inclut un contrôle anti-extrapolation. | Validée | Toute application ou opportunité non soutenue est supprimée ou bloque la publication. |

## 5. Décisions de données

| ID | Décision | Statut | Conséquence |
|---|---|---|---|
| DEC-DATA-001 | PostgreSQL 15, SQLAlchemy 2.x asynchrone, Alembic et pgvector sont conservés. | Validée | Le flux Repository → ContextBuilder → AgentRequest reste la règle. |
| DEC-DATA-002 | `startup_member` devient une relation de projet, pas un rôle global. | Validée | Ajout de `project_members`. |
| DEC-DATA-003 | Les documents sont versionnés et stockés hors PostgreSQL. | Validée | Ajout de `documents`, `document_versions`, `document_processing_jobs`. |
| DEC-DATA-004 | L'historique de conversation est persisté pour les utilisateurs authentifiés. | Validée | Ajout de `conversation_threads` et `conversation_messages`. |
| DEC-DATA-005 | La conformité est normalisée par référentiel, contrôle, résultat et preuve. | Validée | Ajout de cinq tables de conformité. |
| DEC-DATA-006 | `patentability_assessment` et le domaine Patent Guidance sont retirés de la cible active. | Validée | Les tables existantes deviennent legacy, sans nouvelles écritures, puis sont archivées/supprimées après audit. |
| DEC-DATA-007 | Les données startup sont classées publiques, partagées ou privées. | Validée | Ajout de `project_public_profiles` et `project_access_grants`. |
| DEC-DATA-008 | PostgreSQL/pgvector sert au métier et au matching ; Qdrant sert au corpus réglementaire externe. | Validée | Les responsabilités de stockage restent distinctes. |
| DEC-DATA-009 | Research distingue le document intégral, l'extraction interne et la publication approuvée. | Validée | Ajout de `research_output_extractions` et `research_output_publications`. |
| DEC-DATA-010 | Le matching Research référence une publication approuvée, pas directement le document ou l'extraction. | Validée | `research_project_matches.research_output_publication_id` devient la FK canonique. |
| DEC-DATA-011 | Les demandes de contact, d'accès et de collaboration sont persistées séparément. | Validée | Ajout de `research_access_requests`. |
| DEC-DATA-012 | Les champs `possible_applications` et `application_score` non traçables sont retirés de la cible active. | Validée | Ils sont remplacés par `applications_explicitly_mentioned` et des dimensions de match explicables. |
| DEC-DATA-013 | Le schéma cible V2.1 comprend 50 tables actives. | Validée | Le catalogue détaillé est `RegBridge_DATABASE_SCHEMA_V2.1_RESEARCH.md`. |

## 6. Règles de traçabilité Research

Une publication scientifique visible dans RegBridge doit permettre de retrouver :

1. le `research_output` et la version exacte du document analysé ;
2. l'exécution du Research Agent ;
3. les localisateurs soutenant chaque champ extrait ;
4. l'utilisateur ayant validé ou modifié l'extraction ;
5. le snapshot exact publié ;
6. les données startup utilisées lors d'un matching ;
7. les champs appariés et les raisons du match ;
8. la demande d'accès ou de collaboration et sa décision ;
9. la portée, l'expiration et une éventuelle révocation de l'accès.

## 7. Hypothèses à valider avant production

- Le catalogue exact de sources officielles réglementaires et leur fréquence d'actualisation.
- La formule finale du Compliance Maturity Score, ses pondérations et son processus de validation.
- Les formats de documents acceptés et les limites de taille.
- Les objectifs chiffrés de disponibilité, de volumétrie et de latence après tests de charge.
- Le fournisseur d'identité, le fournisseur de stockage objet et les fournisseurs LLM.
- Les règles commerciales et contractuelles exactes des offres freemium/premium avant commercialisation.
- La politique de conservation des documents, conversations, journaux et données supprimées.
- Le niveau maximal de détail de l'Abstract RegBridge et les critères de non-reproductibilité.
- Les règles exactes de partage du texte intégral : téléchargement, consultation, durée, révocation et journalisation.
- Les champs de besoins startup retenus pour le matching Research.
- Le processus de déclaration et de vérification des droits, licences et attributions.

## 8. Sources de conception

- Discussion de cadrage RegBridge consolidée jusqu'au 11 août 2026.
- Cahier des charges RegBridge V1.0, utilisé comme baseline puis révisé.
- `DATABASE.md` : choix technologiques et séparation Repository / ContextBuilder / AgentRequest.
- `DATABASE_SCHEMA.md` : schéma métier initial créé par la migration `20260730_01_initial_business_schema.py`.
- `RegBridge_DATABASE_SCHEMA_V2.1_RESEARCH.md` : schéma cible révisé du domaine Research.
- `RegBridge_Cahier_des_charges_v2.0.docx` : source de vérité fonctionnelle et technique de la version 2.0.
