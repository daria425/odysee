from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig


@dataclass(kw_only=True)
class Configuration:
    question_generator_model: str = "claude-haiku-4-5-20251001"
    research_model: str = "claude-haiku-4-5-20251001"
    synthesis_model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-sonnet-4-6"
    max_search_results: int = 5
    max_reflections: int = 2

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "Configuration":
        configurable = (config or {}).get("configurable", {})
        return cls(**{k: v for k, v in configurable.items() if k in cls.__dataclass_fields__})  # pylint: disable=no-member
