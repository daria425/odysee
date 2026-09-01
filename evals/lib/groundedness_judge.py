"""
Shared groundedness judge logic (v1: single combined extract+verify call per report).
Used by both evals/scripts/run_groundedness_judge.py (ad hoc calibration runs) and
evals/scripts/run_groundedness_experiment.py (Langfuse experiment).
"""

import os
from pathlib import Path
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.lib.utils import load_prompt

EVALS_DIR = Path(__file__).parents[1]
PROMPT_PATH = EVALS_DIR / "prompts" / "groundedness_judge_prompt.txt"

JUDGE_MODEL = "claude-sonnet-4-6"


class GroundednessClaim(BaseModel):
    claim: str = Field(description="The extracted factual claim, quoted or closely paraphrased from the report.")
    section: str = Field(description="The report section/heading the claim came from.")
    verdict: Literal["supported", "unsupported", "uncertain"]
    evidence: str = Field(description="What in the raw search results supports, contradicts, or is silent on this claim.")


class GroundednessResult(BaseModel):
    claims: list[GroundednessClaim]


def format_sources(web_research_result: list[dict]) -> str:
    blocks = []
    for item in web_research_result:
        lines = [f"### Q: {item['question']}  (search: {item['search_query']})"]
        for s in item["sources"]:
            lines.append(f"- [{s['title']}]({s['url']}): {s['content']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def run_judge(report_text: str, sources_text: str) -> GroundednessResult:
    llm = ChatAnthropic(
        model_name=JUDGE_MODEL, temperature=0, api_key=os.getenv("ANTHROPIC_API_KEY")
    ).with_structured_output(GroundednessResult)
    system_prompt = load_prompt(str(PROMPT_PATH), report=report_text, sources=sources_text)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Extract and verify every factual claim in the report now."),
    ]
    return llm.invoke(messages)
