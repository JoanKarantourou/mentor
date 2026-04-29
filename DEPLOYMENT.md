# Deployment

Three recipes in order of complexity. All assume you have `git clone`d the repository.

---

## Local development

The simplest path. Everything runs in Docker Compose on your machine.

```bash
cp .env.example .env
docker compose up
```

On the first run Docker builds three images (db, backend, frontend). Subsequent starts are fast.

- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

**Common gotchas:**

- **Port conflicts.** If ports 3000, 5432, or 8000 are in use, edit `docker-compose.yml` to remap the host-side ports (e.g. `"3001:3000"`). Set `NEXT_PUBLIC_BACKEND_URL=http://localhost:8001` in `.env` if you remap the backend port.
- **First-build slowness.** The backend image installs Python dependencies including `unstructured` which has heavy optional dependencies. The first build takes 3–5 minutes. Subsequent rebuilds are cached.
- **Docker memory.** The backend and Postgres together use ~1 GB RAM at rest. Docker Desktop's default resource limits (2 GB) are sufficient; if you see OOM kills, increase the memory limit in Docker Desktop settings.
- **Apple Silicon (M1/M2/M3).** The pgvector image builds natively for `linux/arm64`. If you see a platform warning, set `platform: linux/amd64` in `docker-compose.yml` or ensure Rosetta is enabled in Docker Desktop.
- **Re-embedding after provider change.** If you switch `EMBEDDING_PROVIDER` after ingesting documents, the existing chunks still have vectors from the old provider. Re-embed them:
  ```bash
  docker compose up --build
  curl -X POST http://localhost:8000/admin/reindex \
    -H "Content-Type: application/json" \
    -d '{"only_stale": true}'
  ```
  Monitor progress with:
  ```bash
  watch -n 2 'curl -s http://localhost:8000/admin/embeddings/status | python3 -m json.tool'
  ```

---

## Single VPS (Hetzner, DigitalOcean, Linode, or similar)

Suitable for a small team (5–20 people). Runs on a single server behind Caddy for HTTPS.

**Minimum spec:** 4 GB RAM, 2 vCPU, 40 GB disk. A Hetzner CX22 or DigitalOcean Basic Droplet ($12–$24/month) works.

### 1. Provision the server

Use your provider's control panel to create a Debian 12 or Ubuntu 22.04 server. Add your SSH public key.

### 2. Install Docker

```bash
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Verify
docker --version
docker compose version
```

### 3. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/mentor.git /opt/mentor
cd /opt/mentor
cp .env.example .env
```

Edit `.env`. At minimum, set:
- `POSTGRES_PASSWORD` — change from the default
- `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...` for a real LLM
- `EMBEDDING_PROVIDER=openai` and `OPENAI_API_KEY=...` for real embeddings
- `NEXT_PUBLIC_BACKEND_URL=https://mentor.yourdomain.com`

### 4. Point your domain

Add two DNS A records pointing to your server IP:
- `mentor.yourdomain.com` → frontend
- `mentor-api.yourdomain.com` → backend (or use a path-based split with one domain)

### 5. Add Caddy for TLS

Install Caddy on the host (not in Docker) so it can provision Let's Encrypt certificates:

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```caddy
mentor.yourdomain.com {
    reverse_proxy localhost:3000
}

mentor-api.yourdomain.com {
    reverse_proxy localhost:8000
    # Restrict the /admin endpoints to your IP only if desired
    # @admin path /admin/*
    # @admin not remote_ip YOUR_IP
    # respond @admin "Forbidden" 403
}
```

```bash
systemctl enable caddy
systemctl start caddy
```

Caddy provisions TLS certificates automatically on first request.

### 6. Start the stack

```bash
cd /opt/mentor
docker compose up -d
```

Check health:

```bash
curl https://mentor-api.yourdomain.com/health
```

### 7. Keep it running

To restart automatically after reboots:

```bash
# Add to /etc/rc.local or create a systemd service
cd /opt/mentor && docker compose up -d
```

Or use Docker Compose's `restart: unless-stopped` (already set in the provided `docker-compose.yml`).

---

## Cloud-managed

For teams who want managed infrastructure (no server to maintain). The mapping is straightforward:

| Mentor component | AWS | Azure | GCP |
|-----------------|-----|-------|-----|
| PostgreSQL + pgvector | RDS for PostgreSQL (enable pgvector extension) | Azure Database for PostgreSQL – Flexible Server | Cloud SQL for PostgreSQL |
| Backend container | ECS Fargate | Azure Container Apps | Cloud Run |
| Frontend container | ECS Fargate or Amplify | Azure Container Apps or Static Web Apps | Cloud Run |
| Blob storage | S3 | Azure Blob Storage | Cloud Storage |

**Note on pgvector:** Verify that your managed PostgreSQL tier supports the `pgvector` extension. On AWS RDS and Azure Flexible Server, enable it via `CREATE EXTENSION vector;` after provisioning. On GCP Cloud SQL, enable the `pgvector` flag in the instance settings.

**Blob storage:** Currently only `BLOB_STORE=local` is implemented. For cloud deployments, the backend container needs a persistent volume (EFS on AWS, Azure Files, or Filestore on GCP) mounted at `BLOB_STORE_ROOT`. A cloud blob storage provider (`s3`, `azure_blob`) is a planned future addition.

**Container images:** Build and push to ECR / ACR / Artifact Registry from the provided Dockerfiles, then reference them in your container service configuration.

---

## Production checklist

Before making a Mentor instance accessible to others:

- [ ] **Change `POSTGRES_PASSWORD`.** The default `postgres` is not acceptable outside localhost.
- [ ] **Change `POSTGRES_USER` if desired.** A non-superuser role reduces blast radius.
- [ ] **Set `ENVIRONMENT=production`.** No behavioral change today, but useful for log filtering.
- [ ] **Set `NEXT_PUBLIC_BACKEND_URL`** to the actual backend URL — not `localhost`.
- [ ] **Set up automated backups** for the PostgreSQL database. `pg_dump` on a cron job works for small deployments; use managed backup snapshots for cloud deployments.
- [ ] **Set up uptime monitoring.** A free monitor on the `/health` endpoint (UptimeRobot, Better Uptime, etc.) gives you alerting on restarts.
- [ ] **Restrict `/admin` endpoints.** The `/admin/reindex` endpoint triggers bulk re-embedding which costs API credits. Put it behind IP allowlisting or HTTP basic auth in your reverse proxy until authentication is implemented.
- [ ] **Verify CORS.** The backend's CORS configuration defaults to permissive for development. In production, restrict `allow_origins` to your frontend domain.
- [ ] **Consider rate limiting the chat endpoint.** Each message triggers embedding and LLM API calls. A reverse proxy rate limit (Caddy's `rate_limit` plugin, nginx `limit_req`) prevents accidental bill inflation.
- [ ] **No authentication exists.** All API endpoints are publicly accessible to anyone who can reach the server. Do not deploy without a network-level access restriction (VPN, IP allowlist, or reverse proxy auth) until authentication is implemented.
