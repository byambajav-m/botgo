from langchain_ollama import ChatOllama
from typing import Tuple
from config import settings


class OllamaClient:
    def __init__(self):
        self.llm = ChatOllama(
            model=settings.OLLAMA_LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.3
        )

    def generate_review(self, diff: str, contexts: list) -> Tuple[str, str]:
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

        response = self.llm.invoke(prompt)
        content = response.content

        summary = "No summary generated"
        suggestion = "No suggestion generated"

        if "SUMMARY:" in content:
            parts = content.split("SUGGESTION:")
            summary = parts[0].replace("SUMMARY:", "").strip()
            suggestion = parts[1].strip() if len(parts) > 1 else "Consider reviewing code quality"

        return summary, suggestion


ollama_client = OllamaClient()