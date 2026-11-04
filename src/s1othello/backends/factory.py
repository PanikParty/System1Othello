"""Backend construction from a name plus optional configs/backends/<name>.yaml.
Mirrors System1Doom's factory, so the config convention and CLI habits carry over.

An HTTP backend's url can be overridden with $<NAME>_URL (e.g. CLEF_FLASH_URL), so one
config works both on the model host (127.0.0.1) and across the LAN.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from s1othello.backends.base import BackendError, DecisionBackend

CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "backends"
KINDS = ("heuristic", "greedy", "random", "minimax", "jev", "systemone-http", "laya-http", "router")
JEV_URL = "https://api.typesafe.ai/v1/systemone"


def backend_config(name: str) -> dict:
    p = CONFIG_DIR / f"{name}.yaml"
    cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
    cfg.setdefault("kind", name)
    return cfg


def _url(name: str, cfg: dict, default: str | None = None) -> str:
    env = name.upper().replace("-", "_") + "_URL"
    url = os.environ.get(env) or cfg.get("url") or default
    if not url:
        raise BackendError(f"{name}: no url (set it in configs/backends/{name}.yaml or ${env})")
    return url


def make_backend(name: str, seed: int | None = None) -> DecisionBackend:
    cfg = backend_config(name)
    kind = cfg["kind"]
    if kind == "heuristic":
        from s1othello.backends.heuristic import HeuristicBackend

        return HeuristicBackend()
    if kind == "greedy":
        from s1othello.backends.greedy import GreedyBackend

        return GreedyBackend()
    if kind == "random":
        from s1othello.backends.random_ import RandomBackend

        return RandomBackend(seed)
    if kind == "minimax":
        from s1othello.backends.minimax import MinimaxBackend
        from s1othello.solver import EXACT_EMPTIES

        return MinimaxBackend(depth=cfg.get("depth", 4), exact_empties=cfg.get("exact_empties", EXACT_EMPTIES),
                              name=name)
    if kind == "jev":
        from s1othello.backends.http import SystemOneHTTP, read_key

        key = read_key("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_FILE", cfg.get("key_file", "Jev.key"))
        if not key:
            raise BackendError("jev needs TYPESAFE_API_KEY (env) or a key file "
                               "(TYPESAFE_API_KEY_FILE, default ./Jev.key)")
        return SystemOneHTTP(name, _url(name, cfg, JEV_URL), cfg.get("model", "jev-latest"), key,
                             timeout_s=cfg.get("timeout_s", 10.0))
    if kind in ("systemone-http", "laya-http"):
        # any Jev-compatible /v1/systemone server: Laya, Clef, Clef-Flash, SemIf
        from s1othello.backends.http import SystemOneHTTP, read_key

        env = cfg.get("key_env", "SYSTEMONE_API_KEY")
        key = read_key(env, f"{env}_FILE", None)
        return SystemOneHTTP(name, _url(name, cfg), cfg.get("model"), key, timeout_s=cfg.get("timeout_s", 30.0))
    if kind == "router":
        from s1othello.backends.router import RouterBackend

        return RouterBackend(make_backend(cfg["model_backend"], seed), make_backend(cfg["search_backend"], seed),
                             mode=cfg.get("mode", "gate"), threshold=cfg.get("threshold", 0.5),
                             top_k=cfg.get("top_k", 3), name=name)
    raise ValueError(f"unknown backend {name!r} (kinds: {KINDS})")
