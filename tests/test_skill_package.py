import os
import shutil
import subprocess
import tempfile
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

    def test_installer_copies_to_existing_agent_dirs_and_skips_missing_ones(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-skill-install-"))
        try:
            (tmpdir / ".codex" / "skills").mkdir(parents=True)
            (tmpdir / ".claude" / "skills").mkdir(parents=True)
            # .antigravity nao existe -> deve ser pulado

            env = os.environ.copy()
            env["USERPROFILE"] = str(tmpdir)
            resultado = subprocess.run(
                ["python", str(ROOT / "scripts" / "instalar_skill.py")],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            saida = resultado.stdout

            self.assertIn("instalou Codex", saida)
            self.assertIn("instalou Claude Code", saida)
            self.assertIn("pulou Antigravity", saida)
            self.assertTrue((tmpdir / ".codex" / "skills" / "central-compras" / "SKILL.md").exists())
            self.assertTrue((tmpdir / ".claude" / "skills" / "central-compras" / "SKILL.md").exists())
            self.assertFalse((tmpdir / ".antigravity").exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
