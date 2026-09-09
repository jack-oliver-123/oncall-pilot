from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/compose.yaml"


class LocalInfrastructureTests(unittest.TestCase):
    def test_compose_services_versions_and_no_interpolation(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        services = text.split("services:\n", 1)[1].split("\nvolumes:", 1)[0]
        self.assertEqual(set(re.findall(r"^  ([a-z]+):$", services, re.M)),
                         {"alertmanager", "etcd", "minio", "milvus", "attu"})
        for image in ("quay.io/coreos/etcd:v3.5.18",
                      "minio/minio:RELEASE.2024-12-18T13-15-44Z",
                      "milvusdb/milvus:v3.0-beta", "zilliz/attu:v2.5.12",
                      "prom/alertmanager:v0.28.1"):
            self.assertIn("image: " + image, text)
        self.assertEqual(text.count("healthcheck:"), 5)
        for forbidden in ("${", "env_file", "build:", "backend:", "frontend:",
                          "cls-mcp-server", "appImage", "log-upload", "sop-seed"):
            self.assertNotIn(forbidden, text)

    def test_no_legacy_assets_or_image_config(self) -> None:
        paths = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, text=True).splitlines()
        for name in paths:
            path = Path(name)
            self.assertFalse(path.name.startswith("Dockerfile"), name)
            self.assertNotEqual(path.name, "project.compose.json")
        for name in ("project.template.json", "user.project.template.json"):
            text = (ROOT / "config" / name).read_text(encoding="utf-8")
            self.assertNotIn("docker", json.loads(text))
            for legacy in ("appImageTag", "clsMcpServerVersion", "milvusImage"):
                self.assertNotIn(legacy, text)

    @unittest.skipUnless(shutil.which("docker"), "docker CLI 不可用；需单独执行 Compose 门禁")
    def test_docker_compose_config_dependencies_mounts_and_ports(self) -> None:
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE), "config", "--format", "json"],
            capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        services = config["services"]
        self.assertEqual(set(services), {"alertmanager", "etcd", "minio", "milvus", "attu"})
        self.assertEqual(services["milvus"]["command"], ["milvus", "run", "standalone"])
        for parent, child in (("milvus", "etcd"), ("milvus", "minio"), ("attu", "milvus")):
            self.assertEqual(services[parent]["depends_on"][child]["condition"], "service_healthy")
        for name in ("alertmanager", "etcd", "minio", "milvus"):
            self.assertTrue(any(v["type"] == "volume" and v["source"] in config["volumes"]
                                for v in services[name]["volumes"]))
        for service in services.values():
            self.assertTrue(service["healthcheck"]["test"])
            for port in service.get("ports", []):
                self.assertEqual(port["host_ip"], "127.0.0.1")
        self.assertNotIn("ports", services["minio"])
        self.assertNotIn("ports", services["etcd"])
        alert = services["alertmanager"]
        self.assertTrue(any(v["type"] == "bind" and v["read_only"] for v in alert["volumes"]))
        self.assertTrue(any(str(p["published"]) == "9093" for p in alert["ports"]))


if __name__ == "__main__":
    unittest.main()
