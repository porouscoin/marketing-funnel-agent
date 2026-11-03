"""Settings and the model registry, all read from environment variables."""

import os
from dataclasses import dataclass


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class ModelSpec:
    id: str  # short name used in config and logs, e.g. "gemini"
    label: str  # what visitors see
    provider: str  # "gemini" | "groq" | "mock"
    model: str  # the provider's model name
    base_url: str
    api_key: str


def _groq(id: str, label: str, model: str) -> ModelSpec:
    return ModelSpec(id, label, "groq", model, "https://api.groq.com/openai/v1", env("GROQ_API_KEY"))


def model_registry() -> dict[str, ModelSpec]:
    """Only models whose API key is set are used."""
    specs = [
        ModelSpec(
            id="gemini",
            label=env("GEMINI_LABEL", "Gemini 3.5 Flash Lite"),
            provider="gemini",
            model=env("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=env("GEMINI_API_KEY"),
        ),
        _groq("qwen", "Qwen3.8 27B", env("GROQ_QWEN_MODEL", "qwen/qwen3.8-27b")),
        _groq("gpt-oss-120b", "GPT-OSS 120B", "openai/gpt-oss-120b"),
        _groq("gpt-oss-20b", "GPT-OSS 20B", "openai/gpt-oss-20b"),
    ]
    if env("ENABLE_MOCK_MODEL") == "1":
        specs.append(ModelSpec("mock", "Mock (local testing)", "mock", "mock", "", "mock"))
    return {s.id: s for s in specs if s.api_key}


def _order(name: str, default: str) -> list[str]:
    return [m.strip() for m in env(name, default).split(",") if m.strip()]


@dataclass(frozen=True)
class Settings:
    frontend_origin: str = env("FRONTEND_ORIGIN", "http://localhost:3000")
    frontend_origin_regex: str = env("FRONTEND_ORIGIN_REGEX", r"https://(marketing-)?funnel-agent[a-z0-9-]*\.vercel\.app")
    tavily_key: str = env("TAVILY_API_KEY")
    # Which models do what, in order of preference. If one is rate limited, the next is tried.
    writer_models: tuple[str, ...] = tuple(_order("WRITER_MODELS", "gemini,gpt-oss-120b,qwen,mock"))
    # Buyers are spread over different models so the panel doesn't think with one brain.
    buyer_models: tuple[str, ...] = tuple(_order("BUYER_MODELS", "gemini,gpt-oss-120b,qwen,gpt-oss-20b,mock"))
    bar: float = float(env("SCORE_BAR", "6"))
    runs_per_day: int = int(env("RUNS_PER_DAY", "3"))
    rescores_per_hour: int = int(env("RESCORES_PER_HOUR", "20"))
    runs_per_day_global: int = int(env("RUNS_PER_DAY_GLOBAL", "150"))
    max_text_chars: int = int(env("MAX_TEXT_CHARS", "12000"))


settings = Settings()
