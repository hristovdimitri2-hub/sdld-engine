"""Реални тестове за src/vat.py — гейтът ги изпълнява наистина."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vat import withVAT  # noqa: E402


class TestWithVAT(unittest.TestCase):
    def test_basic_rate(self):
        self.assertEqual(withVAT(100, 0.21), 121.0)

    def test_zero(self):
        self.assertEqual(withVAT(0, 0.2), 0.0)

    def test_rounding(self):
        # 33.33 * 1.19 = 39.6627 -> 39.66
        self.assertEqual(withVAT(33.33, 0.19), 39.66)


if __name__ == "__main__":
    unittest.main()
