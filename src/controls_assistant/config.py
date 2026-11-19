import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    profile: str
    region: str
    model_id_a: str
    model_id_b: str
    default_model_id: str


def load_settings():
    load_dotenv(PROJECT_ROOT / ".env")
    profile = os.getenv("AWS_PROFILE", "")
    if not profile.startswith("vr-"):
        raise SystemExit(f"AWS_PROFILE '{profile}' is not a VR training profile. Stopping.")
    model_a = os.environ["MODEL_ID_A"]
    return Settings(
        profile=profile,
        region=os.environ["AWS_REGION"],
        model_id_a=model_a,
        model_id_b=os.environ["MODEL_ID_B"],
        default_model_id=os.getenv("DEFAULT_MODEL_ID") or model_a,
    )


def load_pricing():
    with open(PROJECT_ROOT / "config" / "pricing.json") as f:
        return json.load(f)
