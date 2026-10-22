# BangkahFixBot

An issue->PR bot that fixes bugs **test-first**: it triages a GitHub issue, writes its own
failing regression test, implements a minimal patch, verifies the test goes red->green in a
sandbox, and opens a draft PR — all through NVIDIA Nemotron models on
[Nebius Token Factory](https://tokenfactory.nebius.com).

Built for the **Nebius x NVIDIA Global AI Hackathon** (Coding & Agentic Engineering track).

## How it works

```
GitHub issue ──► triage (Nano)  ──► plan (Super) ──► failing test (Super)
                                                          │
                          ┌───────────────────────────────┘
                          ▼
        patch (Super, Ultra on retry) ──► sandbox verify ──► draft PR
```

- **Model cascade on Token Factory** (OpenAI-compatible API):
  - `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` — cheap triage calls ($0.06/$0.24 per 1M tok)
  - `nvidia/nemotron-3-super-120b-a12b` — planning, tests, patches ($0.30/$0.90)
  - `nvidia/Nemotron-3-Ultra-550b-a55b` — deep reasoning on stubborn bugs ($1.00/$3.00)
- **Structured outputs** (`json_schema`, strict) keep every handoff typed.
- **Reasoning control**: `chat_template_kwargs.enable_thinking` toggled per phase.
- Each PR lists: the generated regression test, patch, verification log, and per-phase
  token/cost usage.

## Status

- [x] Repo scaffold, MIT license
- [x] Token Factory client with model cascade + mock mode
- [x] Test-first loop with local sandbox (subprocess pytest)
- [ ] Docker-isolated sandbox
- [ ] GitHub App/webhook + draft PR creation
- [ ] Web dashboard (Next.js)
- [ ] Eval harness (fix-rate & precision on seeded bug set)

## Quickstart (agent)

```bash
cd agent
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # put your NEBIUS_API_KEY here

python -m bfbot.cli demo    # runs the toy repo without an API key (mock mode)
```

## License

MIT — see [LICENSE](LICENSE).
