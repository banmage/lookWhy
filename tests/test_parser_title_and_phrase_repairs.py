from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.parser import CSMParser


def _parse(body: str) -> "tuple":
    csm = (
        "---\n"
        'csm-version: "1.0"\n'
        "document-type: standard\n"
        'document-identifier: "GB/T 20001.10—2014"\n'
        'standard-number: "GB/T 20001.10—2014"\n'
        'title: "标准编写规则 第10部分：产品标准"\n'
        "language: zh-CN\n"
        "extensions:\n"
        "  standard-profile: product\n"
        "---\n\n"
        + body
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.canonical.md"
        path.write_text(csm, encoding="utf-8")
        doc = CSMParser().read(path)
    return doc.blocks, doc.issues


class TitleAndGuidePhraseRepairTests(unittest.TestCase):
    """CSM-STRUCT-004 多部分名称跨行 H1 合并 与 CSM-OCR-011 固定引导语修复。"""

    def test_split_multipart_title_merges_adjacent_h1_pair(self) -> None:
        # 正文首页名称分两行排印（GB_T_20001.10-2014 型）：两个相邻 H1。
        body = (
            "# 标准编写规则\n"
            "\n"
            "# 第10部分：产品标准\n"
            "\n"
            "## 1 范围\n"
            "\n"
            "本文件规定了起草产品标准的要求。\n"
        )
        blocks, issues = _parse(body)
        merged = [issue for issue in issues if issue.code == "CSM-STRUCT-004"]
        self.assertEqual(len(merged), 1)
        headings = [b.text for b in blocks if b.kind == "heading" and b.level == 1]
        self.assertEqual(headings, ["标准编写规则 第10部分：产品标准"])

    def test_split_multipart_title_ignores_non_part_or_separated_lines(self) -> None:
        # 反例 1：第二个 H1 不是“第N部分：…”（章级名称不同段）→ 不合并。
        body1 = "# 标准编写规则\n\n# 产品标准通用要求\n\n## 1 范围\n"
        blocks, issues = _parse(body1)
        self.assertFalse(any(i.code == "CSM-STRUCT-004" for i in issues))
        # 反例 2：两 H1 之间隔着内容（正文段）→ 不相邻，不合并。
        body2 = "# 标准编写规则\n\n本部分为产品标准编写规则。\n\n# 第10部分：产品标准\n\n## 1 范围\n"
        blocks, issues = _parse(body2)
        self.assertFalse(any(i.code == "CSM-STRUCT-004" for i in issues))
        self.assertEqual(
            [b.text for b in blocks if b.kind == "heading" and b.level == 1],
            ["标准编写规则", "第10部分：产品标准"],
        )

    def test_reference_guide_phrase_ocr_misread_is_restored(self) -> None:
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 2 规范性引用文件\n"
            "\n"
            "卜列文件对于本文件的应用是必不可少的。凡是注日期的引用文件，仅注日期的版本适用于本文件。\n"
        )
        blocks, issues = _parse(body)
        fixed = [issue for issue in issues if issue.code == "CSM-OCR-011"]
        self.assertEqual(len(fixed), 1)
        paragraphs = [b.text for b in blocks if b.kind == "paragraph"]
        self.assertTrue(any(t.startswith("下列文件对于本文件") for t in paragraphs))

    def test_reference_guide_phrase_untouched_when_not_the_fixed_sentence(self) -> None:
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 4 总则\n"
            "\n"
            "卜列情形不适用本部分。\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-011" for i in issues))

    def test_reference_entry_brackets_restored(self) -> None:
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 参考文献\n"
            "\n"
            "[7] GB/T 27023 第三方认证制度中标准符合性的表示方法\n"
            "\n"
            "8] GB/T 27050.1 合格评定 供方的符合性声明 第1部分：通用要求\n"
            "\n"
            "9] GB/T 27050.2 合格评定 供方的符合性声明 第2部分：支持性文件\n"
        )
        blocks, issues = _parse(body)
        fixed = [issue for issue in issues if issue.code == "CSM-OCR-013"]
        self.assertEqual(len(fixed), 2)
        refs = [b.text for b in blocks if b.kind == "paragraph"]
        self.assertTrue(any(t.startswith("[8] GB/T 27050.1") for t in refs))
        self.assertTrue(any(t.startswith("[9] GB/T 27050.2") for t in refs))

    def test_reference_entry_brackets_untouched_on_body_text(self) -> None:
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 4 总则\n"
            "\n"
            "8] 该表述不构成参考文献条目。\n"
            "\n"
            "[GB/T 20000.1—2014，定义 7.9]\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-013" for i in issues))

    def test_gfm_footnote_definition_becomes_footnote_block(self) -> None:
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 2 规范性引用文件\n"
            "\n"
            "GB/T 20000.4—2003[foot:1]标准化工作指南 第4部分：标准中涉及安全的内容\n"
            "\n"
            "<!--ssir:foot:1-->GB/T 20000.4—2003已修订，即将被批准为GB/T 20002.4。<!--ssir:/foot-->\n"
        )
        blocks, issues = _parse(body)
        notes = [b for b in blocks if b.kind == "footnote"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].data.get("label"), "1")
        self.assertIn("已修订", notes[0].data.get("text", ""))
        recognised = [issue for issue in issues if issue.code == "CSM-STRUCT-005"]
        self.assertEqual(len(recognised), 1)

    def test_gfm_footnote_survives_ssir_and_csm_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path as _P
        from leleby_ssir.service import parse_csm
        from leleby_ssir.csm_renderer import render_csm
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 2 规范性引用文件\n"
            "\n"
            "GB/T 20000.4—2003[foot:1]标准化工作指南 第4部分：标准中涉及安全的内容<!--ssir:foot:1-->GB/T 20000.4—2003已修订，即将被批准为GB/T 20002.4。<!--ssir:/foot-->\n"
        )
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 20001.10—2014"\n'
            'standard-number: "GB/T 20001.10—2014"\n'
            'title: "标准编写规则 第10部分：产品标准"\n'
            "language: zh-CN\n"
            "---\n\n" + body
        )
        with tempfile.TemporaryDirectory() as d:
            p = _P(d) / "f.canonical.md"
            p.write_text(csm, encoding="utf-8")
            ssir = parse_csm(p)
            # SSIR 内容含 footnote 元素（文本不丢）。
            def find(o):
                if isinstance(o, dict):
                    if o.get("presentationType") == "footnote":
                        return o
                    for v in o.values():
                        r = find(v)
                        if r:
                            return r
                elif isinstance(o, list):
                    for v in o:
                        r = find(v)
                        if r:
                            return r
                return None
            content = find(ssir)
            self.assertIsNotNone(content)
            self.assertTrue(str(content.get("textContent", "")).startswith("1)"))
            # 脚注-条款关系记录（本体层用）：marker 与其注释条款节点 id。
            self.assertEqual(content.get("footnoteMarker"), "1")
            def nodes(o):
                if isinstance(o, dict):
                    if o.get("nodeType") and o.get("number"):
                        yield o
                    for v in o.values():
                        yield from nodes(v)
                elif isinstance(o, list):
                    for v in o:
                        yield from nodes(v)
            chapter2 = next(n for n in nodes(ssir["structuralRoot"]) if n.get("number") == "2")
            self.assertEqual(content.get("footnoteAnchorRef"), chapter2["id"])
            # csm 回环：render 输出保留 [^1]: 定义，可再解析为 footnote。
            rendered = render_csm(ssir)
            self.assertIn("<!--ssir:foot:1-->GB/T 20000.4—2003已修订，即将被批准为GB/T 20002.4。<!--ssir:/foot-->", rendered)
            self.assertIn("GB/T 20000.4—2003[foot:1]", rendered)
            # canonical 写回为“段尾同行”形态：定义紧随其角标段落末尾。
            self.assertIn("<!--ssir:foot:1-->GB/T 20000.4—2003已修订，即将被批准为GB/T 20002.4。<!--ssir:/foot-->", rendered)
            q = _P(d) / "f.render.md"
            q.write_text(rendered, encoding="utf-8")
            from leleby_ssir.parser import CSMParser
            doc2 = CSMParser().read(q)
            self.assertTrue(any(b.kind == "footnote" for b in doc2.blocks))


    def test_inline_trailing_footnote_defs_split_off(self) -> None:
        # canonical“段尾同行”形态：多条定义直接拼在角标段末尾同一行。
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 4.6 分类\n"
            "\n"
            "…或编制为单独的标准[foot:2]。"
            "<!--ssir:foot:2-->这种情况，该标准属于“分类标准”。<!--ssir:/foot-->"
            "<!--ssir:foot:3-->第三条说明。<!--ssir:/foot-->\n"
        )
        blocks, issues = _parse(body)
        kinds = [b.kind for b in blocks]
        self.assertEqual(kinds, ["heading", "heading", "paragraph", "footnote", "footnote"])
        para = blocks[2]
        self.assertNotIn("<!--ssir:foot:2--><!--ssir:/foot-->", para.text)
        self.assertIn("[foot:2]", para.text)
        f1, f2 = blocks[3], blocks[4]
        self.assertEqual(f1.data.get("label"), "2")
        self.assertIn("分类标准", f1.data.get("text", ""))
        self.assertEqual(f2.data.get("label"), "3")
        self.assertIn("第三条", f2.data.get("text", ""))
        recognised = [issue for issue in issues if issue.code == "CSM-STRUCT-005"]
        self.assertEqual(len(recognised), 2)


class FootnoteDefinitionBindingTests(unittest.TestCase):
    """CSM-STRUCT-005 扩展（2026-09-06）：段首粘连定义的剥离 + 脚注块按 [foot:N] 锚点重定位。

    页脚绘制以锚点落页为准：定义行若与下一条目粘连成段（回收脚本漏插后空行）会
    以正文身份渲染；定义若停留在远离锚点的位置（落进后续列表区）会被画到错误页
    页脚。两类都要求归类后的 footnote 块紧跟其锚点段。
    """

    def test_def_line_glued_to_next_entry_is_split_off(self) -> None:
        # 回收脚本漏插后空行：定义行与下一条引用条目无空行并成一个多行段
        # （GB_T_20001.10-2014 脚注 1 型）→ 段首定义剥离为 footnote，条目恢复独立段。
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 2 规范性引用文件\n"
            "\n"
            "GB/T 20000.4—2003[foot:1]标准化工作指南 第4部分:标准中涉及安全的内容\n"
            "\n"
            "<!--ssir:foot:1-->GB/T 20000.4—2003已修订,即将被批准为GB/T 20002.4《标准中特定内容的起草第4部分:标准中涉及安全的内容》。<!--ssir:/foot-->\n"
            "GB/T 20001.4 标准编写规则 第4部分：化学分析方法\n"
            "\n"
            "GB/T 20002.3 标准中特定内容的起草 第3部分：产品标准中涉及环境的内容\n"
        )
        blocks, issues = _parse(body)
        notes = [b for b in blocks if b.kind == "footnote"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].data.get("label"), "1")
        # 剥离后条目恢复为独立段（不再吞在定义段里）
        entry = [b for b in blocks if b.kind == "paragraph" and b.text.startswith("GB/T 20001.4")]
        self.assertEqual(len(entry), 1)
        # 归类 + 绑定后 footnote 紧跟其锚点段
        idx = blocks.index(notes[0])
        self.assertIn("[foot:1]", blocks[idx - 1].text)

    def test_multiline_definition_pair_is_one_footnote(self) -> None:
        """GEN-118：开闭指令对之间可以换行——整对算一条脚注；闭合标记之后的行
        仍是普通段落（定义不再靠「句末标点」猜测，旧启发式已退役）。"""
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 2 规范性引用文件\n"
            "\n"
            "正文[foot:1]。\n"
            "\n"
            "<!--ssir:foot:1-->这是很长很长的定义说明\n"
            "继续第二行的解释文字。<!--ssir:/foot-->\n"
            "\n"
            "这一段在闭合标记之后，仍是普通段落。\n"
        )
        blocks, issues = _parse(body)
        notes = [b for b in blocks if b.kind == "footnote"]
        self.assertEqual(len(notes), 1)
        self.assertIn("继续第二行的解释文字", notes[0].data.get("text", ""))
        self.assertTrue(any(
            b.kind == "paragraph" and b.text.startswith("这一段在闭合标记之后")
            for b in blocks
        ))

    def test_far_def_relocated_to_anchor_paragraph(self) -> None:
        # 定义停留在远离锚点的位置（GB_T_20001.10-2014 脚注 2 型：锚点在 6.4.2、
        # 定义被写在后面的章节区）→ footnote 块搬到锚点段之后，中间内容原样保留。
        body = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 6 要素的起草\n"
            "\n"
            "6.4.2 根据具体情况，该要素可并入技术要求(见6.5)，也可编制为单独的标准[foot:2]。\n"
            "\n"
            "6.4.3 其它条文。\n"
            "\n"
            "### 6.5 技术要求\n"
            "\n"
            "产品标准中技术要求为必备要素。\n"
            "\n"
            "<!--ssir:foot:2-->这种情况，该标准属于“分类标准”，不属于产品标准。<!--ssir:/foot-->\n"
            "\n"
            "## 7 其它要素\n"
            "\n"
            "7.1 内容。\n"
        )
        blocks, issues = _parse(body)
        notes = [b for b in blocks if b.kind == "footnote"]
        self.assertEqual(len(notes), 1)
        idx = blocks.index(notes[0])
        prev = blocks[idx - 1]
        self.assertEqual(prev.kind, "paragraph")
        self.assertIn("6.4.2", prev.text)
        self.assertIn("[foot:2]", prev.text)
        self.assertTrue(any(b.kind == "heading" and "6.5" in b.text for b in blocks))

    def test_relocation_skips_without_unique_anchor(self) -> None:
        # 反例 1：正文无该标记（悬空定义）→ footnote 留在原位。
        body1 = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 5 条文\n"
            "\n"
            "正文内容。\n"
            "\n"
            "<!--ssir:foot:7-->没有对应锚点的悬空定义。<!--ssir:/foot-->\n"
        )
        blocks1, _ = _parse(body1)
        notes1 = [b for b in blocks1 if b.kind == "footnote"]
        self.assertEqual(len(notes1), 1)
        self.assertIs(blocks1[-1], notes1[0])  # 原位保留
        # 反例 2：正文多处引用该标记 → 不搬（无法确定唯一锚点）。
        body2 = (
            "# 标准编写规则 第10部分：产品标准\n"
            "\n"
            "## 5 条文\n"
            "\n"
            "甲处引用[foot:3]。\n"
            "\n"
            "乙处再引用[foot:3]。\n"
            "\n"
            "<!--ssir:foot:3-->定义文本。<!--ssir:/foot-->\n"
        )
        blocks2, _ = _parse(body2)
        notes2 = [b for b in blocks2 if b.kind == "footnote"]
        self.assertEqual(len(notes2), 1)
        self.assertIs(blocks2[-1], notes2[0])  # 仍在文末原位


if __name__ == "__main__":
    unittest.main()
