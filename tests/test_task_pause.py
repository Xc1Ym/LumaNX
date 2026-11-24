"""A paused worker must not remain frozen after its controlling app dies."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'Worker/task_pause_guardian.py'


class PauseGuardianTests(unittest.TestCase):
    def test_app_exit_releases_only_recorded_worker(self):
        app = subprocess.Popen(['/bin/sleep', '30'])
        root = subprocess.Popen(['/bin/sleep', '30'])
        other = subprocess.Popen(['/bin/sleep', '30'])
        guardian = None
        try:
            spec = importlib.util.spec_from_file_location('guardian', SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            entries = [{'pid': root.pid, 'parent': os.getpid(), 'started': module.snapshot()[root.pid]}]
            os.kill(root.pid, signal.SIGSTOP)
            guardian = subprocess.Popen([sys.executable, '-B', '-I', str(SCRIPT), str(app.pid), str(root.pid), json.dumps(entries)])
            time.sleep(0.3)
            self.assertIsNone(root.poll())
            app.terminate()
            app.wait(timeout=3)
            self.assertEqual(guardian.wait(timeout=5), 0)
            self.assertEqual(root.wait(timeout=3), -signal.SIGTERM)
            self.assertIsNone(other.poll())
        finally:
            for process in (guardian, app, root, other):
                if process is not None and process.poll() is None:
                    if process is root:
                        os.kill(root.pid, signal.SIGCONT)
                    process.kill()
                    process.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
