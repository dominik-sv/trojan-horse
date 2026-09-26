"""Small, non-secret settings for the benchmark runner.

Secrets belong in the Windows user environment, not in this project folder.
"""

# Every model call goes through Vercel AI Gateway, which speaks the OpenAI API
# and routes "provider/model" IDs (openai/..., anthropic/..., google/...) to
# the right provider. The key is read from this Windows user variable.
GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
GATEWAY_KEY_ENV_VAR = "VERCEL_API_KEY"

# Output cap per model call. It counts a model's hidden thinking as well as the
# visible answer, so it is set high enough never to get in the way; it is only
# a safety net against a runaway response. An answer that does hit it is
# recorded as an error, never graded.
MAX_OUTPUT_TOKENS = 64_000

# A 429 (rate limit), a dropped connection or a 5xx is usually temporary, so a
# call is retried a few times before it is recorded as an error. When the
# server sends a retry-after time we wait that long; otherwise we wait
# BASE, 2*BASE, 4*BASE, ... seconds. No wait is ever longer than MAX_WAIT.
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_WAIT_SECONDS = 120.0

# How many calls to run at once overall, and how many of those may go to the
# same model. These are independent, I/O-bound requests, so running several in
# parallel just saves wall-clock time. Providers limit requests per model, so
# the per-model cap is what keeps a run from tripping those limits.
MAX_PARALLEL_CALLS = 8
MAX_CALLS_PER_MODEL = 2

# The judge (chosen in benchmark.toml) replies with a short JSON object, but a
# reasoning model spends part of this cap thinking first.
JUDGE_MAX_OUTPUT_TOKENS = 8_000
