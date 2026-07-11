import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.artifact_schema import ARTIFACT_SCHEMA_VERSION, validate_artifact_path
from rand_research.io_utils import atomic_write_text as real_atomic_write_text
from rand_research.models import SCHEMA_VERSION, NormalizedItem, RunMeta
from rand_research.reports import save_run_outputs


class ReportsTests(unittest.TestCase):
    def test_save_run_outputs_writes_state_context_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / 'run-001'
            meta = RunMeta(
                run_id='run-001',
                preset='paper_arxiv_ai_recent',
                started_at='2026-03-15T00:00:00Z',
                finished_at='2026-03-15T00:05:00Z',
                prompt_template='paper_research_prompt.md',
                max_items=1,
                save_dir=str(run_dir),
                target_sites=['https://arxiv.org/list/cs.AI/recent'],
            )
            items = [
                NormalizedItem(
                    id='arxiv-1',
                    kind='paper',
                    source_name='arxiv_cs_ai_recent',
                    url='https://arxiv.org/abs/1',
                    title='Example Paper',
                    priority=8,
                    high_priority=True,
                    metadata={'seen_before': False},
                )
            ]
            task_record = {'task_id': 'task-1', 'status': 'done'}
            memx_record = {'entry_id': 'memx-1', 'status': 'ok'}
            tracker_event = {'sync_id': 'sync-1', 'status': 'ok'}
            before = {'previous_run_count': 1, 'known_urls': ['https://arxiv.org/abs/0'], 'open_tasks': []}
            after = {'previous_run_count': 2, 'known_urls': ['https://arxiv.org/abs/0', 'https://arxiv.org/abs/1'], 'open_tasks': []}

            artifacts, report = save_run_outputs(
                run_dir,
                meta,
                items,
                {'schema_version': SCHEMA_VERSION, 'status': 'ok', 'mode': 'fallback', 'results': []},
                {
                    'schema_version': SCHEMA_VERSION,
                    'status': 'degraded',
                    'mode': 'fallback',
                    'results': [{'decision': {'verdict': 'hold'}}],
                },
                task_record,
                memx_record,
                tracker_event,
                before,
                after,
                'degraded',
                ['gate_failed'],
                {'sources': 'ok', 'state': 'ok', 'report': 'ok', 'insight': 'ok', 'gate': 'degraded', 'memx': 'ok', 'tracker': 'ok'},
            )

            expected_keys = {
                'report_md',
                'report_json',
                'insight_json',
                'gate_json',
                'meta_json',
                'tracker_sync_json',
                'memx_journal_json',
                'state_context_json',
                'manifest_json',
            }
            self.assertEqual(set(artifacts.keys()), expected_keys)
            self.assertEqual(report['schema_version'], ARTIFACT_SCHEMA_VERSION)
            self.assertEqual(report['status'], 'degraded')
            self.assertEqual(report['status_reason'], ['gate_failed'])
            self.assertEqual(report['operational_summary']['item_count'], 1)
            self.assertEqual(report['operational_summary']['new_item_count'], 1)
            self.assertEqual(report['operational_summary']['high_priority_count'], 1)
            self.assertEqual(report['operational_summary']['dependency_status_counts']['degraded'], 1)
            self.assertEqual(report['operational_summary']['gate_verdict_counts']['hold'], 1)
            for artifact_path in artifacts.values():
                self.assertTrue(Path(artifact_path).exists())
            manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['status'], 'committed')
            self.assertEqual(len(manifest['artifacts']), len(expected_keys) - 1)
            for entry in manifest['artifacts']:
                self.assertEqual(len(entry['sha256']), 64)
                self.assertGreater(entry['size_bytes'], 0)

            report_json = json.loads((run_dir / 'report.json').read_text(encoding='utf-8'))
            self.assertIn('state_context', report_json)
            self.assertEqual(report_json['state_context']['before']['previous_run_count'], 1)
            self.assertEqual(report_json['state_context']['after']['previous_run_count'], 2)
            self.assertIn('artifacts', report_json)
            self.assertIn('operational_summary', report_json)
            self.assertEqual(set(report_json['artifacts'].keys()), expected_keys)
            self.assertEqual(report_json['dependency_health']['gate'], 'degraded')
            self.assertEqual(report_json['dependency_health']['report'], 'ok')

            state_context = json.loads((run_dir / 'state_context.json').read_text(encoding='utf-8'))
            self.assertEqual(state_context['schema_version'], ARTIFACT_SCHEMA_VERSION)
            self.assertEqual(state_context['before']['known_urls'], ['https://arxiv.org/abs/0'])
            self.assertEqual(state_context['after']['known_urls'], ['https://arxiv.org/abs/0', 'https://arxiv.org/abs/1'])

            memx_json = json.loads((run_dir / 'memx_journal.json').read_text(encoding='utf-8'))
            self.assertEqual(memx_json['schema_version'], ARTIFACT_SCHEMA_VERSION)
            self.assertEqual(memx_json['entries'][0]['schema_version'], SCHEMA_VERSION)
            self.assertEqual(memx_json['entries'][0]['entry_id'], 'memx-1')

            tracker_json = json.loads((run_dir / 'tracker_sync.json').read_text(encoding='utf-8'))
            self.assertEqual(tracker_json['schema_version'], ARTIFACT_SCHEMA_VERSION)
            self.assertEqual(tracker_json['events'][0]['schema_version'], SCHEMA_VERSION)
            self.assertEqual(tracker_json['events'][0]['sync_id'], 'sync-1')

    def test_save_run_outputs_writes_extra_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / 'run-002'
            meta = RunMeta(
                run_id='run-002',
                preset='kano_requirements_offline_eval',
                started_at='2026-05-26T00:00:00Z',
                finished_at='2026-05-26T00:05:00Z',
                max_items=0,
                save_dir=str(run_dir),
            )

            artifacts, report = save_run_outputs(
                run_dir,
                meta,
                [],
                {'schema_version': SCHEMA_VERSION, 'status': 'ok', 'mode': 'disabled', 'results': []},
                {'schema_version': SCHEMA_VERSION, 'status': 'ok', 'mode': 'disabled', 'results': []},
                {'task_id': 'task-2', 'status': 'done'},
                {'entry_id': 'memx-2', 'status': 'ok'},
                {'sync_id': 'sync-2', 'status': 'ok'},
                {},
                {},
                'ok',
                [],
                {'sources': 'ok', 'state': 'ok', 'report': 'ok', 'insight': 'ok', 'gate': 'ok', 'memx': 'ok', 'tracker': 'ok'},
                {
                    'kano': {'schema_version': SCHEMA_VERSION, 'mode': 'kano'},
                    'requirements_packet': {
                        'schema_version': SCHEMA_VERSION,
                        'packet_id': 'rand:packet:run-002',
                        'qeg_policy_hash_ref': 'qeg:policyHash:proposal',
                        'requirements': [],
                    },
                },
            )

            self.assertIn('kano_json', artifacts)
            self.assertIn('requirements_packet_json', artifacts)
            self.assertTrue((run_dir / 'kano.json').exists())
            self.assertTrue((run_dir / 'requirements_packet.json').exists())
            self.assertEqual(report['kano']['mode'], 'kano')


    def test_save_run_outputs_never_publishes_partial_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for fail_at in range(1, 10):
                run_dir = root / f"run-fail-{fail_at}"
                meta = RunMeta(
                    run_id=f"run-fail-{fail_at}",
                    preset="paper_arxiv_ai_recent",
                    started_at="2026-07-11T00:00:00Z",
                    finished_at="2026-07-11T00:01:00Z",
                    save_dir=str(run_dir),
                )
                calls = 0

                def failing_write(
                    path: Path,
                    content: str,
                    encoding: str = "utf-8",
                    expected_fail_at: int = fail_at,
                ) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == expected_fail_at:
                        raise OSError(f"injected write failure {expected_fail_at}")
                    real_atomic_write_text(path, content, encoding)

                with patch("rand_research.reports.atomic_write_text", side_effect=failing_write):
                    with self.assertRaises(OSError):
                        save_run_outputs(
                            run_dir,
                            meta,
                            [],
                            {"schema_version": SCHEMA_VERSION, "status": "ok", "results": []},
                            {"schema_version": SCHEMA_VERSION, "status": "ok", "results": []},
                            {"task_id": "task-fail", "status": "running"},
                            {"entry_id": "memx-fail", "status": "ok"},
                            {"sync_id": "sync-fail", "status": "ok"},
                            {},
                            {},
                            "ok",
                            [],
                            {"sources": "ok", "state": "ok", "report": "ok"},
                        )

                self.assertFalse(run_dir.exists())
                self.assertEqual(list(root.glob(f".staging-{run_dir.name}-*")), [])

    def test_manifest_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run-checksum"
            meta = RunMeta(
                run_id="run-checksum",
                preset="preset",
                started_at="2026-07-11T00:00:00Z",
                finished_at="2026-07-11T00:01:00Z",
                save_dir=str(run_dir),
            )
            save_run_outputs(
                run_dir,
                meta,
                [],
                {"schema_version": SCHEMA_VERSION, "status": "ok", "results": []},
                {"schema_version": SCHEMA_VERSION, "status": "ok", "results": []},
                {"task_id": "task", "status": "done"},
                {"entry_id": "memx", "status": "ok"},
                {"sync_id": "sync", "status": "ok"},
                {},
                {},
                "ok",
                [],
                {"sources": "ok", "state": "ok", "report": "ok"},
            )
            self.assertEqual(validate_artifact_path(run_dir / "manifest.json")["status"], "ok")
            (run_dir / "report.json").write_text("{}", encoding="utf-8")
            validation = validate_artifact_path(run_dir / "manifest.json")
            self.assertEqual(validation["status"], "failed")
            self.assertIn("sha256 mismatch", " ".join(item["message"] for item in validation["issues"]))


if __name__ == "__main__":
    unittest.main()