# Configuration

File: `~/.multacd/config.yaml` (dibuat wizard saat pertama jalan).
Flag `--config PATH` dan `/model NAMA` untuk override.

```yaml
model: "groq/llama-3.3-70b-versatile"
api_key: "gsk_xxxx"
# api_base: "http://localhost:11434"   # Ollama / endpoint custom

max_tokens: 8096
temperature: 0.3
max_tool_iterations: 20

auto_approve_reads: true
ask_before_write: true
ask_before_bash: true
ask_before_web: true

search_provider: "tavily"    # tavily | exa | brave | serpapi | duckduckgo
search_api_key: "tvly-xxxx"  # kosong = duckduckgo (gratis)
```

- Provider model: format `provider/nama` (`anthropic/...`, `openai/...`,
  `gemini/...`, `groq/...`, `ollama/...`).
- Plugin user: `~/.multacd/plugins/` (lihat [Plugins](plugins.md)).
- Kepribadian: `~/.multacd/soul.md` (override bawaan).
