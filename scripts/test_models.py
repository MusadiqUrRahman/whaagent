"""Test which Z.ai model names are available on your API key/endpoint.

Reads OPENAI_API_KEY and OPENAI_BASE_URL from .env and tests each model
with a minimal chat completion request.
"""

import os
import time

import dotenv
from openai import OpenAI

dotenv.load_dotenv()

MODELS = [
    # Flagship / Latest
    "glm-5.1",
    "glm-5",
    "glm-5-turbo",
    # GLM-4.7 family
    "glm-4.7",
    "glm-4.7-flashx",
    "glm-4.7-flash",
    # GLM-4.6
    "glm-4.6",
    # GLM-4.5 family
    "glm-4.5",
    "glm-4.5-x",
    "glm-4.5-air",
    "glm-4.5-airx",
    "glm-4.5-flash",
    # Older
    "glm-4-32b-0414-128k",
]

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)


def test_model(model: str) -> tuple[bool, str]:
    try:
        start = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
            temperature=0.1,
        )
        elapsed = time.time() - start
        text = resp.choices[0].message.content.strip()[:40]
        return True, f"{elapsed:.1f}s  \"{text}\""
    except Exception as e:
        msg = str(e)[:80]
        return False, msg


if __name__ == "__main__":
    print(f"Endpoint: {os.getenv('OPENAI_BASE_URL')}\n")
    print(f"{'Model':<25} {'Status':<6} {'Details'}")
    print("-" * 80)

    for model in MODELS:
        ok, detail = test_model(model)
        status = "  OK" if ok else "  NOK"
        print(f"{model:<25} {status:<6} {detail}")
