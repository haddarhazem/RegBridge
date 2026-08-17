# RegBridge Coding Agent Instructions

## Project

RegBridge.

## Architecture

- modular monolith;
- Python/FastAPI backend;
- PostgreSQL with SQLAlchemy async;
- Alembic for schema migrations;
- Pydantic contracts and configuration.

## Approved modules

`identity`, `projects`, `documents`, `regulatory`, `compliance`, `investment`, `research`, `ai`. There is no Patent Agent.

## Engineering rules

- inspect existing code before editing;
- preserve useful conventions and avoid duplicate architecture;
- implement only the requested Jira ticket;
- keep `main.py` thin and business logic outside routes;
- use typed interfaces and add tests for acceptance criteria;
- update documentation when behavior or commands change;
- all schema changes require Alembic; never manually edit shared database schemas;
- inspect the approved database documentation before changing models;
- never commit secrets or log private documents/credentials;
- do not create a microservice per AI agent.
- keep the authentication provider configurable;
- never log bearer tokens or disable JWT signature validation;
- RegBridge roles are database-controlled; do not trust arbitrary token roles;
- project/object authorization belongs to explicit later authorization logic;
- do not add authentication bypasses;
- inspect `docs/AUTHENTICATION.md` before modifying identity/authentication.

## Data/AI boundary

Future flow: PostgreSQL → Repository → ContextBuilder → validated `AgentRequest` → Agent. Agents must not receive SQLAlchemy ORM entities directly.

## Research rule

Research functionality must not invent new applications or opportunities from research papers. Future research discovery data requires author-controlled publication.

## Database source of truth:
docs/specs/RegBridge_DATABASE_SCHEMA_V2.1_RESEARCH.md

Architecture/product decisions:
docs/decisions/RegBridge_Decisions_et_tracabilite_v2.0.md

When changing database models or migrations:
- inspect the database source of truth first;
- use exact table and column names from it;
- do not invent missing fields or tables;
- do not implement future-domain tables unless the current Jira ticket requires them.

## Commands

- database: `docker compose up -d postgres`
- install: `python -m pip install -e ".[test]"`
- API: `python -m uvicorn app.main:app --reload`
- tests: `python -m pytest`
- migrations: `alembic upgrade head`

## Before finishing a task

Run relevant tests, verify acceptance criteria, summarize modified files, report assumptions and unresolved issues, and stop at the Jira ticket boundary.
