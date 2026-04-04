from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_nginx_template_covers_public_routes() -> None:
    content = (REPO_ROOT / "deploy/nginx/bingwall.conf").read_text(encoding="utf-8")

    assert "upstream bingwall_app" in content
    assert "server 127.0.0.1:8000;" in content
    assert "location /api/" in content
    assert "location / {" in content
    assert "location /images/" in content
    assert "location /assets/" in content
    assert "proxy_pass http://bingwall_app;" in content
    assert "alias /var/lib/bingwall/images/public/;" in content


def test_systemd_service_uses_managed_env_and_restart_policy() -> None:
    content = (REPO_ROOT / "deploy/systemd/bingwall-api.service").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/bingwall/bingwall.env" in content
    assert "Environment=PATH=/usr/local/bin:/usr/bin:/bin" in content
    assert "ExecStart=/usr/bin/env uv run --no-sync python -m uvicorn" in content
    assert "--host ${BINGWALL_APP_HOST} --port ${BINGWALL_APP_PORT}" in content
    assert "WorkingDirectory=/opt/bingwall/app" in content
    assert "SupplementaryGroups=" not in content
    assert "Restart=on-failure" in content
    assert "RemoveIPC=true" in content
    assert "PrivateDevices=true" in content
    assert "ProtectSystem=strict" in content
    assert "ProtectProc=invisible" in content
    assert "CapabilityBoundingSet=" in content
    assert "RestrictNamespaces=true" in content
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in content
    assert "SystemCallArchitectures=native" in content
    assert "ReadWritePaths=/var/lib/bingwall /var/log/bingwall /etc/bingwall" in content


def test_tmpfiles_template_defines_public_image_permissions() -> None:
    content = (REPO_ROOT / "deploy/systemd/bingwall.tmpfiles.conf").read_text(encoding="utf-8")

    assert "d /var/lib/bingwall/images/public 2750 bingwall www-data -" in content
    assert "d /var/lib/bingwall/images/tmp 0750 bingwall bingwall -" in content
    assert "d /var/log/bingwall 0750 bingwall bingwall -" in content
