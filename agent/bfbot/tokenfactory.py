import json
import os
import random
from pathlib import Path
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

T = TypeVar("T", bound=BaseModel)

MODELS = {
    "nano": os.getenv("BFBOT_MODEL_NANO", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
    "super": os.getenv("BFBOT_MODEL_SUPER", "nvidia/nemotron-3-super-120b-a12b"),
    "ultra": os.getenv("BFBOT_MODEL_ULTRA", "nvidia/Nemotron-3-Ultra-550b-a55b"),
}


class TokenFactoryClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("NEBIUS_API_KEY", "")
        self.base_url = os.getenv(
            "NEBIUS_TF_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
        )
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls: list[dict] = []

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    def chat(self, tier: str, messages: list[dict], temperature: float = 0.0) -> str:
        model = MODELS[tier]
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        self.total_input_tokens += resp.usage.prompt_tokens
        self.total_output_tokens += resp.usage.completion_tokens
        self.calls.append(
            {
                "tier": tier,
                "model": model,
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        )
        content = resp.choices[0].message.content or ""
        Path(".bfbot").mkdir(parents=True, exist_ok=True)
        (
            Path(".bfbot") / "last_reasoning.json"
        ).write_text(
            json.dumps(
                {
                    "tier": tier,
                    "reasoning_content": getattr(resp.choices[0].message, "reasoning_content", None)
                    or getattr(resp.choices[0].message, "reasoning", None),
                }
            ),
            encoding="utf-8",
        )
        return content

    def structured(self, tier: str, schema: Type[T], messages: list[dict]) -> T:
        model = MODELS[tier]
        use_reasoning = tier in ("super", "ultra")
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
            extra_body={
                "chat_template_kwargs": {"enable_thinking": use_reasoning},
            },
        )
        self.total_input_tokens += resp.usage.prompt_tokens
        self.total_output_tokens += resp.usage.completion_tokens
        self.calls.append(
            {
                "tier": tier,
                "model": model,
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "structured": schema.__name__,
            }
        )
        return schema.model_validate_json(resp.choices[0].message.content or "{}")

    def usage_report(self) -> dict:
        pricing = {
            "nano": (0.06, 0.24),
            "super": (0.30, 0.90),
            "ultra": (1.00, 3.00),
        }
        cost = 0.0
        for call in self.calls:
            p = pricing[call["tier"]]
            cost += (
                call["input_tokens"] / 1_000_000 * p[0]
                + call["output_tokens"] / 1_000_000 * p[1]
            )
        return {
            "calls": self.calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(cost, 6),
        }


class MockTokenFactoryClient(TokenFactoryClient):
    def __init__(self) -> None:
        object.__setattr__(self, "client", None)
        self.api_key = ""
        self.base_url = ""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls: list[dict] = []

    @property
    def live(self) -> bool:
        return False

    def _record(self, tier: str, schema_name: str | None, text: str) -> None:
        self.calls.append(
            {
                "tier": tier,
                "model": f"mock::{tier}",
                "input_tokens": random.randint(120, 900),
                "output_tokens": random.randint(40, 400),
                **({"structured": schema_name} if schema_name else {}),
            }
        )

    def chat(self, tier: str, messages: list[dict], temperature: float = 0.0) -> str:
        self._record(tier, None, "")
        return f"[mock:{tier}] {messages[-1]['content'][:80]}"

    def structured(self, tier: str, schema: Type[T], messages: list[dict]) -> T:
        self._record(tier, schema.__name__, "")
        sample_fields = {
            name: field
            for name, field in
            schema.model_fields.items()
        }
        data = {}
        for name, field in sample_fields.items():
            annotation = str(field.annotation)
            if "bool" in annotation:
                data[name] = True
            elif "int" in annotation:
                data[name] = 3
            elif "float" in annotation:
                data[name] = 0.5
            elif "list" in annotation or "List" in annotation:
                data[name] = ["mock-item-1"]
            elif "dict" in annotation or "Dict" in annotation:
                data[name] = {"mock": True}
            else:
                data[name] = f"[mock:{schema.__name__}.{name}]"
        try:
            return schema.model_validate(data)
        except Exception:
            return schema.model_construct(**data)

    def usage_report(self) -> dict:
        return {
            "calls": self.calls,
            "total_input_tokens": sum(c["input_tokens"] for c in self.calls),
            "total_output_tokens": sum(c["output_tokens"] for c in self.calls),
            "estimated_cost_usd": 0.0,
        }
