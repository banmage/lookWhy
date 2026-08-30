"""Tests for standard-name parsing (standard_name.py) — 标准类型与标准化主对象识别。

覆盖 376 条清单中的代表性名称：类型判定、主词长词优先、应用场合提取、
"通用/专用"干扰词、第X部分回退、命名一致性核查（GBT-N01/N02）。
"""

from __future__ import annotations

import unittest

from leleby_ssir.standard_name import StandardNameInfo, name_matches_type, parse_standard_name


class ClassifyTypeTest(unittest.TestCase):
    def test_method(self):
        self.assertEqual(parse_standard_name("三相异步电动机试验方法").standard_type, "方法标准")
        self.assertEqual(parse_standard_name("旋转电机噪声测定方法及限值 第1部分：旋转电机噪声测定方法").standard_type, "方法标准")
        self.assertEqual(parse_standard_name("振动与冲击传感器的校准方法 激光干涉法振动绝对校准").standard_type, "方法标准")

    def test_terminology(self):
        self.assertEqual(parse_standard_name("传感器通用术语").standard_type, "术语标准")
        self.assertEqual(parse_standard_name("仪器仪表 通用术语").standard_type, "术语标准")

    def test_classification(self):
        self.assertEqual(parse_standard_name("控制电机型号命名方法").standard_type, "分类标准")

    def test_guide(self):
        self.assertEqual(parse_standard_name("用于电力传动系统的交流电机 应用导则").standard_type, "指南标准")

    def test_safety(self):
        self.assertEqual(parse_standard_name("旋转电机 安全技术规范").standard_type, "安全标准")
        self.assertEqual(parse_standard_name("小功率电动机的安全要求").standard_type, "安全标准")

    def test_product(self):
        self.assertEqual(parse_standard_name("永磁式直流力矩电动机通用技术规范").standard_type, "产品标准")
        self.assertEqual(parse_standard_name("离心泵技术条件（Ⅰ类）").standard_type, "产品标准")


class SubjectTest(unittest.TestCase):
    def test_long_word_priority(self):
        # 长词优先：三相异步电动机 优先于 电动机/电机
        info = parse_standard_name("三相异步电动机试验方法")
        self.assertEqual(info.subject, "三相异步电动机")

    def test_rotation_machine(self):
        info = parse_standard_name("旋转电机 安全技术规范")
        self.assertEqual(info.subject, "旋转电机")

    def test_part_fallback(self):
        # 冒号后无主词时回退主标题（小功率电动机）
        info = parse_standard_name("小功率电动机 第21部分：通用试验方法")
        self.assertEqual(info.subject, "小功率电动机")

    def test_part_specific_subject(self):
        # 冒号后有更具体主词时取冒号后（三相异步电动机）
        info = parse_standard_name("交流电梯电动机通用技术条件 第1部分：三相异步电动机")
        self.assertEqual(info.subject, "三相异步电动机")

    def test_pump_family(self):
        info = parse_standard_name("离心泵、混流泵和轴流泵 汽蚀余量")
        self.assertIn(info.subject, ("离心泵", "混流泵", "轴流泵"))


class ApplicationTest(unittest.TestCase):
    def test_ship(self):
        info = parse_standard_name("船用旋转电机基本技术要求")
        self.assertEqual(info.application, "船用")
        self.assertEqual(info.subject, "旋转电机")

    def test_compressor(self):
        # "封闭式"形态词不应混入场景；场景为"制冷压缩机用"
        info = parse_standard_name("封闭式制冷压缩机用电动机绝缘相容性试验方法")
        self.assertEqual(info.application, "制冷压缩机用")
        self.assertEqual(info.subject, "电动机")

    def test_series_prefix(self):
        # "系列"前缀剥除 → 场景"起重及冶金用"
        info = parse_standard_name("YZR3系列起重及冶金用绕线转子三相异步电动机 技术条件")
        self.assertEqual(info.application, "起重及冶金用")

    def test_generic_not_application(self):
        # "通用"中的"用"不是场景后缀
        info = parse_standard_name("传感器通用术语")
        self.assertEqual(info.application, "")

    def test_zhuan_yong(self):
        # "X专用" → 场景还原为"X用"（纺织专用 → 纺织用）
        info = parse_standard_name("纺织专用三相异步电动机 技术条件")
        self.assertEqual(info.application, "纺织用")


class NameMatchesTypeTest(unittest.TestCase):
    def test_consistent(self):
        self.assertTrue(name_matches_type(parse_standard_name("三相异步电动机试验方法")))
        self.assertTrue(name_matches_type(parse_standard_name("传感器通用术语")))
        self.assertTrue(name_matches_type(parse_standard_name("旋转电机 安全技术规范")))

    def test_inconsistent(self):
        # 命名与类型不一致：术语标准名称缺"术语/定义/词汇"
        info = StandardNameInfo(title="传感器通用要求", standard_type="术语标准")
        self.assertFalse(name_matches_type(info))
        # 方法标准名称缺方法类关键词
        info = StandardNameInfo(title="三相异步电动机技术条件", standard_type="方法标准")
        self.assertFalse(name_matches_type(info))
        # 分类标准名称缺分类类关键词
        info = StandardNameInfo(title="旋转电机 噪声限值", standard_type="分类标准")
        self.assertFalse(name_matches_type(info))


if __name__ == "__main__":
    unittest.main()
