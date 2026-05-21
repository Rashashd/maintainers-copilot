from app.infra.inference_client import get_inference_client


async def run(args: dict) -> str:
    client = get_inference_client()
    result = await client.summarize(
        text=args["text"],
        max_sentences=args.get("max_sentences", 3),
    )
    return result.summary
