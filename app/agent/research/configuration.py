from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig


@dataclass(kw_only=True)
class Configuration:
    question_generator_model: str = "claude-haiku-4-5-20251001"
    max_search_results: int = 5

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "Configuration":
        configurable = (config or {}).get("configurable", {})
        return cls(**{k: v for k, v in configurable.items() if k in cls.__dataclass_fields__})  # pylint: disable=no-member
