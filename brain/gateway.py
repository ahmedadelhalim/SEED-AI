
from brain.model_gateway import ModelGateway
from brain.model_types import ModelRequest

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:4b"


def ask_seedo(prompt: str) -> str:
    gateway = ModelGateway.with_local_defaults(
        ollama_base_url=OLLAMA_URL.rsplit("/api/chat", 1)[0]
    )
    response = gateway.complete(ModelRequest(
        messages=({"role": "user", "content": prompt},),
        model=MODEL,
        provider="ollama",
    ))
    return response.content


if __name__ == "__main__":
    print(
        "SEEDO:",
        ask_seedo("Reply with exactly: SEED_GATEWAY_OPERATIONAL")
    )
