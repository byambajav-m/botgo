from openai import AsyncOpenAI
from typing import Tuple
from config import settings


class LLMWorker:
    _client: AsyncOpenAI | None = None

    @classmethod
    def client(cls) -> AsyncOpenAI:
        if cls._client is None:
            cls._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
        return cls._client

    @classmethod
    async def generate_review(cls, diff: str, contexts: list) -> Tuple[str, str]:
        context_str = "\n".join(contexts[:2]) if contexts else "No prior context"

        prompt = f"""You are a code reviewer. Analyze this merge request diff and provide:
                    1. A brief summary (2-3 sentences)
                    2. One concrete improvement suggestion

                    Prior similar code contexts:
                    {context_str[:500]}

                    Current MR Diff:
                    {diff[:2000]}

                    Format your response as:
                    SUMMARY: <your summary>
                    SUGGESTION: <one specific suggestion>
                 """

        response = await cls.client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.01,
            top_p=0.8,
            stream=False,
        )
        content = response.choices[0].message.content

        summary = "No summary generated"
        suggestion = "No suggestion generated"

        if "SUMMARY:" in content:
            parts = content.split("SUGGESTION:")
            summary = parts[0].replace("SUMMARY:", "").strip()
            suggestion = parts[1].strip() if len(parts) > 1 else "Consider reviewing code quality"

        return summary, suggestion