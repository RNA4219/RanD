import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class ResolveComponentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2] / "r-and-d-agent-installer"
        self.script_path = self.repo_root / "scripts" / "Resolve-Components.ps1"
        self.install_root = self.repo_root / ".installed"
        self.example_override = self.repo_root / "config" / "localPathOverrides.json"
        if self.example_override.exists():
            self.example_override.unlink()

    def tearDown(self) -> None:
        if self.example_override.exists():
            self.example_override.unlink()

    def _run_pwsh(self, script: str, env: dict[str, str] | None = None, expect_error: bool = False) -> str:
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=full_env,
            check=not expect_error,
        )
        return (result.stderr if expect_error else result.stdout).strip()

    def test_resolves_env_var_before_codex_dev_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_repo = Path(tmp_dir) / "insight-agent-env"
            local_repo.mkdir()
            script = f"""
. '{self.script_path}'
$component = [pscustomobject]@{{
  name = 'insight-agent'
  layer = 'Insight'
  required = $true
  pathKey = 'CODEX_DEV_ROOT'
  relativePath = 'insight-agent'
  envVar = 'RAND_LOCAL_PATH_INSIGHT_AGENT'
  remoteUrl = 'https://example.com/insight-agent.git'
  installSubdir = 'repos\\insight-agent'
  pinnedCommit = 'abc123'
}}
$result = Resolve-ComponentPath -Component $component -Overrides @{{}}
$result | ConvertTo-Json -Compress
"""
            output = self._run_pwsh(script, {
                "RAND_LOCAL_PATH_INSIGHT_AGENT": str(local_repo),
                "CODEX_DEV_ROOT": str(Path(tmp_dir) / "root"),
            })
            payload = json.loads(output)
            self.assertEqual(payload["resolvedLocalPath"], str(local_repo))
            self.assertEqual(payload["localResolution"], "repo-env")
            self.assertTrue(payload["localAvailable"])

    def test_resolves_path_key_and_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "Codex_dev"
            target = root / "memx-resolver"
            target.mkdir(parents=True)
            script = f"""
. '{self.script_path}'
$component = [pscustomobject]@{{
  name = 'memx-resolver'
  layer = 'Knowledge'
  required = $true
  pathKey = 'CODEX_DEV_ROOT'
  relativePath = 'memx-resolver'
  envVar = 'RAND_LOCAL_PATH_MEMX_RESOLVER'
  remoteUrl = 'https://example.com/memx-resolver.git'
  installSubdir = 'repos\\memx-resolver'
  pinnedCommit = 'def456'
}}
$result = Resolve-ComponentPath -Component $component -Overrides @{{}}
$result | ConvertTo-Json -Compress
"""
            output = self._run_pwsh(script, {"CODEX_DEV_ROOT": str(root)})
            payload = json.loads(output)
            self.assertEqual(payload["resolvedLocalPath"], str(target))
            self.assertEqual(payload["localResolution"], "CODEX_DEV_ROOT")
            self.assertTrue(payload["localAvailable"])

    def test_override_json_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            override_path = Path(tmp_dir) / "tracker-bridge-materials"
            override_path.mkdir()
            self.example_override.write_text(
                json.dumps({"components": {"tracker-bridge-materials": str(override_path)}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            script = f"""
. '{self.script_path}'
$components = Get-ResolvedComponents -RepoRoot '{self.repo_root}' -InstallRootPath '{self.install_root}'
$target = $components | Where-Object {{ $_.name -eq 'tracker-bridge-materials' }}
$target | ConvertTo-Json -Compress
"""
            output = self._run_pwsh(script)
            payload = json.loads(output)
            self.assertEqual(payload["resolvedLocalPath"], str(override_path))
            self.assertEqual(payload["localResolution"], "override-json")

    def test_missing_path_returns_remote_only(self) -> None:
        script = f"""
. '{self.script_path}'
$component = [pscustomobject]@{{
  name = 'open_deep_research'
  layer = 'Research'
  required = $true
  pathKey = 'CODEX_DEV_ROOT'
  relativePath = 'open_deep_research'
  envVar = 'RAND_LOCAL_PATH_OPEN_DEEP_RESEARCH'
  remoteUrl = 'https://example.com/open_deep_research.git'
  installSubdir = 'repos\\open_deep_research'
  pinnedCommit = 'ghi789'
}}
$result = Resolve-ComponentPath -Component $component -Overrides @{{}}
$result | ConvertTo-Json -Compress
"""
        output = self._run_pwsh(script, {"CODEX_DEV_ROOT": "C:/does-not-exist"})
        payload = json.loads(output)
        self.assertEqual(payload["localResolution"], "CODEX_DEV_ROOT")
        self.assertFalse(payload["localAvailable"])

    def test_missing_required_field_raises_error(self) -> None:
        script = f"""
. '{self.script_path}'
$component = [pscustomobject]@{{
  name = 'broken-component'
  layer = 'Broken'
  required = $true
  pathKey = 'CODEX_DEV_ROOT'
  relativePath = 'broken-component'
  envVar = 'RAND_LOCAL_PATH_BROKEN'
  remoteUrl = ''
  installSubdir = 'repos\\broken-component'
  pinnedCommit = 'zzz999'
}}
Resolve-ComponentPath -Component $component -Overrides @{{}} | Out-Null
"""
        error_output = self._run_pwsh(script, expect_error=True)
        self.assertIn("Component schema error", error_output)
        self.assertIn("remoteUrl", error_output)


if __name__ == "__main__":
    unittest.main()
