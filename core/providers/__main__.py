"""Self-test paket providers (python -m core.providers)."""

from core.providers import ProviderError, estimate_cost, resolve_provider

s = resolve_provider("anthropic/claude-sonnet-4-6")
assert (s.kind, s.model) == ("anthropic", "claude-sonnet-4-6"), s
assert s.chat_url == "https://api.anthropic.com/v1/messages"
s = resolve_provider("groq/llama-3.3-70b-versatile")
assert s.kind == "openai" and "groq" in s.chat_url and s.model == "llama-3.3-70b-versatile"
s = resolve_provider("openai/gpt-4o")
assert s.chat_url == "https://api.openai.com/v1/chat/completions"
s = resolve_provider("gemini/gemini-2.0-flash")
assert "googleapis" in s.chat_url and s.model == "gemini-2.0-flash"
s = resolve_provider("ollama/llama3.2")
assert s.chat_url == "http://localhost:11434/v1/chat/completions"
s = resolve_provider("gpt-4o-mini")  # tanpa prefix → openai
assert s.model == "gpt-4o-mini" and "openai.com" in s.chat_url
s = resolve_provider("custom/mymodel", api_base="https://h:8000/v1")
assert s.chat_url == "https://h:8000/v1/chat/completions"
s = resolve_provider("deepseek/deepseek-chat")
assert s.chat_url == "https://api.deepseek.com/chat/completions"
try:
    resolve_provider("ngawur/xyz")
except ProviderError as e:
    assert "tidak dikenali" in str(e)
else:
    raise AssertionError("model ngawur harus ditolak")
try:
    resolve_provider("custom/mymodel")
except ProviderError as e:
    assert "api_base" in str(e)
else:
    raise AssertionError("custom tanpa base harus ditolak")
# Cost: 1000 in + 500 out sonnet = 3*1k + 15*0.5k per 1M
assert abs(estimate_cost("claude-sonnet-4-6", 1000, 500) - 0.0105) < 1e-9
assert estimate_cost("ollama/llama3.2", 9999, 9999) == 0.0
assert estimate_cost("??", 10, 10) == 0.0
print("✅ providers self-test OK (routing + cost)")
