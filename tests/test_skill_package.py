import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class SkillPackageTest(unittest.TestCase):
    def test_central_compras_skill_has_valid_metadata_and_no_todos(self):
        skill = ROOT / "skills" / "central-compras" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        _, frontmatter, body = text.split("---", 2)
        meta = yaml.safe_load(frontmatter)

        self.assertEqual(meta["name"], "central-compras")
        self.assertIn("Central de Compras", meta["description"])
        self.assertIn("references/fluxo.md", body)
        self.assertNotIn("TODO", text)

    def test_central_compras_skill_reference_exists(self):
        reference = ROOT / "skills" / "central-compras" / "references" / "fluxo.md"
        text = reference.read_text(encoding="utf-8")

        self.assertIn("promover-cotacao", text)
        self.assertIn("registrar-licao", text)


if __name__ == "__main__":
    unittest.main()
