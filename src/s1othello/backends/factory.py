"""Backend construction from a name (+ optional configs/backends/<name>.yaml).
Mirrors System1Doom's factory so the same config convention/CLI muscle memory
carries over."""
from __future__ import annotations

from pathlib import Path

import yaml

from s1othello.backends.base import DecisionBackend

CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "backends"
KINDS = ("jev", "laya-http", "systemone-http", "heuristic", "random", "minimax")


def backend_config(name: str) -> dict:
    p = CONFIG_DIR / f"{name}.yaml"
    cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
    cfg.setdefault("kind", name)
    return cfg


def make_backend(name: str, url: str | None = None, seed: int | None = None) -> DecisionBackend:
    cfg = backend_config(name)
    kind = cfg["kind"]
    if kind == "heuristic":
        from s1othello.backends.heuristic import HeuristicBackend

        return HeuristicBackend()
    if kind == "random":
        from s1othello.backends.random_ import RandomBackend

        return RandomBackend(seed)
    if kind == "minimax":
        from s1othello.backends.minimax import MinimaxBackend

        return MinimaxBackend(depth=cfg.get("depth", 6))
    if kind == "jev":
        from s1othello.backends.http import SystemOneHTTP, read_key

        key = read_key("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_FILE", cfg.get("key_file", "Jev.key"))
        return SystemOneHTTP("jev", url or cfg.get("url", "https://api.typesafe.ai/v1/systemone"),
                             cfg.get("model", "jev-latest"), key, timeout_s=cfg.get("timeout_s", 10.0))
    if kind in ("laya-http", "systemone-http"):
        # any Jev-compatible /v1/systemone server: Laya, Clef, Clef-Flash, SemIf
        from s1othello.backends.http import SystemOneHTTP, read_key

        b = SystemOneHTTP(cfg.get("name", name), url or cfg["url"], cfg.get("model"),
                          read_key(cfg.get("key_env", "SYSTEMONE_API_KEY"), "SYSTEMONE_API_KEY_FILE", None),
                          timeout_s=cfg.get("timeout_s", 10.0))
        return b
    raise ValueError(f"unknown backend {name!r} (kinds: {KINDS})")
