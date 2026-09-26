# Model costs

List prices (Vercel AI Gateway `pricing` field, i.e. what the provider charges — this is
the same basis as `marketCost` used for run costs), USD per 1M tokens, for every model
currently listed in `benchmark.toml`. Pulled from the gateway's `/v1/models` endpoint,
so this costs nothing to regenerate.

Ordered most expensive to cheapest (by output $/1M, ties broken by input $/1M).

| Model | Input $/1M | Output $/1M | Context window |
|---|---:|---:|---:|
| anthropic/claude-fable-5.1 | 10.00 | 50.00 | 1,000,000 |
| openai/gpt-6-astra | 10.00 | 50.00 | 1,050,000 |
| openai/gpt-5.6-sol | 4.00 | 20.00 | 1,050,000 |
| anthropic/claude-opus-5.5 | 4.00 | 20.00 | 1,000,000 |
| moonshotai/kimi-k3 | 3.00 | 15.00 | 1,000,000 |
| openai/gpt-5.6-terra | 2.00 | 12.00 | 1,050,000 |
| google/gemini-3.1-pro-preview | 2.00 | 12.00 | 1,000,000 |
| anthropic/claude-sonnet-5 | 2.00 | 10.00 | 1,000,000 |
| openai/gpt-6-sol | 2.00 | 10.00 | 1,050,000 |
| spacexai/grok-4.6 | 2.00 | 6.00 | 500,000 |
| alibaba/qwen3.8-max | 2.00 | 6.00 | 262,144 |
| anthropic/claude-haiku-4.5 | 1.00 | 5.00 | 200,000 |
| zai/glm-5.3 | 1.40 | 4.40 | 1,000,000 |
| google/gemini-3.8-flash | 0.75 | 3.75 | 1,000,000 |
| spacexai/grok-4.7 | 1.20 | 3.60 | 500,000 |
| google/gemini-3.5-flash-lite | 0.30 | 2.50 | 1,000,000 |
| deepseek/deepseek-v4-pro | 0.66 | 1.98 | 1,000,000 |
| mistral/mistral-large-3 | 0.50 | 1.50 | 262,144 |
| openai/gpt-5.6-luna | 0.20 | 1.20 | 1,050,000 |
| deepseek/deepseek-v4.1-flash | 0.30 | 1.20 | 1,048,576 |
| meta/llama-4-maverick | 0.24 | 0.97 | 128,000 |
| spacexai/grok-4.1-fast-reasoning | 0.20 | 0.50 | 1,000,000 |
| zai/glm-5.3-flash | 0.15 | 0.50 | 1,000,000 |
| openai/gpt-6-luna | 0.10 | 0.50 | 1,050,000 |

Sorted by output price (the dominant cost since `output_tokens` includes thinking
tokens). Cheapest is `gpt-6-luna` at $0.10/$0.50 per 1M; most expensive are
`claude-fable-5.1` and `gpt-6-astra`, tied at $10/$50 per 1M.

Regenerate with:

```python
from openai import OpenAI
import os
client = OpenAI(api_key=os.getenv("VERCEL_API_KEY"), base_url="https://ai-gateway.vercel.sh/v1")
for m in client.models.list().data:
    print(m.id, m.pricing)
```
