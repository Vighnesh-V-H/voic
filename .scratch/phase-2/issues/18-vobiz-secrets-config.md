# 18: Configure Vobiz secrets and local call settings

> Synced from https://github.com/Vighnesh-V-H/voic/issues/18
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-04T09:08:30Z | Updated: 2026-09-04T09:08:30Z
> Blocked by: None (can start immediately)

**What to build:** Every secret and URL the voice-call build needs exists as a documented placeholder, so any developer can configure calling without touching code. No real credentials are ever committed; the backend reads them from the environment with safe empty defaults.

**Status:** ready-for-agent

- [ ] `.env.example` lists every Vobiz/voice setting with a comment explaining where the real value comes from (Vobiz console, purchased DID, public tunnel URL), values left empty.
- [ ] Backend settings load all of them; missing values disable calling but never crash boot or webhook handling.
- [ ] The callback authentication strategy (shared token embedded in our per-call callback URLs) is documented and has a setting.
- [ ] Backend README documents the setup path: console signup, auth ID/token, buy a DID, expose a public base URL, fill `.env`.
- [ ] An automated config test locks the contract: empty means disabled, complete means enabled.

## Full body

## What to build

Every secret and URL the voice-call build needs exists as a documented placeholder, so any developer can configure calling without touching code. No real credentials are ever committed; the backend reads them from the environment with safe empty defaults.

## Acceptance criteria

- [ ] `.env.example` lists every Vobiz/voice setting with a comment explaining where the real value comes from (Vobiz console, purchased DID, public tunnel URL), values left empty.
- [ ] Backend settings load all of them; missing values disable calling but never crash boot or webhook handling.
- [ ] The callback authentication strategy (shared token embedded in our per-call callback URLs) is documented and has a setting.
- [ ] Backend README documents the setup path: console signup, auth ID/token, buy a DID, expose a public base URL, fill `.env`.
- [ ] An automated config test locks the contract: empty means disabled, complete means enabled.

## Blocked by

None (can start immediately).
