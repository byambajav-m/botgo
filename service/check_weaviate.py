import asyncio

import weaviate
import requests, json
from weaviate.collections.classes.config import Configure

async def main():
    client = weaviate.connect_to_local()
    client.connect()

    # await client.collections.delete(name="Question")
    #
    # await client.collections.create(
    #     name="Question",
    #     vector_config=Configure.Vectors.text2vec_ollama(
    #         api_endpoint="http://host.docker.internal:11434",
    #         model="embeddinggemma",
    #     ),
    # )
    #
    # await client.close()

    # resp = requests.get(
    #     "https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/jeopardy_tiny.json"
    # )
    # data = json.loads(resp.text)
    #
    questions = client.collections.use("Question")
    #
    # objs = [
    #     {"answer": d["Answer"], "question": d["Question"], "category": d["Category"]}
    #     for d in data
    # ]
    #
    # result = await questions.data.insert_many(objs)
    #
    # if getattr(result, "has_errors", False):
    #     print("Some inserts failed.")
    #     print(result.errors)
    # else:
    #     print(f"Inserted {len(objs)} objects successfully.")

    response = questions.query.hybrid(
                query="biology",
                alpha=0.5,
                limit=2)

    print(response)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
