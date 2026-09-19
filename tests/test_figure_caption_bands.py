"""GEN-112：图块 bbox 越界圈入的题注像素 → 图资产裁到题注上边界。

现象（2026-09-19 用户报告：GB_T_30819-2024 4.1.8 的 4 张图只有第 3 张显示了图下名称）：
MinerU 把 c 分图的图块 bbox 画到了题注行里（图块 y∈[96,312]、题注行 y∈[301,314]），
裁剪图因此带着题注像素；渲染端按 GBT-B06 再排一次题注，图上图下就成了两条同样的
「c) Ⅲ型」。修复：``pipeline._trim_figure_caption_bands`` 按 ``middle.json`` 的几何把
资产裁到题注上边界（目标像素高由几何与该资产**宽向**密度算出 → 幂等）。

断言全部落在真实文件上：像素尺寸变化、幂等、无几何时不动作。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.pipeline import _trim_figure_caption_bands  # noqa: E402

# 实测几何：GB_T_30819-2024 p10 图3 的 c 分图（宽 115pt、高 216pt、题注带上沿 301 → 压缩 11pt）
BLOCK_BBOX = [293.0, 96.0, 408.0, 312.0]
CAPTION_BBOX = [327.0, 301.0, 368.0, 314.0]
ASSET_NAME = "c.png"
ASSET_PIXELS = (300, 600)


def _middle(caption_bbox: list[float] | None = CAPTION_BBOX) -> dict:
    inner: list[dict] = [
        {"type": "image_body", "bbox": BLOCK_BBOX,
         "lines": [{"spans": [{"type": "image", "image_path": f"https://cdn.example/{ASSET_NAME}"}]}]}
    ]
    if caption_bbox is not None:
        inner.append({"type": "image_caption", "bbox": caption_bbox,
                      "lines": [{"spans": [{"type": "text", "content": "c) Ⅲ型"}]}]})
    return {"pdf_info": [{"page_idx": 10, "para_blocks": [{"type": "image", "bbox": BLOCK_BBOX, "blocks": inner}]}]}


class FigureCaptionBandTrimTests(unittest.TestCase):
    def _docroot(self, directory: Path, *, provenance: bool = True, middle: dict | None = None) -> Path:
        from PIL import Image as PILImage

        (directory / "01_extract").mkdir(parents=True, exist_ok=True)
        (directory / "03_ssir").mkdir(parents=True, exist_ok=True)
        (directory / "assets" / "images").mkdir(parents=True, exist_ok=True)
        middle_path = directory / "layout.json"
        middle_path.write_text(json.dumps(middle if middle is not None else _middle()), encoding="utf-8")
        if provenance:
            (directory / "01_extract" / "t.provenance.json").write_text(
                json.dumps({"inputFormat": "middle-json", "sourceRaw": str(middle_path)}), encoding="utf-8")
        PILImage.new("RGB", ASSET_PIXELS, (255, 255, 255)).save(directory / "assets" / "images" / ASSET_NAME)
        (directory / "03_ssir" / "t.ssir.json").write_text(
            json.dumps({"figures": [{"id": "f1", "assetRef": f"assets/images/{ASSET_NAME}"}]}), encoding="utf-8")
        return directory / "03_ssir" / "t.ssir.json"

    def _size(self, path: Path) -> tuple[int, int]:
        from PIL import Image as PILImage

        with PILImage.open(path) as image:
            return image.size

    def test_asset_is_trimmed_to_the_caption_band(self) -> None:
        from PIL import Image as PILImage

        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            ssir = self._docroot(directory)
            asset = directory / "assets" / "images" / ASSET_NAME
            self.assertEqual(_trim_figure_caption_bands(ssir), 1)
            width, height = self._size(asset)
            # 目标高 = 有效高(205pt) × 宽向密度(300px/115pt) ≈ 535px
            self.assertEqual((width, height), (300, 535))
            # 幂等：几何不变 → 再跑不动文件
            self.assertEqual(_trim_figure_caption_bands(ssir), 0)
            self.assertEqual(self._size(asset), (300, 535))
            with PILImage.open(asset) as image:
                self.assertEqual(image.format, "JPEG" if asset.suffix == ".jpg" else "PNG")

    def test_caption_below_the_block_leaves_the_asset_alone(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            ssir = self._docroot(directory, middle=_middle(caption_bbox=[327, 320, 368, 333]))
            asset = directory / "assets" / "images" / ASSET_NAME
            self.assertEqual(_trim_figure_caption_bands(ssir), 0)
            self.assertEqual(self._size(asset), ASSET_PIXELS)

    def test_no_provenance_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            ssir = self._docroot(directory, provenance=False)
            asset = directory / "assets" / "images" / ASSET_NAME
            self.assertEqual(_trim_figure_caption_bands(ssir), 0)
            self.assertEqual(self._size(asset), ASSET_PIXELS)

    def test_missing_asset_is_reported_as_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            ssir = self._docroot(directory)
            (directory / "assets" / "images" / ASSET_NAME).unlink()
            self.assertEqual(_trim_figure_caption_bands(ssir), 0)

    def test_asset_shorter_than_the_target_is_left_alone(self) -> None:
        from PIL import Image as PILImage

        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            ssir = self._docroot(directory)
            asset = directory / "assets" / "images" / ASSET_NAME
            PILImage.new("RGB", (300, 400), (255, 255, 255)).save(asset)  # 比目标矮：不放大不裁
            self.assertEqual(_trim_figure_caption_bands(ssir), 0)
            self.assertEqual(self._size(asset), (300, 400))


if __name__ == "__main__":
    unittest.main()
