from __future__ import annotations

import unittest

from homorepeat.acquisition.translation import get_translation_table, translate_cds


class TranslationTablesTest(unittest.TestCase):
    def test_translate_cds_accepts_vertebrate_mitochondrial_table(self) -> None:
        result = translate_cds("ATATGATAA", "2")

        self.assertTrue(result.accepted)
        self.assertEqual(result.translation_table, "2")
        self.assertEqual(result.protein_sequence, "MW")

    def test_translate_cds_accepts_invertebrate_mitochondrial_table(self) -> None:
        result = translate_cds("ATATGAAGATAG", "5")

        self.assertTrue(result.accepted)
        self.assertEqual(result.translation_table, "5")
        self.assertEqual(result.protein_sequence, "MWS")

    def test_translate_cds_accepts_bacterial_table_alias(self) -> None:
        result = translate_cds("ATGGCCTAA", "11")

        self.assertTrue(result.accepted)
        self.assertEqual(result.translation_table, "11")
        self.assertEqual(result.protein_sequence, "MA")

    def test_translate_cds_reports_likely_translation_table_mismatch(self) -> None:
        result = translate_cds("ATATGATAA", "1")

        self.assertFalse(result.accepted)
        self.assertEqual(result.warning_code, "likely_translation_table_mismatch")
        self.assertIn("translated successfully under table 2", result.warning_message)

    def test_translate_cds_reports_unsupported_translation_table(self) -> None:
        result = translate_cds("ATGGCCTAA", "99")

        self.assertFalse(result.accepted)
        self.assertEqual(result.warning_code, "unsupported_translation_table")
        self.assertIn("Unsupported translation table: 99", result.warning_message)
        self.assertIsNone(get_translation_table("99"))


if __name__ == "__main__":
    unittest.main()
