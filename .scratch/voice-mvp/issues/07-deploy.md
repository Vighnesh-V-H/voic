# 07: Deploy wiring + demo runbook (integrate everything)

**What to build:** One deployable demo: wire all routers, finalize env template, and write the runbook + demo script that proves failed-payment → Vobiz call → ElevenLabs talk → checkout link → email.

**Blocked by:** 06-orchestration (and transitively 02–05; start the runbook skeleton early, wire code last).

**Status:** ready-for-agent

**Branch:** `feature/voice-07-deploy`

**Timebox:** 30–45 min. Only ticket allowed to touch shared wiring.

**Owns:** `app/main.py` (router includes ONLY — add `voice_ws`, `agent_tools`, `voice_demo` routers), `apps/backend/.env.example` (add voice vars with empty placeholders, never real secrets), `docs/voice-demo-runbook.md` (new), `scripts/voice-demo.py` (new, optional helper). Must NOT touch business logic in other tickets' files (resolve conflicts by keeping their logic, only fixing imports).

## Acceptance criteria

- [ ] `app/main.py` includes all new routers; backend boots with empty voice env (agent/WS paths log-and-skip, existing webhook + answer XML unaffected); `CORS`/WS allows the production + ngrok origins.
- [ ] `.env.example` documents every voice var (`ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID`, `AGENT_TOOL_TOKEN`, `VOICE_WS_BASE_URL`, existing `VOBIZ_*`/`VOICE_CALLBACK_TOKEN`) with empty values and one-line source notes; `git diff` shows no real secrets.
- [ ] `docs/voice-demo-runbook.md` is a 10-step checklist: env fill → migrate → boot → seed/demo-trigger → Vobiz places call → WS bridges → ElevenLabs talks → agent calls `create-checkout-link` → agent calls `send-email` → verify Stripe link + inbox. Includes curl examples and expected outputs.
- [ ] Secrets server-side only: no voice secret referenced from `apps/frontend/*`.
- [ ] Manual verify (Definition of Done): failed payment → customer gets Vobiz call → ElevenLabs converses → customer asks for link → agent hits Voic backend → Stripe checkout link created → email sent. Record which steps were live vs simulated in the runbook.
