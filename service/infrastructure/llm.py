from openai import AsyncOpenAI
from typing import Tuple, List, Dict
from config import settings
import re

BASE_REVIEW_CONTRACT = """
You are a senior software engineer performing a strict merge request review.

Global rules:
- Base all conclusions strictly on the provided diff
- Do NOT speculate or assume missing context
- Focus on correctness, safety, and maintainability
- Avoid stylistic comments unless they affect correctness
- If the diff is insufficient to judge, state that explicitly
- Do NOT invent issues when the code is correct

Follow the output format exactly.
""".strip()

NO_ISSUE_RULE = """
If the diff is correct and no concrete improvement is warranted:
- Do NOT invent issues
- Set SUGGESTION to exactly: LGTM
- SUMMARY should briefly state that the change is sound and consistent
""".strip()


STACK_RULES = {
    "python": """
Stack: Python backend (FastAPI, async services, Celery)

Review focus:
- Async/await correctness and blocking call risks
- Exception handling and failure paths
- Input validation and boundary checks
- Side effects in request handlers
- Background job idempotency and retries
""".strip(),

    "golang": """
Stack: Go backend (net/http, Gin, gRPC, services)

Review focus:
- Error handling (explicit checks, wrapped errors)
- Context propagation and cancellation
- Goroutine lifecycle and leaks
- Concurrency safety (channels, mutexes, shared state)
- Resource cleanup (defer usage, closes)
- API boundary correctness
""".strip(),

    "frontend-ts": """
Stack: Frontend TypeScript (framework-agnostic)

Review focus:
- Type safety and unsafe casts
- State management correctness
- Effect / lifecycle correctness
- Rendering or computation inefficiencies
- Accessibility regressions when applicable
""".strip(),

    "vue": """
Stack: Vue.js frontend (Vue 2 / Vue 3)

Review focus:
- Component responsibility and separation of concerns
- Reactive state correctness (ref vs reactive, computed vs methods)
- Watcher correctness and cleanup
- Lifecycle hook usage and side effects
- Template reactivity pitfalls (v-if vs v-show, key usage)
- Prop / emit contract correctness
- Performance issues from unnecessary reactivity
""".strip(),

    "nuxt": """
Stack: Nuxt.js application

Review focus:
- SSR vs client-only logic correctness
- useAsyncData / useFetch / asyncData correctness
- Hydration mismatch risks
- Plugin execution context (server vs client)
- Runtime config exposure
- Middleware side effects and ordering
""".strip(),

    "devops": """
Stack: Infrastructure / DevOps

Review focus:
- Secret exposure
- Idempotency of scripts and manifests
- Rollback and failure recovery
- Environment-specific risks
- Resource and cost limits
""".strip(),

    "data-sql": """
Stack: Data / SQL / Migrations

Review focus:
- Data integrity and correctness
- Backward compatibility
- Locking and performance impact
- Migration safety and reversibility
- Index usage and query efficiency
""".strip(),
}


STACK_CLASSIFIER_PROMPT = """
You are classifying the applicable technology stacks for a file diff.

Rules:
- Base decisions ONLY on the diff content
- Return ALL applicable stacks
- Nuxt implies Vue + frontend-ts, but still list them explicitly
- Documentation files are "docs"
- SQL / migrations are "data-sql"

Return a comma-separated list from:
python
golang
frontend-ts
vue
nuxt
devops
data-sql
docs

Examples:
- nuxt,vue,frontend-ts
- vue,frontend-ts
- frontend-ts
- docs

Return only the comma-separated values.
""".strip()

def build_review_prompt(diff: str, contexts: list, stacks: List[str]) -> str:
    context_str = "\n---\n".join(contexts[:3]) if contexts else "None"

    rules = "\n\n".join(STACK_RULES[s] for s in stacks if s in STACK_RULES)

    return f"""
{BASE_REVIEW_CONTRACT}

{rules}

{NO_ISSUE_RULE}

Prior context (reference only, do not assume):
{context_str[:800]}

File diff:
{diff[:3000]}

IMPORTANT FORMAT RULES:
- Each field MUST start on its own line
- Field labels MUST be exactly:
  SUMMARY:
  SUGGESTION:
  CONFIDENCE:
  REASON:
- Do NOT inline field labels inside sentences
- Do NOT add extra text before or after fields

Required output format (EXACT):

SUMMARY: <2–3 concise sentences>
SUGGESTION: <one concrete improvement OR exactly "LGTM">
CONFIDENCE: <high | medium | low>
REASON: <one short sentence>
""".strip()


FILE_DIFF_REGEX = re.compile(r"diff --git a/(.*?) b/.*?\n", re.DOTALL)

def split_diff_by_file(diff: str) -> Dict[str, str]:
    files = FILE_DIFF_REGEX.split(diff)
    result = {}

    for i in range(1, len(files), 2):
        result[files[i]] = files[i + 1]

    return result or {"unknown": diff}


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
    async def classify_stacks(cls, file_diff: str) -> List[str]:
        response = await cls.client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": STACK_CLASSIFIER_PROMPT},
                {"role": "user", "content": file_diff[:3000]},
            ],
            temperature=0.0,
        )

        raw = (response.choices[0].message.content or "").strip()
        stacks = [s.strip() for s in raw.split(",") if s.strip() in STACK_RULES]

        return stacks or ["frontend-ts"]

    @classmethod
    async def _review(
        cls,
        diff: str,
        contexts: list,
        stacks: List[str],
    ) -> Tuple[str, str]:
        prompt = build_review_prompt(diff, contexts, stacks)

        response = await cls.client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.0,
            top_p=1.0,
        )

        return cls._parse_response(response.choices[0].message.content or "")

    @classmethod
    async def generate_review(
        cls,
        diff: str,
        contexts: list,
    ) -> Tuple[str, str]:
        file_diffs = split_diff_by_file(diff)

        summaries = []
        suggestions = []

        for file_diff in file_diffs.values():
            stacks = await cls.classify_stacks(file_diff)
            summary, suggestion = await cls._review(
                file_diff,
                contexts,
                stacks,
            )

            summaries.append(f"[{','.join(stacks)}] {summary}")
            suggestions.append(suggestion)

        if suggestions and all(s.upper() == "LGTM" for s in suggestions):
            return (
                " ".join(summaries) if summaries else "No significant changes detected.",
                "LGTM",
            )

        return (
            " ".join(summaries) if summaries else "No significant changes detected.",
            " | ".join(s for s in suggestions if s.upper() != "LGTM") or "LGTM",
        )


    @staticmethod
    def _parse_response(content: str) -> Tuple[str, str]:
        text = content.strip()

        fields = {
            "SUMMARY:": "",
            "SUGGESTION:": "",
            "CONFIDENCE:": "",
            "REASON:": "",
        }

        current = None
        for line in text.splitlines():
            line = line.strip()
            for key in fields:
                if line.startswith(key):
                    current = key
                    fields[key] = line[len(key):].strip()
                    break
            else:
                if current and line:
                    fields[current] += " " + line

        summary = fields["SUMMARY:"].strip()
        suggestion = fields["SUGGESTION:"].strip()

        if not suggestion or suggestion.upper() == "LGTM":
            return (
                summary or "No issues were found during review.",
                "LGTM",
            )

        return (
            summary or "No summary generated.",
            suggestion,
        )
