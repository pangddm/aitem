import asyncio

from app.llm.embedding.jina import JinaEmbedding


async def main():

    embedding = JinaEmbedding()

    vector = await embedding.embed(
        "用户喜欢使用nerdctl"
    )

    print(len(vector))

    print(vector[:10])


if __name__ == "__main__":

    asyncio.run(main())