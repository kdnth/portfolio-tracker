# Deploy (Neon + Railway + Netlify)

Order matters: database → API → frontend (the UI needs the API URL at build time).

## 1. Neon (Postgres)

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the connection string from the dashboard.
3. Prefer the pooled connection string for the app.
4. Keep `?sslmode=require` (Neon includes this).

You can paste Neon’s `postgresql://…` URL as-is into Railway. The API normalizes it to `postgresql+psycopg://…` for SQLAlchemy.

## 2. Railway (FastAPI)

1. New project → Deploy from GitHub → select this repo.
2. Root directory: repo root (not `frontend/`). It uses the `Dockerfile` + `railway.toml`.
3. Variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `JWT_SECRET` | Long random string (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | Your Netlify URL, e.g. `https://your-app.netlify.app` (comma-separate if you also keep localhost) |

4. Deploy. `railway.toml` runs `alembic upgrade head` on release, then starts uvicorn.
5. Confirm `https://<your-railway-domain>/health` returns `{"status":"ok"}`.
6. Copy the public Railway HTTPS URL (no trailing slash).

## 3. Netlify (Vue)

1. New site → import the same GitHub repo.
2. Build settings are in `netlify.toml` (`base = frontend`, Node 22, SPA redirect).
3. Environment variable:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | Railway URL, e.g. `https://your-api.up.railway.app` |

4. Deploy. Open the Netlify URL and register/login.

## 4. Wire CORS after Netlify exists

If you deployed Railway before knowing the Netlify URL:

1. Set `CORS_ORIGINS` on Railway to the final Netlify origin.
2. Redeploy the API (env changes need a restart).

Local + prod example:

```text
CORS_ORIGINS=http://localhost:5173,https://your-app.netlify.app
```

## Checklist

- [ ] Neon project created; URL has `sslmode=require`
- [ ] Railway health check passes
- [ ] Migrations ran (release command / check tables in Neon)
- [ ] Netlify `VITE_API_BASE_URL` points at Railway
- [ ] Railway `CORS_ORIGINS` includes the Netlify origin
- [ ] Register → create portfolio → record trade works in production

## Local parity

```bash
# API
cp .env.example .env   # fill DATABASE_URL + JWT_SECRET
uvicorn app.main:app --reload

# Frontend
cp frontend/.env.example frontend/.env
cd frontend && npm run dev
```
