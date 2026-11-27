"""Test guardian retry behavior without sending signals to real processes."""
import importlib.util
import io
import json
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'Worker/task_pause_guardian.py'
SPEC = importlib.util.spec_from_file_location('guardian', SCRIPT)
guardian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guardian)


class PauseGuardianTests(unittest.TestCase):
    def test_eof_retries_failed_release_and_only_signals_recorded_identities(self):
        root = {'token': [0] * 7 + [1]}
        child = {'token': [0] * 7 + [2]}
        calls = []

        def send(identity, sig):
            calls.append((identity, sig))
            if identity == child and sig == signal.SIGCONT and calls.count((child, sig)) == 1:
                raise PermissionError('temporary failure')
            return True

        journal = io.StringIO(json.dumps(root) + '\n' + json.dumps(child) + '\n')
        with patch.object(sys, 'argv', [str(SCRIPT), json.dumps(root)]), patch.object(sys, 'stdin', journal), \
             patch.object(guardian.os, 'setsid'), patch.object(guardian.time, 'sleep'), patch.object(guardian, 'send', send):
            guardian.main()
        self.assertEqual(calls, [(root, signal.SIGTERM), (child, signal.SIGCONT),
                                 (root, signal.SIGCONT), (child, signal.SIGCONT)])

    def test_orderly_completion_disarms_guardian(self):
        root = {'token': [0] * 8}
        journal = io.StringIO(json.dumps(root) + '\ndone\n')
        with patch.object(sys, 'argv', [str(SCRIPT), json.dumps(root)]), patch.object(sys, 'stdin', journal), \
             patch.object(guardian.os, 'setsid'), patch.object(guardian, 'send') as send:
            guardian.main()
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
