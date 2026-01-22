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

    "nuxt": """
Stack: Nuxt.js application

Review focus:
- Correct usage of server-side rendering (SSR) vs client-only logic
- Data fetching correctness (useAsyncData, useFetch, asyncData)
- State hydration and mismatch risks
- Route and layout boundaries
- Runtime config usage and exposure
- Plugin execution context (server vs client)
- Middleware side effects and ordering

Avoid stylistic preferences unless they affect correctness.
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

Avoid stylistic preferences unless they affect correctness.
""".strip(),

    "frontend-ts": """
Stack: Frontend (React, TypeScript)

Review focus:
- Component responsibility boundaries
- State management correctness
- useEffect dependency correctness
- Rendering performance regressions
- Type safety and accessibility regressions
""".strip(),

    "docs": """
Stack: Documentation (README, markdown, docs)

Review focus:
- Accuracy and correctness
- Missing or outdated information
- Broken examples or commands
- Inconsistencies with code behavior

Do not comment on tone unless it causes ambiguity.
""".strip(),

    "devops": """
Stack: Infrastructure / DevOps

Review focus:
- Secret exposure and credential safety
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

Avoid stylistic preferences unless they affect correctness.
""".strip(),
}

STACK_CLASSIFIER_PROMPT = """
You are classifying the primary technology stack of a file diff.

Rules:
- Base your decision ONLY on the diff content
- Documentation files (README.md, *.md, docs/) are "docs"
- Go files (*.go, go.mod, go.sum) are "golang-backend"
- Choose the single most relevant stack
- If unclear, choose the closest match

Return EXACTLY one of:
python
golang
frontend-ts
devops
data-sql
docs
vue

Return only the value.
""".strip()

def build_review_prompt(diff: str, contexts: list, stack: str) -> str:
    context_str = "\n---\n".join(contexts[:3]) if contexts else "None"

    return f"""
{BASE_REVIEW_CONTRACT}

{STACK_RULES[stack]}

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
    async def classify_stack(cls, file_diff: str) -> str:
        response = await cls.client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": STACK_CLASSIFIER_PROMPT},
                {"role": "user", "content": file_diff[:3000]},
            ],
            temperature=0.0,
        )

        stack = (response.choices[0].message.content or "").strip()
        return stack if stack in STACK_RULES else "python-backend"

    @classmethod
    async def _review_stack(
        cls,
        diff: str,
        contexts: list,
        stack: str,
    ) -> Tuple[str, str]:
        prompt = build_review_prompt(diff, contexts, stack)

        response = await cls.client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.01,
            top_p=0.8,
        )

        return cls._parse_response(response.choices[0].message.content or "")

    @classmethod
    async def generate_review(
        cls,
        diff: str,
        contexts: list,
    ) -> Tuple[str, str]:
        file_diffs = split_diff_by_file(diff)

        stack_buckets: Dict[str, List[str]] = {}
        for file_diff in file_diffs.values():
            stack = await cls.classify_stack(file_diff)
            stack_buckets.setdefault(stack, []).append(file_diff)

        summaries = []
        suggestions = []

        for stack, diffs in stack_buckets.items():
            combined_diff = "\n".join(diffs)
            summary, suggestion = await cls._review_stack(
                combined_diff,
                contexts,
                stack,
            )
            summaries.append(f"[{stack}] {summary}")
            suggestions.append(suggestion)

        if suggestions and all(s.upper() == "LGTM" for s in suggestions):
            return (
                "All changes across stacks are correct and consistent.",
                "LGTM",
            )

        return (
            " ".join(summaries) if summaries else "No significant changes detected.",
            " | ".join(s for s in suggestions if s.upper() != "LGTM") or "LGTM",
        )

    @staticmethod
    def _parse_response(content: str) -> Tuple[str, str]:
        text = content.strip()

        replacements = {
            "SUGGESTION :": "SUGGESTION:",
            "SUMMARY :": "SUMMARY:",
            "CONFIDENCE :": "CONFIDENCE:",
            "REASON :": "REASON:",
        }

        for bad, good in replacements.items():
            text = text.replace(bad, good)

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

        if not suggestion:
            if "SUGGESTION:" in text:
                suggestion = text.split("SUGGESTION:", 1)[1].strip()
            else:
                suggestion = "LGTM"

        if suggestion.upper() == "LGTM":
            return (
                summary or "No issues were found during review.",
                "LGTM",
            )

        return (
            summary or "No summary generated.",
            suggestion,
        )

