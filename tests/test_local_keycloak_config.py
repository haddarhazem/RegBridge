import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REALM_PATH = ROOT / "infra" / "keycloak" / "regbridge-realm.json"
COMPOSE_PATH = ROOT / "docker-compose.yml"


def _realm() -> dict:
    return json.loads(REALM_PATH.read_text(encoding="utf-8"))


def _frontend_client() -> dict:
    clients = [client for client in _realm()["clients"] if client["clientId"] == "regbridge-frontend"]
    assert len(clients) == 1
    return clients[0]


def test_local_keycloak_realm_contains_no_users_credentials_or_business_roles() -> None:
    realm = _realm()
    serialized = json.dumps(realm).lower()

    assert realm["realm"] == "regbridge"
    assert realm["registrationAllowed"] is True
    assert realm["users"] == []
    assert "credential" not in serialized
    assert "clientsecret" not in serialized
    assert "entrepreneur" not in serialized
    assert "investor" not in serialized
    assert "researcher" not in serialized


def test_local_keycloak_spa_client_is_public_code_flow_with_required_pkce() -> None:
    client = _frontend_client()

    assert client["publicClient"] is True
    assert client["standardFlowEnabled"] is True
    assert client["implicitFlowEnabled"] is False
    assert client["directAccessGrantsEnabled"] is False
    assert client["serviceAccountsEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert client["redirectUris"] == ["http://127.0.0.1:8000/auth/callback/"]
    assert client["webOrigins"] == ["http://127.0.0.1:8000"]
    assert client["attributes"]["post.logout.redirect.uris"] == "http://127.0.0.1:8000/auth/login/"


def test_local_keycloak_access_token_has_explicit_api_audience_and_identity_claims() -> None:
    mappers = {mapper["name"]: mapper for mapper in _frontend_client()["protocolMappers"]}
    audience = mappers["regbridge-api-audience"]["config"]
    email = mappers["regbridge-email-access-token"]["config"]

    assert audience["included.custom.audience"] == "regbridge-api"
    assert audience["access.token.claim"] == "true"
    assert audience["id.token.claim"] == "false"
    assert email["claim.name"] == "email"
    assert email["access.token.claim"] == "true"


def test_compose_uses_pinned_keycloak_image_import_and_environment_credentials() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "quay.io/keycloak/keycloak:26.7.2" in compose
    assert "start-dev --import-realm" in compose
    assert "--hostname=http://127.0.0.1:18080" in compose
    assert '"127.0.0.1:18080:8080"' in compose
    assert "./infra/keycloak/regbridge-realm.json:/opt/keycloak/data/import/regbridge-realm.json:ro" in compose
    assert "KC_BOOTSTRAP_ADMIN_USERNAME: ${KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME:-}" in compose
    assert "KC_BOOTSTRAP_ADMIN_PASSWORD: ${KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD:-}" in compose
