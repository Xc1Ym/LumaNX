"""Release a paused task if its controlling app exits unexpectedly."""
import json
import os
import signal
import subprocess
import sys
import time


def snapshot():
    rows = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,lstart='], text=True)
    return {int(fields[0]): fields[2].strip() for line in rows.splitlines()
            if len(fields := line.split(None, 2)) == 3}


def main():
    app, root, entries = int(sys.argv[1]), int(sys.argv[2]), json.loads(sys.argv[3])
    try:
        os.setsid()
    except OSError:
        pass
    original = snapshot()
    while True:
        current = snapshot()
        if current.get(root) != original.get(root):
            return
        if app not in current or current.get(app) != original.get(app):
            # Queue termination before resuming: the worker's normal handler
            # cancels its registered subprocess groups and preserves checkpoints.
            try:
                os.kill(root, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for entry in reversed(entries):
                if current.get(entry['pid']) == entry['started']:
                    try:
                        os.kill(entry['pid'], signal.SIGCONT)
                    except ProcessLookupError:
                        pass
            return
        time.sleep(0.5)


if __name__ == '__main__':
    main()
