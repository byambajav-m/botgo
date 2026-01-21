import weaviate
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery
from typing import List
from config import settings


def _get_embedding(text: str) -> List[float]:
    from langchain_ollama import OllamaEmbeddings
    embeddings = OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL
    )
    return embeddings.embed_query(text)


def _generate_id(project_id: int, mr_iid: int) -> str:
    import uuid
    content = f"mr_{project_id}_{mr_iid}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, content))


class WeaviateClient:
    def __init__(self):
        self.client = weaviate.connect_to_local(
        host="localhost",
        port="8888",
        grpc_port=50051,
    )
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            if self.client.collections.exists(settings.WEAVIATE_COLLECTION):
                return

            self.client.collections.create(
                name=settings.WEAVIATE_COLLECTION,
                properties=[
                    Property(
                        name="content",
                        data_type=DataType.TEXT,
                        description="Code diff content"
                    ),
                    Property(
                        name="project_id",
                        data_type=DataType.INT,
                        description="GitLab project ID"
                    ),
                    Property(
                        name="mr_iid",
                        data_type=DataType.INT,
                        description="Merge request IID"
                    ),
                    Property(
                        name="context_type",
                        data_type=DataType.TEXT,
                        description="Type of context (e.g., 'mr_diff')"
                    )
                ]
            )
        except Exception as e:
            print(f"Error ensuring collection: {e}")

    def store_diff(self, project_id: int, mr_iid: int, diff: str) -> None:
        if not diff:
            return

        try:
            collection = self.client.collections.get(settings.WEAVIATE_COLLECTION)

            diff_preview = diff[:500]
            embedding = _get_embedding(diff_preview)

            uuid = _generate_id(project_id, mr_iid)

            collection.data.insert(
                properties={
                    "content": diff_preview,
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "context_type": "mr_diff"
                },
                vector=embedding,
                uuid=uuid
            )
        except Exception as e:
            print(f"Error storing diff: {e}")

    def query_similar(self, diff: str, n_results: int = 3) -> List[str]:
        try:
            collection = self.client.collections.get(settings.WEAVIATE_COLLECTION)

            query_embedding = _get_embedding(diff[:500])

            response = collection.query.near_vector(
                near_vector=query_embedding,
                limit=n_results,
                return_metadata=MetadataQuery(distance=True)
            )

            contexts = []
            for obj in response.objects:
                contexts.append(obj.properties["content"])

            return contexts
        except Exception as e:
            print(f"Error querying similar contexts: {e}")
            return []

    def close(self):
        self.client.close()


weaviate_client = WeaviateClient()