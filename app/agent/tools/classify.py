import json

from app.infra.inference import get_inference_client
from app.infra.tracing import observe


@observe(name="agent.tool.classify_issue")
async def run(args: dict) -> str:
    client = get_inference_client()
    result = await client.classify(
        title=args["title"],
        body=args.get("body", ""),
    )
    return json.dumps({"label": result.label, "scores": result.scores})
