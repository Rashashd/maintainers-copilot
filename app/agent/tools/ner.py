import json

from app.infra.inference_client import get_inference_client


async def run(args: dict) -> str:
    client = get_inference_client()
    result = await client.ner(text=args["text"])
    entities = [
        {"text": e.text, "label": e.label, "score": round(e.score, 3)}
        for e in result.entities
    ]
    return json.dumps({"entities": entities})
