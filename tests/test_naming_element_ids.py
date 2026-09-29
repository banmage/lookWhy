"""文档元素标识（TDRS 命名规则）测试 —— naming.py §文档元素标识。

依据：`技术文件智能审查系统（TDRS）设计说明文档v2.0.md`「附录：标准元素标识 / 命名规则」
§一 标准号处理、§二 条款号引用格式、§四 附录、§五 项、§六 表图公式、§八 变量 ID、§九 概念 ID。

夹具逐条取自该文档的示例表（标准号映射、条款路径、附录、多级项、表图公式、变量 ID、概念 ID）。
"""

from __future__ import annotations

import unittest

from leleby_ssir.naming import (
    annex_path,
    clause_path,
    concept_id,
    element_id,
    escape_standard_number,
    figure_element_id,
    formula_element_id,
    local_element_id,
    numbered_element_path,
    owned_element_id,
    parse_element_id,
    standard_filename,
    table_element_id,
    variable_id,
)


class EscapeStandardNumberTest(unittest.TestCase):
    """TDRS §一 转义规则与示例表。"""

    def test_document_examples(self):
        cases = {
            "GB/T 1.1—2020": "GB_T_1.1-2020",
            "GB 3100—2026": "GB_3100-2026",
            "GB/T 20001.10—2014": "GB_T_20001.10-2014",
            "ISO 80000-1:2022": "ISO_80000-1_2022",
            "IEC 60027": "IEC_60027",
            "GB 4351—2023": "GB_4351-2023",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(escape_standard_number(raw), expected)

    def test_agrees_with_file_name_derivation(self):
        """转义结果与文件名 STANDARD_ID 推导同值（同一标准、同一标识）。"""
        for raw in ("GB/T 1.1—2020", "GB 3100—2026", "GB/T 20001.10—2014",
                    "JB/T 14054—2021", "Q/XKBZ 002—2026"):
            with self.subTest(raw=raw):
                self.assertEqual(escape_standard_number(raw), standard_filename(raw))

    def test_hyphen_preserved(self):
        self.assertEqual(escape_standard_number("GB/T 20001.10-2014"), "GB_T_20001.10-2014")

    def test_version_separator_variants_normalised(self):
        """抽取层把一字线认成「一」/全角连字符等时，标识仍与规范写法同值（同一标准同一标识）。"""
        expected = "GB_T_4208-2017"
        for raw in ("GB/T 4208—2017", "GB/T 4208-2017", "GB/T 4208一2017",
                    "GB/T 4208－2017", "GB/T 4208~2017", "GB/T 4208 一 2017"):
            with self.subTest(raw=raw):
                self.assertEqual(escape_standard_number(raw), expected)

    def test_cjk_numeral_outside_year_position_untouched(self):
        """「一」只在「数字 + 分隔符 + 4 位年份」位置归一，其它位置的原文字符不动。"""
        self.assertEqual(escape_standard_number("GB/T 第一"), "GB_T_第一")


class ElementIdTest(unittest.TestCase):
    """TDRS §二/§三/§四/§五 条款路径。"""

    def test_document_examples(self):
        sid = "GB_T_1.1-2020"
        cases = [
            (clause_path("8.2.1"), f"{sid}#8.2.1"),
            (clause_path("8.2.1", ["a)"]), f"{sid}#8.2.1_a"),
            (clause_path("8.2.1", ["c)", "1)"]), f"{sid}#8.2.1_c_1"),
            (clause_path("8.2.1", ["a)", "1)", "i)"]), f"{sid}#8.2.1_a_1_i"),
            (annex_path("A"), f"{sid}#Annex_A"),
            (annex_path("A", "2.1"), f"{sid}#Annex_A.2.1"),
            (annex_path("A", "A.2.1"), f"{sid}#Annex_A.2.1"),
            (annex_path("A", "A.2.1", ["b)"]), f"{sid}#Annex_A.2.1_b"),
            (annex_path("Annex_B", "B.1"), f"{sid}#Annex_B.1"),
        ]
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(element_id(sid, path), expected)

    def test_separator_is_hash(self):
        self.assertEqual(element_id("GB_3100-2026", "8.2.1"), "GB_3100-2026#8.2.1")
        self.assertIn("#", element_id("GB_3100-2026", "8.2.1"))

    def test_parse_roundtrip(self):
        for identifier in ("GB_T_1.1-2020#8.2.1_a", "GB_3100-2026#Annex_B.1",
                           "GB_T_1.1-2020#Table_3", "GB_T_30819-2024#5.2.1/Paragraph-001"):
            with self.subTest(identifier=identifier):
                standard, path = parse_element_id(identifier)
                self.assertEqual(element_id(standard, path), identifier)

    def test_rejects_invalid(self):
        for bad in ("", "#8.2.1", "GB_T_1.1-2020", "GB_T_1.1-2020#", "GB_T_1.1-2020#8.2.1 x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_element_id(bad)
        with self.assertRaises(ValueError):
            element_id("GB_T_1.1#2020", "8.1")     # 标准标识不得含 '#'
        with self.assertRaises(ValueError):
            element_id("GB_T_1.1-2020", "")


class NumberedElementTest(unittest.TestCase):
    """TDRS §六 表、图、公式。"""

    def test_document_examples(self):
        sid = "GB_T_1.1-2020"
        self.assertEqual(table_element_id(sid, "3"), "GB_T_1.1-2020#Table_3")
        self.assertEqual(figure_element_id(sid, "5"), "GB_T_1.1-2020#Figure_5")
        self.assertEqual(formula_element_id(sid, "3"), "GB_T_1.1-2020#Formula_3")
        self.assertEqual(numbered_element_path("Formula", "1"), "Formula_1")

    def test_annex_elements_use_element_prefix(self):
        """偏离①：附录内表/图/公式带类型前缀，避免与附录条款号（Annex_A.1）撞车。"""
        sid = "GB_3100-2026"
        self.assertEqual(table_element_id(sid, "B.1"), "GB_3100-2026#Table_B.1")
        self.assertEqual(figure_element_id(sid, "E.1"), "GB_T_1.1-2020#Figure_E.1".replace("GB_T_1.1-2020", sid))
        self.assertEqual(formula_element_id("GB_T_1.1-2020", "A.1"), "GB_T_1.1-2020#Formula_A.1")
        self.assertNotEqual(table_element_id(sid, "A.1"), annex_path("A", "1"))

    def test_rejects_empty_number(self):
        with self.assertRaises(ValueError):
            table_element_id("GB_T_1.1-2020", "  ")


class OwnedAndLocalElementTest(unittest.TestCase):
    def test_owned_element(self):
        self.assertEqual(owned_element_id("GB_T_1.1-2020#Table_3", "note", "1"),
                         "GB_T_1.1-2020#Table_3.Note_1")
        self.assertEqual(owned_element_id("GB_T_1.1-2020#8.2.1", "footnote", "1"),
                         "GB_T_1.1-2020#8.2.1.Foot_1")
        with self.assertRaises(ValueError):
            owned_element_id("GB_T_1.1-2020", "note", "1")

    def test_local_element(self):
        self.assertEqual(local_element_id("GB_T_1.1-2020#8.2.1", "paragraph", 7),
                         "GB_T_1.1-2020#8.2.1/Paragraph-007")
        self.assertEqual(local_element_id("GB_T_1.1-2020#Annex_A", "list", 1),
                         "GB_T_1.1-2020#Annex_A/List-001")
        self.assertEqual(local_element_id("GB_T_1.1-2020#8.2.1", "block", 3),
                         "GB_T_1.1-2020#8.2.1/Block-003")
        with self.assertRaises(ValueError):
            local_element_id("GB_T_1.1-2020#8.2.1", "widget", 1)


class VariableIdTest(unittest.TestCase):
    """TDRS §八 变量 ID 示例表。"""

    def test_document_examples(self):
        self.assertEqual(variable_id(r"\overline{\eta}"), "VAR_ETA_OVERLINE")
        self.assertEqual(variable_id("x_n^e"), "VAR_X_SUB_N_SUP_E")
        self.assertEqual(variable_id("S_{ME,i}"), "VAR_S_SUB_ME_I")

    def test_stable_and_ascii(self):
        for latex in (r"\overline{P}_{1}", r"\dfrac{a}{b}", "v_{max}"):
            with self.subTest(latex=latex):
                first = variable_id(latex)
                self.assertEqual(first, variable_id(latex))
                self.assertRegex(first, r"^VAR_[A-Z0-9_]+$")


class ConceptIdTest(unittest.TestCase):
    """TDRS §九 概念 ID 示例表。"""

    def test_document_examples(self):
        self.assertEqual(concept_id("MASS"), "CONCEPT_MASS")
        self.assertEqual(concept_id("QUALITY"), "CONCEPT_QUALITY")

    def test_requires_latin_name(self):
        with self.assertRaises(ValueError):
            concept_id("质量")


if __name__ == "__main__":
    unittest.main()
