import json

from app.infra.inference_client import get_inference_client


async def run(args: dict) -> str:
    client = get_inference_client()
    result = await client.classify(
        title=args["title"],
        body=args.get("body", ""),
    )
    return json.dumps({"label": result.label, "scores": result.scores})
