import json
import logging
import os
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from a2ui.core.basic_catalog import BasicCatalog, SPEC_VERSION, _basic_catalog_id
from a2ui.core.validating.catalog_schema_validator import CatalogSchemaValidator
from a2ui.core.validating.validator import A2uiValidator, STRICT_VALIDATION

from app.lib.utils import load_prompt

logger = logging.getLogger(__name__)

REPORT_UI_MODEL = "claude-haiku-4-5-20251001"
BASIC_CATALOG_ID = _basic_catalog_id(SPEC_VERSION)
MAX_ATTEMPTS = 3

_catalog = BasicCatalog()
_schema_validator = CatalogSchemaValidator(_catalog)
_validator = A2uiValidator()


class ReportUiGenerationError(Exception):
    """Raised when the model fails to produce a valid A2UI payload after all retries."""


def _extract_json(text: str) -> list[dict]:
    """Parses the model's raw text output into a list of component dicts, tolerating
    markdown code fences and smart quotes the way A2UI reference parsers do."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    candidate = candidate.replace("“", '"').replace("”", '"')
    parsed = json.loads(candidate)
    if not isinstance(parsed, list):
        raise ValueError("expected a JSON array of components")
    return parsed


def _build_payload(surface_id: str, components: list[dict]) -> list[dict]:
    return [
        {"version": SPEC_VERSION, "createSurface": {"surfaceId": surface_id, "catalogId": BASIC_CATALOG_ID}},
        {"version": SPEC_VERSION, "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


def generate_report_ui(report: str, surface_id: str, config: RunnableConfig | None = None) -> str:
    """Compiles a trip report (Markdown) into A2UI protocol messages, returned as a JSON string.

    Generation is unconstrained plain-text (no provider-side structured output — Anthropic's strict
    schema mode rejects the full basic-catalog schema as "too large to compile"). Validity is instead
    enforced client-side against the real catalog schema, with retries that feed the validation error
    back to the model.
    """
    llm = ChatAnthropic(
        model_name=REPORT_UI_MODEL, temperature=0,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
    system_prompt = load_prompt("app/lib/prompts/generate_report_ui_prompt.txt")
    messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=report)]

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = llm.invoke(messages, config)
        try:
            components = _extract_json(response.content)
            payload = _build_payload(surface_id, components)
            _validator.validate(_schema_validator, payload, config=STRICT_VALIDATION)
            logger.info(
                "[generate_report_ui] surface=%s components=%d attempt=%d",
                surface_id, len(components), attempt,
            )
            return json.dumps(payload)
        except Exception as e:
            last_error = e
            logger.warning(
                "[generate_report_ui] attempt=%d/%d failed surface=%s error=%s",
                attempt, MAX_ATTEMPTS, surface_id, e,
            )
            messages.append(AIMessage(content=response.content))
            messages.append(HumanMessage(
                content=f"That output was invalid: {e}\n\nFix it and return the corrected JSON array only."
            ))

    raise ReportUiGenerationError(
        f"failed to generate valid A2UI for surface={surface_id} after {MAX_ATTEMPTS} attempts: {last_error}"
    )
