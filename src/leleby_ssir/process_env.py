"""子进程代理环境规整（GEN-132）。

MinerU 3.x 的 CLI（`mineru` 命令）不直接跑推理：它先起一个本地 mineru-api
（127.0.0.1 随机端口），再用 httpx 与它通信。httpx 在**构造客户端时**就把环境里的
每个代理变量解析成 Proxy 对象，只接受 http / https / socks5 / socks5h 四种方案，
其余一律 `ValueError: Unknown scheme for proxy URL …`——于是调用方 shell 里一个
`socks://127.0.0.1:7897/`（Clash 等工具设「系统代理（SOCKS）」时的写法）就能让整次
抽取在启动阶段直接 traceback 失败（2026-09-23 用户报告 JB_T_14425-2023 抽取失败）。

本模块给出**面向问题类**的通用规整（规则对应: GEN-132，2026-09-23）：

1. `socks://` → `socks5://`：curl/urllib 同义的 SOCKS5 别名，httpx 只认后者；
2. 其余 httpx 无法使用的方案（`socks4://`、`ftp://`…）删除该变量——留着必然崩，
   删掉只是这一项代理失效（模型已在本地缓存，抽取本身不需要外网）；
3. 回环地址（localhost / 127.0.0.1 / ::1）写进 `NO_PROXY`：本地 mineru-api 的
   通信通道不该经过任何代理。

规整只作用于交给子进程的 env **副本**，绝不改 `os.environ`；无可规整项时值原样
保留（连大小写都不动）。urllib 读代理变量时同 scheme 有大小写优先级（小写优先），
所以同名的大小写两种变量都要各自规整，不能只挑一个。
"""

from __future__ import annotations

from typing import MutableMapping

# httpx 0.28 的 _config.Proxy 白名单（其余方案在客户端构造期抛 ValueError）。
HTTPX_PROXY_SCHEMES = frozenset({"http", "https", "socks5", "socks5h"})
# 保义别名：curl/urllib 把 socks:// 当 SOCKS5，httpx 不认这个写法。
PROXY_SCHEME_ALIASES = {"socks": "socks5"}
# 本地 mineru-api 走回环，必须绕开代理。
LOOPBACK_BYPASS = ("localhost", "127.0.0.1", "::1")


def _normalize_proxy_url(value: str) -> str | None:
    """规整单个代理变量值；返回 None 表示该方案 httpx 无法使用（应删除该变量）。"""
    scheme, separator, rest = value.partition("://")
    if not separator:
        # 裸 host:port：httpx 自己补 http://，不需要动。
        return value
    lowered = scheme.lower()
    if lowered in HTTPX_PROXY_SCHEMES:
        return value  # 原样保留（含大小写）
    alias = PROXY_SCHEME_ALIASES.get(lowered)
    if alias:
        return f"{alias}://{rest}"
    return None


def _with_loopback_bypass(value: str) -> tuple[str, list[str]]:
    """把缺失的回环地址追加到 NO_PROXY 列表；返回（新值, 变更说明）。"""
    entries = [item.strip() for item in value.split(",") if item.strip()]
    known = {item.lower() for item in entries}
    added = [host for host in LOOPBACK_BYPASS if host.lower() not in known]
    if not added:
        return value, []
    return ",".join(entries + added), [
        f"added loopback bypass {', '.join(added)} to NO_PROXY"
    ]


def normalize_proxy_environment(env: MutableMapping[str, str]) -> list[str]:
    """就地规整 env 里的代理变量，返回人类可读的变更说明（无变更时为空表）。"""
    notes: list[str] = []
    no_proxy_names: list[str] = []
    has_proxy = False
    for name in list(env):
        lowered = name.lower()
        if not lowered.endswith("_proxy"):
            continue
        value = (env.get(name) or "").strip()
        if not value:
            continue
        if lowered == "no_proxy":
            no_proxy_names.append(name)
            continue
        has_proxy = True
        normalized = _normalize_proxy_url(value)
        if normalized is None:
            env.pop(name, None)
            notes.append(
                f"dropped {name}={value!r}: httpx（MinerU CLI 用它访问本地 mineru-api）"
                "无法使用该代理方案"
            )
        elif normalized != value:
            env[name] = normalized
            notes.append(f"rewrote {name}={value!r} -> {normalized!r}: socks:// 是 SOCKS5 的别名")

    if no_proxy_names:
        for name in no_proxy_names:
            updated, changes = _with_loopback_bypass(env.get(name) or "")
            if changes:
                env[name] = updated
                notes.append(f"{name}={updated!r}: {changes[0]}")
    elif has_proxy:
        # 一个代理都不规整就永远读不到 NO_PROXY：本地 mineru-api 会被送进代理。
        env["NO_PROXY"] = ",".join(LOOPBACK_BYPASS)
        notes.append(f"set NO_PROXY={env['NO_PROXY']!r}: 本地 mineru-api 走回环，不得经过代理")
    return notes
