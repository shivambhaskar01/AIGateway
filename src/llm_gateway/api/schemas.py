"""HTTP schemas. Validation failures are answered without echoing the body."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_gateway.config import MAX_PROMPT_CHARS


class GenerateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    tier: Literal["auto", "fast", "strong"] = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    cache: bool = True
