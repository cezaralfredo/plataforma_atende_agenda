from pathlib import Path


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


def test_readme_documents_authenticated_api_and_current_asaas_urls():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Authorization: Bearer" in readme
    assert "https://api-sandbox.asaas.com/v3" in readme
    assert "/ready" in readme
    assert "buscar_cliente_por_telefone" in readme
