from app.config.deployment import validate_deployment_config


def complete_values() -> dict[str, str]:
    return {
        "CLOUDBASE_ENV_ID_DEMO": "demo-env-placeholder",
        "CLOUDBASE_ENV_ID_AUTHORIZED": "authorized-env-placeholder",
        "DEMO_NAMESPACE": "demo-xinyu-v2",
        "AUTHORIZED_NAMESPACE": "authorized-xinyu-v2",
        "ADMIN_WEB_ORIGIN_DEMO": "https://demo.example.invalid",
        "ADMIN_WEB_ORIGIN_AUTHORIZED": "https://authorized.example.invalid",
    }


def test_deployment_config_requires_two_distinct_isolated_environments() -> None:
    values = complete_values()
    values["CLOUDBASE_ENV_ID_AUTHORIZED"] = values["CLOUDBASE_ENV_ID_DEMO"]
    values["AUTHORIZED_NAMESPACE"] = values["DEMO_NAMESPACE"]

    result = validate_deployment_config(values)

    assert not result.valid
    assert "CloudBase environment IDs must differ" in result.errors
    assert "database namespaces must differ" in result.errors


def test_deployment_config_rejects_non_https_or_path_origins() -> None:
    values = complete_values()
    values["ADMIN_WEB_ORIGIN_DEMO"] = "http://demo.example.invalid/app"

    result = validate_deployment_config(values)

    assert "ADMIN_WEB_ORIGIN_DEMO must be an HTTPS origin without a path" in result.errors


def test_deployment_config_does_not_echo_secret_like_values() -> None:
    values = complete_values()
    values["CLOUDBASE_API_KEY_DEMO"] = "do-not-print-this"
    values["DEMO_NAMESPACE"] = ""

    result = validate_deployment_config(values)

    assert not result.valid
    assert all("do-not-print-this" not in error for error in result.errors)
