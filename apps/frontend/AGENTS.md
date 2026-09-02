# Frontend Guidance

- This app uses Next.js App Router and TypeScript.
- Public routes live under `src/app/(public)`.
- Authentication routes live under `src/app/(auth)/auth` and are served at `/auth/*`; `/login` and `/signup` are public aliases.
- Protected routes live under `src/app/(protected)` and are guarded by `src/proxy.ts` plus backend session validation.
- Run `npm run lint` for linting and `npm run build` for a production build.
- Browser authentication requests use the versioned FastAPI API under `/api/v1` and include credentials.
- The browser never receives the session token directly; it is an HTTP-only cookie set by the backend.
