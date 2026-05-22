from app.infra.inference import get_inference_client
from app.infra.tracing import observe


@observe(name="agent.tool.summarize_issue")
async def run(args: dict) -> str:
    client = get_inference_client()
    result = await client.summarize(
        text=args["text"],
        max_sentences=args.get("max_sentences", 3),
    )
    return result.summary
