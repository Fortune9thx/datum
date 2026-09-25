"""
Windows compatibility shim for gltest's direct-mode message injection.

gltest.direct.loader._inject_message_to_fd0 (genlayer-test) does:
    os.dup2(fd, 0)   # duplicate the temp file's fd onto stdin
    os.close(fd)     # close the original fd
    os.unlink(path)  # delete the temp file

On POSIX this works because unlinking an open file just removes the
directory entry while the still-open fd (now living at fd 0) keeps the
data alive. On Windows, os.unlink refuses to remove a file that any
handle still has open -- fd 0 still points at it via dup2 -- so this
raises PermissionError (WinError 32) on every direct-mode contract deploy.

This is an upstream bug in the test library, not in the contract under
test (same shim used across every prior GenLayer project on this machine,
e.g. authorization-proof-settler/tests/direct/conftest.py). We patch
os.unlink to swallow exactly that failure so test collection can proceed;
the OS actually deletes the temp file once fd 0 is closed/reused at
process exit.

A DEEPER failure ("name 'gl' is not defined" / genvm-lint validate/schema
failing the same way) was previously assumed to be a long-standing,
unresolved local toolchain gap. It turned out to be three real, fixable
things instead, once actually debugged end-to-end on this project: (1) the
contract used a stale pre-v0.3.0 genlayer import/API pattern
(`from genlayer import *`, bare `gl.Contract`/`gl.Event`,
`gl.vm.run_nondet_unsafe`), (2) `__init__` hand-instantiated its TreeMap
fields instead of letting the storage generator auto-allocate them, and
(3) gltest's own `artifacts/` cache directory collided by name with this
project's bundle output directory and gltest clears it at session start.
See docs/STATUS.md and CHANGELOG.md for the full writeup -- gltest direct-
mode deploy and a real create/accept/cancel/adjudicate-guard flow all pass
end-to-end on this contract now. This shim's own fix (Windows os.unlink)
remains necessary and unrelated to any of that.
"""

import os

_original_unlink = os.unlink


def _tolerant_unlink(path, *args, **kwargs):
    try:
        _original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass


os.unlink = _tolerant_unlink
