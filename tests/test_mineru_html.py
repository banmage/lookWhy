"""MinerU HTML → CSM 表格适配（合并单元格通用方案）测试。"""

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.mineru_html import convert_mineru_markup, formula_assets_index, html_table_to_csm


TABLE1_HTML = (
    "<table>"
    "<tr><td rowspan=1 colspan=2>扇叶规格mm</td><td rowspan=1 colspan=1>250</td>"
    "<td rowspan=1 colspan=1>300</td><td rowspan=1 colspan=1>350</td>"
    "<td rowspan=1 colspan=1>400</td><td rowspan=1 colspan=1>450</td>"
    "<td rowspan=1 colspan=1>500</td><td rowspan=1 colspan=1>600</td></tr>"
    "<tr><td rowspan=3 colspan=1>输入功率W</td><td rowspan=1 colspan=1>电容运转异步电动机</td>"
    "<td rowspan=1 colspan=1>32.8</td><td rowspan=1 colspan=1>42.7</td><td rowspan=1 colspan=1>51.1</td>"
    "<td rowspan=1 colspan=1>60.0</td><td rowspan=1 colspan=1>63.6</td><td rowspan=1 colspan=1>70.8</td>"
    "<td rowspan=1 colspan=1>100.0</td></tr>"
    "<tr><td rowspan=1 colspan=1>罩极异步电动机</td><td rowspan=1 colspan=1>44.9</td>"
    "<td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td>"
    "<td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td>"
    "<td rowspan=1 colspan=1></td></tr>"
    "<tr><td rowspan=1 colspan=1>无刷直流电动机</td><td rowspan=1 colspan=1></td>"
    "<td rowspan=1 colspan=1>22.9</td><td rowspan=1 colspan=1>28.8</td><td rowspan=1 colspan=1>33.3</td>"
    "<td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td>"
    "<td rowspan=1 colspan=1></td></tr>"
    "</table>"
)


class HtmlTableToCsmTests(unittest.TestCase):
    def test_not_applicable_marker_variants_normalise_to_em_dash(self):
        # OCR 把"不适用"一字线 — 误读为 一/二//－ 等；单独成格时归一为 —（GBT-C17）。
        html = (
            "<table>"
            "<tr><td>规格</td><td>值A</td><td>值B</td></tr>"
            "<tr><td>200</td><td>一</td><td>—</td></tr>"
            "<tr><td>300</td><td>/</td><td>二</td></tr>"
            "<tr><td>400</td><td>－</td><td>50</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t2", "表2 示例")
        self.assertIn("| 200 | — | — |", out)
        self.assertIn("| 300 | — | — |", out)
        self.assertIn("| 400 | — | 50 |", out)
        self.assertNotIn("一", out.splitlines()[3])
        self.assertNotIn("/", out.splitlines()[4])

    def test_footnote_marker_restored_to_referenced_cell(self):
        # GB/T 1.1 表脚注：单元格"匝间绝缘"的上角标 a 被 OCR 丢失，仅剩脚注行
        # "a 匝间绝缘的检验…"；恢复逻辑把 a 补回说明文本所引用的最长单元格（GBT-C18）。
        html = (
            "<table>"
            "<tr><td>序号</td><td>检验项目</td><td>章条编号</td></tr>"
            "<tr><td>1</td><td>外观</td><td>4.6.1</td></tr>"
            "<tr><td>7</td><td>匝间绝缘</td><td>4.13</td></tr>"
            "<tr><td colspan=3>a 匝间绝缘的检验可在部件生产过程中进行。</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t5", "表5 出厂检验项目")
        self.assertIn("| 7 | 匝间绝缘a | 4.13 |", out)
        self.assertIn("| a 匝间绝缘的检验可在部件生产过程中进行。 |", out)

    def test_footnote_without_matching_cell_is_left_alone(self):
        html = (
            "<table>"
            "<tr><td>序号</td><td>项目</td></tr>"
            "<tr><td>1</td><td>外观</td></tr>"
            "<tr><td colspan=2>a 检验在部件生产过程中进行。</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t6", "表6 示例")
        # 脚注说明不含任何单元格完整内容，不猜测、不补标记。
        self.assertIn("| 1 | 外观 |", out)
        self.assertNotIn("外观a", out)

    def test_rowspan_keeps_columns_aligned_and_emits_merge(self):
        out = html_table_to_csm(TABLE1_HTML, "t1", "表1 配套扇叶规格的电动机输入功率")
        lines = out.splitlines()
        # 9 列等宽网格：被 rowspan 覆盖的行必须补空占位，不得左移。
        widths = {line.count("|") - 1 for line in lines if line.startswith("|")}
        self.assertEqual(widths, {9})
        self.assertIn("| 输入功率W | 电容运转异步电动机 | 32.8 | 42.7 | 51.1 | 60.0 | 63.6 | 70.8 | 100.0 |", out)
        # 罩极/无刷行首位是 rowspan 占位空列，机型文本仍在第 2 列。
        self.assertIn("|  | 罩极异步电动机 | 44.9 |", out)
        self.assertIn("|  | 无刷直流电动机 |  | 22.9 |", out)
        # 表头跨列（row=0）与数据行 rowspan 都产 merge 指令。
        self.assertIn('<!-- ssir:table-merge table="mineru-table-t1" row="0" column="1" rowspan="1" colspan="2" -->', out)
        self.assertIn('<!-- ssir:table-merge table="mineru-table-t1" row="1" column="1" rowspan="3" colspan="1" -->', out)
        self.assertEqual(out.count("ssir:table-merge"), 2)

    def test_header_colspan_emits_merge_with_row_zero(self):
        # 表2 形态：表头"功率因数cosφ"跨第 3、4 列。
        html = (
            "<table>"
            "<tr><td>电动机配套的扇叶直径mm</td><td>电动机同步转速r/min</td><td colspan=2>功率因数cosφ</td></tr>"
            "<tr><td>200</td><td>3 000</td><td>电容运转异步电动机</td><td>罩极异步电动机</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t2", "表2")
        self.assertIn("| 电动机配套的扇叶直径mm | 电动机同步转速r/min | 功率因数cosφ |  |", out)
        self.assertIn('ssir:table-merge table="mineru-table-t2" row="0" column="3" rowspan="1" colspan="2"', out)

    def test_out_of_range_rowspan_is_clamped(self):
        html = (
            "<table>"
            "<tr><td>A</td><td>B</td></tr>"
            "<tr><td rowspan=9 colspan=2>C</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t2", None)
        # 数据行仅 1 行：rowspan=9 钳制为 1（防止渲染 SPAN 越界），colspan=2 保留。
        self.assertNotIn("rowspan=\"9\"", out)
        self.assertIn('ssir:table-merge table="mineru-table-t2" row="1" column="1" rowspan="1" colspan="2"', out)

    def test_inner_rowspan_columns_stay_aligned(self):
        """表10 寿命型：被覆盖的列出现在行中（运行方式列跨 2 行），其后单元格不得左移（GBT-X02）。"""
        html = (
            "<table>"
            "<tr><td>机座号</td><td>轴伸位置</td><td>运行方式</td><td>试验时间h</td><td>温度°C</td></tr>"
            '<tr><td rowspan="3">90及以下</td><td>水平</td><td rowspan="2">空载</td><td>32±1</td><td>L</td></tr>'
            '<tr><td>垂直向上</td><td>12±1</td><td rowspan="2">H</td></tr>'
            "<tr><td>向上45°</td><td>空载</td><td>12±1</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t10", "表 10 寿命")
        widths = {line.count("|") - 1 for line in out.splitlines() if line.startswith("|")}
        self.assertEqual(widths, {5})
        # 空载（column 3）跨行时，后面的试验时间/温度列必须留在第 4/5 列。
        self.assertIn("|  | 垂直向上 |  | 12±1 | H |", out)
        self.assertIn("|  | 向上45° | 空载 | 12±1 |  |", out)
        self.assertIn('ssir:table-merge table="mineru-table-t10" row="1" column="3" rowspan="2" colspan="1"', out)
        self.assertIn('ssir:table-merge table="mineru-table-t10" row="2" column="5" rowspan="2" colspan="1"', out)

    def test_inline_eq_marker_becomes_csm_inline_math(self):
        """GEN-097：MinerU 的 <eq> 行内公式标记 → CSM `$…$`（表10 的 \\frac{1}{2} 型）。"""
        html = (
            "<table>"
            "<tr><td>运行方式</td><td>试验时间h</td></tr>"
            "<tr><td><eq>\\frac{1}{2}</eq>连续堵转转矩</td><td>170±1</td></tr>"
            "</table>"
        )
        out = html_table_to_csm(html, "t1", None)
        self.assertIn("$\\frac{1}{2}$连续堵转转矩", out)
        self.assertNotIn("<eq>", out)


class ConvertMineruMarkupTests(unittest.TestCase):
    def test_inline_eq_in_body_text_becomes_csm_inline_math(self):
        out = convert_mineru_markup("转速为 <eq>n_{1}</eq> 时, 波动不大于 5%。\n", "p001", {})
        self.assertIn("$n_{1}$", out)
        self.assertNotIn("<eq>", out)

    def test_tables_images_and_formulas_are_adapted(self):
        raw = (
            "## 4.7 电动机的输入功率\n\n"
            "输入功率应不大于表1的规定。\n\n"
            "表1 配套扇叶规格的电动机输入功率\n\n"
            + TABLE1_HTML + "\n\n"
            "![图1 示意图](images/fig-001.png)\n\n"
            "图1 示意图\n\n"
            "$$\nE = m c ^ 2\n$$\n"
        )
        out = convert_mineru_markup(raw, "p001", {})
        self.assertIn("<!-- ssir:table id=\"mineru-table-p001-001\" header-rows=\"1\" caption-number=\"1\" caption=\"配套扇叶规格的电动机输入功率\" -->", out)
        self.assertIn("ssir:table-merge table=\"mineru-table-p001-001\" row=\"1\" column=\"1\" rowspan=\"3\"", out)
        # 题注行被吸附进表格指令，不再作为孤立段落残留。
        self.assertNotIn("表1 配套扇叶规格的电动机输入功率\n\n<!-- ssir:table", out)
        # 图片路径改写为 assets/，标签按"图 N 题名"规范化。
        self.assertIn("![图 1 示意图](assets/images/fig-001.png)", out)

    def test_placeholder_image_alt_is_dropped(self):
        """GEN-096：MinerU 的通用占位替代文本不是图题名（docs/07 §6.5）。"""
        out = convert_mineru_markup("![image](assets/images/fig-001.png)\n\n正文。\n", "p001", {})
        self.assertIn("![](assets/images/fig-001.png)", out)
        self.assertNotIn("[image]", out)

    def test_placeholder_variants_dropped_and_real_alt_kept(self):
        raw = (
            "![接线图](images/fig-001.png)\n\n"
            "![image1](images/fig-002.png)\n\n"
            "![图片](images/fig-003.png)\n\n"
            "段末不是整行图片语法的 ![image](images/fig-004.png) 不动。\n"
        )
        out = convert_mineru_markup(raw, "p001", {})
        self.assertIn("![接线图](assets/images/fig-001.png)", out)
        self.assertIn("![](assets/images/fig-002.png)", out)
        self.assertIn("![](assets/images/fig-003.png)", out)
        self.assertIn("段末不是整行图片语法的 ![image](assets/images/fig-004.png) 不动。", out)

    def test_figure_caption_still_wins_over_placeholder_alt(self):
        out = convert_mineru_markup("![image](images/fig-001.png)\n\n图1 接线图\n", "p001", {})
        self.assertIn("![图 1 接线图](assets/images/fig-001.png)", out)

    def test_formula_assets_are_bound_from_content_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "p1_content_list.json").write_text(
                '[{"type": "equation", "img_path": "images/eq_01.jpg", "text": "$$E = m c ^ 2$$"}]',
                encoding="utf-8",
            )
            source = root / "p1.md"
            assets = formula_assets_index(source)
            self.assertEqual(assets, {"E=mc^2": ["assets/images/eq_01.jpg"]})
            out = convert_mineru_markup("$$\nE = m c ^ 2\n$$\n", "p001", assets)
            self.assertIn('<!-- ssir:formula id="mineru-formula-p001-001" asset-ref="assets/images/eq_01.jpg" -->', out)


class HeaderMergeRoundTripTests(unittest.TestCase):
    """表头合并（row=0）必须通过 render.md 回环保持，否则 ssir 与 verify 分歧。"""

    def test_header_colspan_survives_round_trip(self):
        from leleby_ssir.service import round_trip_csm

        csm = (
            "---\n"
            "document-type: standard\n"
            'document-identifier: "Q/TEST 001-2026"\n'
            'standard-number: "Q/TEST 001-2026"\n'
            'title: "表头合并回环测试"\n'
            "language: zh-CN\n"
            "---\n"
            "# 表头合并回环测试\n\n"
            "## 1 范围\n\n"
            "本文件规定了表头合并的回环行为。\n\n"
            "<!-- ssir:table id=\"tbl-001\" header-rows=\"1\" caption-number=\"1\" caption=\"示例\" -->\n"
            "| a | b | c |  |\n"
            "| --- | --- | --- | --- |\n"
            "| 1 | 2 | 3 | 4 |\n"
            "<!-- ssir:table-merge table=\"tbl-001\" row=\"0\" column=\"3\" rowspan=\"1\" colspan=\"2\" -->\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "t.canonical.md"
            source.write_text(csm, encoding="utf-8")
            ssir, verify, report = round_trip_csm(source, root / "t.render.md")
            self.assertTrue(report.passed, report.to_dict())
            for document in (ssir, verify):
                table = document["tables"][0]
                header_cell = table["rows"][0]["cells"][2]
                self.assertEqual(header_cell["text"], "c")
                self.assertEqual(header_cell["colspan"], 2)
                self.assertEqual(header_cell["rowspan"], 1)


if __name__ == "__main__":
    unittest.main()
