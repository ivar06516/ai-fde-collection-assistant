"""Agent modules."""
import re


def parse_llm_json(content: str) -> str:
    """Strip markdown fences from LLM response and return clean JSON string."""
    content = content.strip()
    content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
    content = re.sub(r"```\s*$", "", content)
    return content.strip()
