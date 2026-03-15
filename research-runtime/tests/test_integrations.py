import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rand_research import integrations
from rand_research.models import NormalizedItem, SCHEMA_VERSION


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

    def test_load_log_backfills_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'memx.json'
            path.write_text(json.dumps({'entries': [{'entry_id': 'memx-1'}]}), encoding='utf-8')

            payload = integrations._load_log(path, 'entries')

            self.assertEqual(payload['schema_version'], SCHEMA_VERSION)
            self.assertEqual(payload['entries'][0]['schema_version'], SCHEMA_VERSION)


if __name__ == '__main__':
    unittest.main()
