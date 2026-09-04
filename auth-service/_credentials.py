"""
site-manager's credentials.enc blob format, isolated to its own file.

This is the one piece of deploy_plugin.py that has already broken silently
once: site-manager migrated its blob layout from v1 to a versioned v2, and
the public copy of deploy_plugin.py -- decoupled from site-manager on
purpose, so it does not import site-manager's own parser -- kept the old v1
assumption until that was noticed and fixed by hand.

deploy_plugin.py exists as two independent copies (this repo, and
wp-auth-service's public mirror) that are NOT kept in sync by
publish-plugin.ps1 -- wp-auth-service is documented there as a deliberate
exception to the automated public-mirror pipeline every other plugin uses.
So nothing currently re-syncs this file when one copy changes. Splitting
the format-parsing logic out of the ~430-line deploy_plugin.py into this
~20-line file does not remove that duplication -- it still has to be
copied by hand -- but it shrinks what has to be checked to one small,
rarely-touched file instead of a large one where a format change could
land buried in unrelated edits. `check_sync.py` in this same directory
diffs this file (and deploy_plugin.py) against the sibling repo on demand.

If this ever grows a third format version, or a third consumer, this is
the file to package properly instead of hand-copying again.
"""
import struct

#: site-manager writes credentials.enc in one of two layouts:
#:   v2 (current):  b"WPSMv2:" + iterations (4-byte big-endian) + 16-byte salt
#:                  + Fernet ciphertext
#:   v1 (legacy) :  16-byte salt + Fernet ciphertext, always 100_000 iterations
#: The v2 header exists so the iteration count can be raised without breaking
#: files already on disk -- it was raised, from 100k to 600k.
CRED_MAGIC = b"WPSMv2:"
CRED_LEGACY_ITERATIONS = 100_000


def parse_credentials_blob(data: bytes) -> tuple[bytes, bytes, int]:
    """Return (salt, ciphertext, iterations) for either layout."""
    if data.startswith(CRED_MAGIC):
        offset = len(CRED_MAGIC)
        iterations = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        return data[offset:offset + 16], data[offset + 16:], iterations
    return data[:16], data[16:], CRED_LEGACY_ITERATIONS
