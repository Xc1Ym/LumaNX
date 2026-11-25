"""Cancel and release an abandoned paused task using launcher-provided audit tokens."""
import ctypes
import errno
import json
import os
import signal
import sys
import time

Token = ctypes.c_uint32 * 8
kernel_signal = ctypes.CDLL(None, use_errno=True).proc_signal_with_audittoken
kernel_signal.argtypes = [ctypes.POINTER(Token), ctypes.c_int]
kernel_signal.restype = ctypes.c_int


def send(identity, action):
    token = Token(*identity['token'])
    if kernel_signal(ctypes.byref(token), action) == 0:
        return True
    error = ctypes.get_errno()
    if error == errno.ESRCH:
        return False
    raise OSError(error, os.strerror(error))


def main():
    root = json.loads(sys.argv[1])
    try:
        os.setsid()
    except OSError:
        pass
    # The launcher records a token before attempting SIGSTOP. Closing its
    # pipe without the completion record means the app lost control.
    pending = []
    for line in sys.stdin:
        if line == 'done\n':
            return
        pending.append(json.loads(line))
    if not pending:
        return

    terminate = True
    while pending or terminate:
        if terminate:
            try:
                send(root, signal.SIGTERM)
                terminate = False
            except OSError:
                pass
        failed = []
        for identity in reversed(pending):
            try:
                send(identity, signal.SIGCONT)
            except OSError:
                failed.append(identity)
        pending = list(reversed(failed))
        if pending or terminate:
            time.sleep(.5)


if __name__ == '__main__':
    main()
