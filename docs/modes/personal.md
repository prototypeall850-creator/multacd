# Personal Agent (/personal)

Kontrol multacd dari mana saja via bot Telegram + daemon background.

- **Bot**: stranger auto-reply + notif admin; user/admin agent penuh
  (konfirmasi tool Y/N); kirim/terima file; 30/46 tool aktif remote.
- **Scheduler**: cron di `config.yaml`, persist SQLite (survive restart).
- **Briefing**: todo + git + berita tiap pagi, `[private]` tidak
  pernah keluar ke LLM.
- **Daemon**: `multacd daemon start|status|logs|stop` — tanpa token
  jalan scheduler-only.
- Dari TUI `/personal`: kelola user, job, daemon, dan trigger briefing.
