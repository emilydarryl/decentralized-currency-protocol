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
            document["files"][0]["bytes"] += 1
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(challenge_pack.PackError):
                challenge_pack.verify_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
