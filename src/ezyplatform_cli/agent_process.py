"""Bound non-interactive agent probes and clean up their child processes."""
import os
import signal
import subprocess
import tempfile


def stop_probe(proc):
    """Only stop the process tree created for this probe, never the user's agent."""
    if os.name == 'nt':
        for flags in ([], ['/F']):
            try:
                result = subprocess.run(['taskkill', '/PID', str(proc.pid), '/T'] + flags,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=1)
                if result.returncode == 0:
                    break
            except (OSError, subprocess.SubprocessError):
                pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        # A launcher may exit before its descendants; finish cleaning the group.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait()


def probe(argv, timeout):
    # File captures cannot keep communicate() waiting when a launcher leaves a
    # descendant holding stdout/stderr open after the launcher has been killed.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                start_new_session=os.name != 'nt')
        try:
            proc.wait(timeout=timeout)
        except BaseException:
            stop_probe(proc)
            raise
        stdout.seek(0)
        stderr.seek(0)
        return subprocess.CompletedProcess(argv, proc.returncode,
                                           stdout.read().decode('utf-8', errors='replace'),
                                           stderr.read().decode('utf-8', errors='replace'))
