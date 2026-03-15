import json
import tempfile
import unittest
from pathlib import Path

from rand_research.models import NormalizedItem, RunMeta
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
            memx_record = {'entry_id': 'memx-1'}
            tracker_event = {'sync_id': 'sync-1'}
            before = {'previous_run_count': 1, 'known_urls': ['https://arxiv.org/abs/0'], 'open_tasks': []}
            after = {'previous_run_count': 2, 'known_urls': ['https://arxiv.org/abs/0', 'https://arxiv.org/abs/1'], 'open_tasks': []}

            artifacts = save_run_outputs(
                run_dir,
                meta,
                items,
                {'mode': 'fallback', 'results': []},
                {'mode': 'fallback', 'results': []},
                task_record,
                memx_record,
                tracker_event,
                before,
                after,
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
            }
            self.assertEqual(set(artifacts.keys()), expected_keys)
            for artifact_path in artifacts.values():
                self.assertTrue(Path(artifact_path).exists())

            report = json.loads((run_dir / 'report.json').read_text(encoding='utf-8'))
            self.assertIn('state_context', report)
            self.assertEqual(report['state_context']['before']['previous_run_count'], 1)
            self.assertEqual(report['state_context']['after']['previous_run_count'], 2)
            self.assertIn('artifacts', report)
            self.assertEqual(set(report['artifacts'].keys()), expected_keys)

            state_context = json.loads((run_dir / 'state_context.json').read_text(encoding='utf-8'))
            self.assertEqual(state_context['before']['known_urls'], ['https://arxiv.org/abs/0'])
            self.assertEqual(state_context['after']['known_urls'], ['https://arxiv.org/abs/0', 'https://arxiv.org/abs/1'])


if __name__ == '__main__':
    unittest.main()
