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

This alone does not fix the deeper, separately-documented local toolchain
gap (genvm-lint validate/schema and gltest direct-deploy both fail with
"name 'gl' is not defined" when the sandbox tries to actually load a
contract module -- see docs/STATUS.md). This shim only removes the
Windows-specific PermissionError so that deeper failure surfaces cleanly
instead of being masked by an unrelated crash.
"""

import os

_original_unlink = os.unlink


def _tolerant_unlink(path, *args, **kwargs):
    try:
        _original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass


os.unlink = _tolerant_unlink
