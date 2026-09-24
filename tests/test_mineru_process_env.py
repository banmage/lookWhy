"""GEN-132：MinerU 子进程的代理环境规整回归夹具。

背景（2026-09-23，用户报告 `tools/mineru_full_standard.py JB_T_14425-2023.pdf` 出错）：
MinerU 3.4.5 的 CLI 先起本地 mineru-api（127.0.0.1）再用 httpx 与它通信，而 httpx
在**构造客户端时**解析环境里每个代理变量，只接受 http/https/socks5/socks5h 四种方案，
其余直接 `ValueError: Unknown scheme for proxy URL`——调用方 shell 里一个
`all_proxy=socks://127.0.0.1:7897/`（代理工具设「系统代理（SOCKS）」时的写法）就让整次
抽取在启动阶段 traceback 失败，退出码 1。

本文件锁四件事：
① 规整判据（socks:// → socks5://；不可用方案删除该变量；合法方案与裸 host:port 原样；
   回环地址进 NO_PROXY）；② 规整后的 env 确实能被 httpx 接受、规整前确实抛错（真实
   httpx 构造，不是字符串断言）；③ 工具侧 `_mineru_env()` 不改 os.environ；④ 抽取
   阶段的子进程真的拿到规整后的 env（stub 掉 subprocess.run 断言 env 实参）。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from leleby_ssir.process_env import normalize_proxy_environment  # noqa: E402

import mineru_full_standard as mfs  # noqa: E402

# 用户环境的形态：Clash 设「系统代理（SOCKS）」写出 socks://，NO_PROXY 只列 localhost。
HOSTILE_PROXY_ENV = {
    "ALL_PROXY": "socks://127.0.0.1:7897/",
    "all_proxy": "socks://127.0.0.1:7897/",
    "http_proxy": "http://127.0.0.1:7897/",
    "NO_PROXY": "localhost",
    "no_proxy": "localhost",
}


def _synthetic_pdf(directory: Path) -> Path:
    """合成真实中文文本层 PDF（pymupdf 内置 CJK 字体；helv 无中文字形）。"""
    import pymupdf

    path = directory / "JB_T_14425-2023.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), "机械行业标准", fontname="china-s", fontsize=12)
    page.insert_text((72, 130), "JB/T 14425—2023", fontname="china-s", fontsize=12)
    document.save(str(path))
    document.close()
    return path


def _extract_args(directory: Path, pdf: Path) -> argparse.Namespace:
    return argparse.Namespace(
        input=pdf,
        output_dir=directory,
        state_file=directory / "pipeline-state.json",
        chunk_size=18,
        method="auto",
        standard_number=None,
        output_stem=None,
        hybrid_tables=False,
        hf_endpoint=None,
    )


class ProxyNormalizationTests(unittest.TestCase):
    """判据层：只测纯函数。"""

    def test_socks_alias_is_rewritten_to_socks5(self) -> None:
        env = {"all_proxy": "socks://127.0.0.1:7897/"}
        notes = normalize_proxy_environment(env)
        self.assertEqual(env["all_proxy"], "socks5://127.0.0.1:7897/")
        self.assertTrue(any("socks5://" in note for note in notes))

    def test_uppercase_variant_is_rewritten_too(self) -> None:
        # urllib 的代理变量读取按大小写两轮，小写优先——同名两种变量都要规整。
        env = {"ALL_PROXY": "SOCKS://127.0.0.1:7897/"}
        normalize_proxy_environment(env)
        self.assertEqual(env["ALL_PROXY"], "socks5://127.0.0.1:7897/")

    def test_unsupported_scheme_is_dropped_not_left_to_crash(self) -> None:
        env = {"all_proxy": "socks4://127.0.0.1:1080/", "https_proxy": "http://proxy:8080/"}
        notes = normalize_proxy_environment(env)
        self.assertNotIn("all_proxy", env)
        self.assertEqual(env["https_proxy"], "http://proxy:8080/")
        self.assertTrue(any("dropped all_proxy" in note for note in notes))

    def test_supported_schemes_and_bare_host_port_are_untouched(self) -> None:
        env = {
            "http_proxy": "http://127.0.0.1:7897/",
            "HTTPS_PROXY": "HTTPS://proxy:8080/",  # 大小写原样保留
            "all_proxy": "socks5h://127.0.0.1:7897/",
            "no_proxy": "localhost,127.0.0.1,::1",
            "HTTP_PROXY": "",
        }
        before = dict(env)
        notes = normalize_proxy_environment(env)
        self.assertEqual(env, before)
        self.assertEqual(notes, [])

    def test_loopback_bypass_is_appended_once(self) -> None:
        env = {"all_proxy": "socks5://127.0.0.1:7897/", "NO_PROXY": "localhost,example.com"}
        notes = normalize_proxy_environment(env)
        self.assertEqual(env["NO_PROXY"], "localhost,example.com,127.0.0.1,::1")
        self.assertTrue(any("127.0.0.1" in note for note in notes))
        # 幂等：再跑一次不再改
        again = normalize_proxy_environment(env)
        self.assertEqual(env["NO_PROXY"], "localhost,example.com,127.0.0.1,::1")
        self.assertEqual(again, [])

    def test_loopback_bypass_is_created_when_absent(self) -> None:
        env = {"all_proxy": "socks5://127.0.0.1:7897/"}
        normalize_proxy_environment(env)
        self.assertEqual(env["NO_PROXY"], "localhost,127.0.0.1,::1")

    def test_no_proxy_is_not_invented_without_any_proxy(self) -> None:
        env = {"PATH": "/usr/bin", "NO_PROXY": ""}
        notes = normalize_proxy_environment(env)
        self.assertEqual(env, {"PATH": "/usr/bin", "NO_PROXY": ""})
        self.assertEqual(notes, [])


class HttpxConstructionTests(unittest.TestCase):
    """失败现场复现：httpx 构造客户端时对代理方案白名单。"""

    def _construct(self, env: dict[str, str]) -> str:
        import httpx

        with mock.patch.dict(os.environ, env, clear=True):
            try:
                httpx.AsyncClient(timeout=5, follow_redirects=True)
            except ValueError as exc:
                return str(exc)
        return ""

    def test_hostile_env_makes_httpx_raise_the_reported_error(self) -> None:
        error = self._construct(HOSTILE_PROXY_ENV)
        self.assertIn("Unknown scheme for proxy URL", error)
        self.assertIn("socks://127.0.0.1:7897/", error)

    def test_sanitized_env_constructs_the_client(self) -> None:
        env = dict(HOSTILE_PROXY_ENV)
        normalize_proxy_environment(env)
        self.assertEqual(self._construct(env), "")


class ToolEnvironmentTests(unittest.TestCase):
    """工具层：交给 MinerU 子进程的 env。"""

    def test_mineru_env_sanitizes_without_touching_os_environ(self) -> None:
        with mock.patch.dict(os.environ, HOSTILE_PROXY_ENV):
            env = mfs._mineru_env({"HF_ENDPOINT": "https://hf-mirror.com"})
            self.assertEqual(env["all_proxy"], "socks5://127.0.0.1:7897/")
            self.assertEqual(env["ALL_PROXY"], "socks5://127.0.0.1:7897/")
            self.assertIn("127.0.0.1", env["NO_PROXY"])
            self.assertIn("::1", env["NO_PROXY"])
            self.assertEqual(env["HF_ENDPOINT"], "https://hf-mirror.com")
            # os.environ 不动（规整只作用于副本）
            self.assertEqual(os.environ["ALL_PROXY"], "socks://127.0.0.1:7897/")

    def test_extract_passes_the_sanitized_env_to_mineru(self) -> None:
        seen: list[dict[str, str]] = []

        def fake_run(invocation, cwd=None, env=None, **kwargs):  # noqa: ANN001
            seen.append(env or {})
            part = Path(invocation[invocation.index("-o") + 1])
            part.mkdir(parents=True, exist_ok=True)
            (part / "JB_T_14425-2023.md").write_text("# 机械行业标准\n", encoding="utf-8")
            return subprocess.CompletedProcess(invocation, 0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = _synthetic_pdf(root)
            args = _extract_args(root / "out", pdf)
            with mock.patch.dict(os.environ, HOSTILE_PROXY_ENV), \
                    mock.patch.object(mfs, "_mineru_command", return_value="/usr/bin/mineru"), \
                    mock.patch.object(mfs.subprocess, "run", side_effect=fake_run):
                mfs.extract(args, {})

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["all_proxy"], "socks5://127.0.0.1:7897/")
        self.assertEqual(seen[0]["http_proxy"], "http://127.0.0.1:7897/")


if __name__ == "__main__":
    unittest.main()
