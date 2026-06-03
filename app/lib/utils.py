from pathlib import Path
import json
def load_prompt(path: str, **kwargs) -> str:
    text = Path(path).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text

def load_profile() -> dict:
    path = Path(__file__).parents[2] / "data" / "user-profile.json"
    return json.loads(path.read_text(encoding="utf-8"))