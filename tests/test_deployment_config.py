from pathlib import Path

import yaml


def _yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _step(job: dict, name: str) -> dict:
    return next(step for step in job["steps"] if step.get("name") == name)


def _env_example() -> dict[str, str]:
    values = {}
    for raw_line in Path(".env.prod.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_only_one_workflow_publishes_latest():
    workflows = Path(".github/workflows").glob("*.yml")
    publishers = [
        path for path in workflows if "build-push-action" in path.read_text()
    ]
    assert [path.name for path in publishers] == ["ci-cd.yml"]


def test_ci_type_check_is_not_advisory():
    workflow = Path(".github/workflows/ci-cd.yml").read_text()
    assert "mypy app/ --ignore-missing-imports || true" not in workflow
    assert "mypy app/ --ignore-missing-imports" in workflow


def test_domain_example_produces_single_api_prefix():
    assert _env_example()["DOMAIN"] == "seudominio.com"


def test_registry_repository_example_is_complete():
    assert _env_example()["GITHUB_REPOSITORY"] == (
        "cezaralfredo/plataforma_atende_agenda"
    )


def test_runtime_entrypoint_does_not_call_removed_test_seed():
    assert "python -m tests.seed" not in Path("entrypoint.sh").read_text(
        encoding="utf-8"
    )


def test_runtime_entrypoint_uses_configured_database_for_migrations():
    entrypoint = Path("entrypoint.sh").read_text(encoding="utf-8")
    assert "pg_isready -h postgres" not in entrypoint
    assert "python /app/scripts/run_migrations.py" in entrypoint
    assert "DATABASE_URL" in entrypoint.split("for secret in", 1)[1].split("; do", 1)[0]


def test_readme_documents_authenticated_api_and_current_asaas_urls():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Authorization: Bearer" in readme
    assert "https://api-sandbox.asaas.com/v3" in readme
    assert "/ready" in readme
    assert "buscar_cliente_por_telefone" in readme


def test_ci_uses_psycopg3_urls_for_migrations_and_tests():
    jobs = _yaml(".github/workflows/ci-cd.yml")["jobs"]
    migration = _step(jobs["test"], "Run Alembic migrations")
    tests = _step(jobs["test"], "Run tests with coverage")
    expected = "postgresql+psycopg://test:test@localhost:5432/test_db"
    assert migration["env"]["DATABASE_URL"] == expected
    assert tests["env"]["DATABASE_URL"] == expected
    assert tests["env"]["TEST_DATABASE_URL"] == expected


def test_pull_requests_build_both_images_without_publishing():
    jobs = _yaml(".github/workflows/ci-cd.yml")["jobs"]
    validation = jobs["validate-images"]
    assert validation["needs"] == "test"
    assert "pull_request" in validation["if"]
    builds = [
        step
        for step in validation["steps"]
        if step.get("uses", "").startswith("docker/build-push-action@")
    ]
    assert len(builds) == 2
    assert {step["with"]["file"] for step in builds} == {
        "./Dockerfile",
        "./Dockerfile.backup",
    }
    assert all(step["with"]["push"] is False for step in builds)


def test_ci_does_not_claim_an_automatic_production_deploy():
    jobs = _yaml(".github/workflows/ci-cd.yml")["jobs"]
    assert "deploy" not in jobs
    assert jobs["build"]["needs"] == "test"


def test_portainer_neon_stack_has_only_the_external_database_api():
    compose = _yaml("docker-compose.portainer-neon.yml")
    assert set(compose["services"]) == {"api", "mcp-gateway"}
    assert "volumes" not in compose


def test_portainer_neon_stack_requires_traceable_image_and_database_config():
    compose = _yaml("docker-compose.portainer-neon.yml")
    api = compose["services"]["api"]
    environment = api["environment"]
    assert "${IMAGE_TAG:?Defina IMAGE_TAG no Portainer}" in api["image"]
    assert environment["DATABASE_URL"] == (
        "${DATABASE_URL:?Defina DATABASE_URL no Portainer}"
    )
    assert environment["APP_TIMEZONE"] == "${APP_TIMEZONE:-America/Sao_Paulo}"
    assert environment["DEBUG"] == "false"

    source = Path("docker-compose.portainer-neon.yml").read_text(encoding="utf-8")
    assert "postgresql://" not in source
    assert "postgresql+psycopg://" not in source
    assert ":latest" not in api["image"]


def test_portainer_neon_stack_uses_only_the_existing_proxy_network():
    compose = _yaml("docker-compose.portainer-neon.yml")
    api = compose["services"]["api"]
    assert set(api["networks"]) == {"npm"}
    assert api["networks"]["npm"]["aliases"] == ["agenda-api"]
    assert "ports" not in api
    assert compose["networks"]["npm"] == {
        "external": True,
        "name": "${NPM_NETWORK:-nginx-proxy_default}",
    }


def test_shipped_compose_defaults_use_the_current_asaas_production_endpoint():
    current_endpoint = "https://api.asaas.com/v3"
    defaults = {}
    for path in sorted(Path(".").glob("docker-compose*.yml")):
        environment = _yaml(str(path)).get("services", {}).get("api", {}).get(
            "environment", {}
        )
        if isinstance(environment, dict):
            value = environment.get("ASAAS_BASE_URL")
            if isinstance(value, str) and ":-" in value:
                defaults[path.name] = value.removesuffix("}").split(":-", 1)[1]

    assert defaults == {
        "docker-compose.nginx.yml": current_endpoint,
        "docker-compose.portainer-neon.yml": current_endpoint,
        "docker-compose.portainer-npm.yml": current_endpoint,
    }
