import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rand_research import integrations
from rand_research.models import NormalizedItem, SCHEMA_VERSION
from rand_research import sync_writers


class IntegrationsTests(unittest.TestCase):
    def test_run_insight_marks_degraded_when_nested_run_fails(self) -> None:
        fake_insight = Mock()
        fake_insight.run.return_value = {
            'run': {'request_id': 'paper-1', 'status': 'failed'},
            'insights': [],
        }
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
        )

        with patch.object(integrations, 'ensure_repo_paths'), patch.object(integrations, 'load_env_from_peer_repos'), patch(
            'rand_research.integrations.importlib.import_module', return_value=fake_insight
        ):
            payload = integrations.run_insight([item])

        self.assertEqual(payload['status'], 'degraded')
        self.assertEqual(payload['results'][0]['run']['status'], 'failed')
        self.assertIn('paper-1:failed', payload['error'])

    def test_run_insight_prefers_external_api(self) -> None:
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
        )
        api_response = {
            'status': 'ok',
            'results': [{'run': {'request_id': 'paper-1', 'status': 'ok'}}],
        }

        with patch.dict('os.environ', {'RAND_INSIGHT_API_URL': 'https://api.example.test/insight'}, clear=False), patch.object(
            integrations, 'ensure_repo_paths'
        ), patch.object(integrations, 'load_env_from_peer_repos'), patch.object(
            integrations, '_post_json', return_value=api_response
        ):
            payload = integrations.run_insight([item])

        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['mode'], 'insight-api')
        self.assertEqual(payload['results'][0]['run']['request_id'], 'paper-1')

    def test_run_insight_falls_back_to_subagent_when_api_fails(self) -> None:
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
        )
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({'status': 'ok', 'results': [{'run': {'request_id': 'paper-1', 'status': 'ok'}}]}),
            stderr='',
        )

        with patch.dict(
            'os.environ',
            {
                'RAND_INSIGHT_API_URL': 'https://api.example.test/insight',
                'RAND_INSIGHT_SUBAGENT_CMD': 'codex-subagent insight',
            },
            clear=False,
        ), patch.object(integrations, 'ensure_repo_paths'), patch.object(integrations, 'load_env_from_peer_repos'), patch.object(
            integrations, '_post_json', side_effect=RuntimeError('network down')
        ), patch(
            'rand_research.integrations.subprocess.run', return_value=completed
        ) as run_mock:
            payload = integrations.run_insight([item])

        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['mode'], 'insight-subagent')
        self.assertIn('api_failed', json.loads(run_mock.call_args.kwargs['input'])['fallback_cause'])

    def test_run_gate_marks_degraded_when_nested_run_fails(self) -> None:
        fake_gate = Mock()
        fake_gate.GateRequest.side_effect = lambda **kwargs: kwargs
        fake_gate.PocSpec.side_effect = lambda **kwargs: kwargs
        fake_gate.EvidenceBundle.side_effect = lambda **kwargs: kwargs
        fake_gate.run_gate.return_value = SimpleNamespace(
            model_dump=lambda: {
                'run': {'request_id': 'paper-1', 'status': 'failed'},
                'decision': {'verdict': 'hold'},
                'next_step': {'recommended_action': 'gather_evidence'},
            }
        )
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
            high_priority=True,
        )

        with patch.object(integrations, 'ensure_repo_paths'), patch.object(integrations, 'load_env_from_peer_repos'), patch(
            'rand_research.integrations.importlib.import_module', return_value=fake_gate
        ):
            payload = integrations.run_gate([item], {'sources': 'ok', 'state': 'ok', 'report': 'ok', 'insight': 'ok'})

        self.assertEqual(payload['status'], 'degraded')
        self.assertEqual(payload['results'][0]['run']['status'], 'failed')
        self.assertIn('paper-1:failed', payload['error'])

    def test_run_gate_prefers_external_api(self) -> None:
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
            high_priority=True,
        )
        api_response = {
            'status': 'ok',
            'results': [{'run': {'request_id': 'paper-1', 'status': 'ok'}, 'decision': {'verdict': 'go'}}],
        }

        with patch.dict('os.environ', {'RAND_GATE_API_URL': 'https://api.example.test/gate'}, clear=False), patch.object(
            integrations, 'ensure_repo_paths'
        ), patch.object(integrations, 'load_env_from_peer_repos'), patch.object(
            integrations, '_post_json', return_value=api_response
        ):
            payload = integrations.run_gate([item], {'sources': 'ok', 'state': 'ok', 'report': 'ok', 'insight': 'ok'})

        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['mode'], 'gate-api')
        self.assertEqual(payload['results'][0]['decision']['verdict'], 'go')

    def test_run_gate_falls_back_to_subagent_when_api_fails(self) -> None:
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
            high_priority=True,
        )
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                'status': 'ok',
                'results': [{'run': {'request_id': 'paper-1', 'status': 'ok'}, 'decision': {'verdict': 'hold'}}],
            }),
            stderr='',
        )

        with patch.dict(
            'os.environ',
            {
                'RAND_GATE_API_URL': 'https://api.example.test/gate',
                'RAND_GATE_SUBAGENT_CMD': 'codex-subagent gate',
            },
            clear=False,
        ), patch.object(integrations, 'ensure_repo_paths'), patch.object(integrations, 'load_env_from_peer_repos'), patch.object(
            integrations, '_post_json', side_effect=RuntimeError('network down')
        ), patch(
            'rand_research.integrations.subprocess.run', return_value=completed
        ) as run_mock:
            payload = integrations.run_gate([item], {'sources': 'ok', 'state': 'ok', 'report': 'ok', 'insight': 'ok'})

        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['mode'], 'gate-subagent')
        self.assertIn('api_failed', json.loads(run_mock.call_args.kwargs['input'])['fallback_cause'])

    def test_load_log_backfills_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'memx.json'
            path.write_text(json.dumps({'entries': [{'entry_id': 'memx-1'}]}), encoding='utf-8')

            payload = sync_writers._load_log(path, 'entries')

            self.assertEqual(payload['schema_version'], SCHEMA_VERSION)
            self.assertEqual(payload['entries'][0]['schema_version'], SCHEMA_VERSION)

    def test_sync_writers_use_common_atomic_write(self) -> None:
        item = NormalizedItem(
            id='paper-1',
            kind='paper',
            source_name='arxiv',
            url='https://example.com/paper-1',
            title='Example Paper',
            high_priority=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch('rand_research.sync_writers.atomic_write_text') as atomic_write:
                memx_entry = integrations.write_memx_journal(root / 'memx.json', 'run-1', 'paper_arxiv_ai_recent', [item], {})
                tracker_event = integrations.write_tracker_sync(
                    root / 'tracker.json',
                    'run-1',
                    'paper_arxiv_ai_recent',
                    [item],
                    {'results': [{'run': {'request_id': 'paper-1'}, 'decision': {'verdict': 'go'}, 'next_step': {'recommended_action': 'probe'}}]},
                )

            self.assertEqual(memx_entry['entry_id'], 'memx-run-1')
            self.assertEqual(tracker_event['sync_id'], 'sync-run-1')
            self.assertEqual(tracker_event['dry_run_issues'][0]['status'], 'dry_run')
            self.assertIn('gate:go', tracker_event['dry_run_issues'][0]['labels'])
            self.assertEqual(atomic_write.call_count, 2)
            self.assertEqual(atomic_write.call_args_list[0].args[0], root / 'memx.json')
            self.assertEqual(atomic_write.call_args_list[1].args[0], root / 'tracker.json')


if __name__ == '__main__':
    unittest.main()
