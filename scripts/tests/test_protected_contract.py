"""受保护 path 默认关闭，安全声明缺失或漂移必须阻断生成。"""

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("generate_contracts", ROOT / "scripts/generate_contracts.py")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class ProtectedContractTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(generator.SOURCE.read_text(encoding="utf-8"))

    def test_missing_security_or_response_is_rejected(self):
        for key in ["security", "401", "403"]:
            with self.subTest(key=key):
                doc = deepcopy(self.doc)
                operation = doc["paths"]["/auth/me"]["get"]
                (operation if key == "security" else operation["responses"]).pop(key)
                with self.assertRaisesRegex(ValueError, "受保护操作"):
                    generator.render(doc)

    def test_new_operation_defaults_to_protected(self):
        op = deepcopy(self.doc["paths"]["/health"]["get"])
        op["operationId"] = "futureResource"
        self.doc["paths"]["/future"] = {"get": op}
        with self.assertRaisesRegex(ValueError, "受保护操作"):
            generator.render(self.doc)
        op["security"] = deepcopy(self.doc["x-protected-operation"]["security"])
        op["responses"].update(self.doc["x-protected-operation"]["responses"])
        generator.render(self.doc)

    def test_template_and_response_cannot_weaken_auth(self):
        for mutation in ["security", "response", "public", "inline"]:
            with self.subTest(mutation=mutation):
                doc = deepcopy(self.doc)
                if mutation == "security":
                    doc["x-protected-operation"]["security"] = []
                elif mutation == "response":
                    doc["components"]["responses"]["Forbidden"]["content"]["application/json"]["schema"] = {
                        "$ref": "#/components/schemas/ApiSuccess",
                    }
                elif mutation == "public":
                    doc["x-public-operations"].append("notRegistered")
                else:
                    doc["paths"]["/auth/me"]["get"]["responses"]["403"] = doc["components"]["responses"]["Forbidden"]
                with self.assertRaises(ValueError):
                    generator.render(doc)

    def test_duplicate_public_operation_id_is_rejected(self):
        self.doc["paths"]["/copied-health"] = deepcopy(self.doc["paths"]["/health"])
        with self.assertRaisesRegex(ValueError, "operationId 必须唯一"):
            generator.render(self.doc)


if __name__ == "__main__":
    unittest.main()
