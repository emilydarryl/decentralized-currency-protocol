# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for physical-memory diagnostic parsers."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.measure_physical_memory_v1 import parse_verbose_time
from contrib.pow_research_cpp.verify_recursive_stack_usage_v1 import (
    maximum_bounded_stack_usage,
    parse_stack_usage,
)


class PhysicalMemoryToolsV1Test(unittest.TestCase):
    def test_verbose_time_parser_converts_kibibytes(self) -> None:
        parsed = parse_verbose_time(
            """
            Maximum resident set size (kbytes): 1234
            Minor (reclaiming a frame) page faults: 55
            Major (requiring I/O) page faults: 2
            """
        )
        self.assertEqual(parsed["maximum_resident_set_bytes"], 1234 * 1024)
        self.assertEqual(parsed["minor_page_faults"], 55)
        self.assertEqual(parsed["major_page_faults"], 2)

    def test_stack_usage_parser_finds_recursive_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "powvm.su"
            source.write_text(
                "powvm.cpp:1:1:uint64_t RecursiveRegenerator::ValueAt(uint64_t)"
                "\t496\tstatic\n",
                encoding="utf-8",
            )
            records = parse_stack_usage([source])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bytes"], 496)
        self.assertEqual(records[0]["qualifier"], "static")

    def test_stack_usage_accepts_bounded_dynamic_and_rejects_unbounded(self) -> None:
        bounded = [{"bytes": 352, "qualifier": "dynamic,bounded"}]
        self.assertEqual(maximum_bounded_stack_usage(bounded), 352)
        with self.assertRaisesRegex(AssertionError, "unbounded stack usage"):
            maximum_bounded_stack_usage([{"bytes": 352, "qualifier": "dynamic"}])


if __name__ == "__main__":
    unittest.main()
