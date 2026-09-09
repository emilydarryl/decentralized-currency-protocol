# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_v1 import challenge_pack


class ChallengePackTest(unittest.TestCase):
    def test_committed_manifest_matches_pack(self) -> None:
        challenge_pack.verify_manifest()

    def test_changed_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            document = challenge_pack.build_document()
            document["files"][0]["canonical_bytes"] += 1
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(challenge_pack.PackError):
                challenge_pack.verify_manifest(manifest)

    def test_line_endings_have_one_canonical_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lf_path = Path(temporary) / "lf.txt"
            crlf_path = Path(temporary) / "crlf.txt"
            lf_path.write_bytes(b"one\ntwo\n")
            crlf_path.write_bytes(b"one\r\ntwo\r\n")
            self.assertEqual(
                challenge_pack._sha3_384(lf_path), challenge_pack._sha3_384(crlf_path)
            )


if __name__ == "__main__":
    unittest.main()
