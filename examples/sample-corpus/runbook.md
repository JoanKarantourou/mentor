# Deployment and Operations Runbook

## Standard deployment

All deployments go through CI/CD. To deploy the API to production:

1. Merge your PR to `main`.
2. The GitHub Actions workflow builds and pushes the Docker image to ECR.
3. The workflow opens a deploy PR in `platform-infra` that bumps the image tag.
4. Approve the deploy PR (one approval required).
5. Merging the deploy PR triggers an ECS rolling deployment. It takes ~3 minutes.

Monitor the deployment in the [Deployments dashboard](https://datadog.example.com/dashboard/deployments) or watch ECS service events in the AWS console.

If you need to deploy outside CI (emergency fix), see [Manual deployment](#manual-deployment) below.

## Rollback

### Fast rollback (ECS task definition)

If the deployment is clearly broken and you need to roll back in under 2 minutes:

```bash
# List recent task definitions
aws ecs list-task-definitions --family-prefix platform-api --sort DESC --max-items 5

# Roll back to the previous revision
aws ecs update-service \
  --cluster production \
  --service platform-api \
  --task-definition platform-api:PREVIOUS_REVISION_NUMBER
```

This does not require a code change or PR. The ECS service rolls back immediately.

### Code rollback (git revert)

For rollbacks that need to go through normal CI:

```bash
git revert <commit-hash>
git push origin main
# Follow standard deployment flow
```

## Manual deployment

For emergencies only. Requires AWS console access.

```bash
# Build and push manually
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.eu-west-1.amazonaws.com
docker build -t platform-api .
docker tag platform-api:latest 123456789.dkr.ecr.eu-west-1.amazonaws.com/platform-api:manual-$(git rev-parse --short HEAD)
docker push 123456789.dkr.ecr.eu-west-1.amazonaws.com/platform-api:manual-$(git rev-parse --short HEAD)

# Update service (use actual image URI from above)
aws ecs update-service \
  --cluster production \
  --service platform-api \
  --force-new-deployment
```

Log the manual deployment in the #incidents Slack channel.

## Database migrations

Migrations run automatically on startup via Alembic. If a migration fails, the container exits and ECS does not replace the existing task — the old version stays up.

To run migrations manually:

```bash
docker run --rm \
  --env-file .env.production \
  platform-api:latest \
  alembic upgrade head
```

**Never** run `alembic downgrade` in production without a backup. Downgrade migrations are untested on production data.

### Zero-downtime migration rules

Adding columns with defaults and adding new tables are safe. The following are unsafe without a multi-step migration:

- Renaming a column (reads from old name break on old code, writes to new name break on new code)
- Dropping a column used by the running version
- Adding a `NOT NULL` constraint to an existing column without a default

When in doubt, use an expand-contract pattern: add the new column, deploy, backfill, then remove the old column in a later release.

## Common alerts and responses

### `delivery_failure_rate > 5%` (Pagerduty: P1)

**Cause:** Usually a tenant's webhook endpoint is returning 5xx. Could also be a worker bug.

1. Check Datadog APM for the failing delivery traces.
2. Identify the affected tenant: `SELECT tenant_id, COUNT(*) FROM deliveries WHERE status='failed' AND created_at > NOW() - INTERVAL '10 minutes' GROUP BY 1 ORDER BY 2 DESC LIMIT 10;`
3. If isolated to one tenant, check their endpoint URL. Contact them if it looks like their server is down.
4. If affecting all tenants, check worker health and Redis Stream lag.

### `redis_stream_lag > 50000` (PagerDuty: P2)

**Cause:** Workers are falling behind. Either a traffic spike or worker crash.

1. Check worker count in the ECS service.
2. Check Celery worker logs in Datadog for errors.
3. Scale up workers manually if needed: `aws ecs update-service --cluster production --service platform-worker --desired-count 20`

### `database_connections > 80%` (PagerDuty: P2)

**Cause:** Connection pool exhaustion. Often triggered by a spike in API traffic or a slow query holding connections.

1. Check `pg_stat_activity` for long-running queries: `SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 10;`
2. Kill blocking queries if safe: `SELECT pg_terminate_backend(pid) WHERE ...`
3. If recurring, check PgBouncer configuration and consider reducing pool size per service.

## Health checks

- API health: `GET /health` — returns 200 with `{"status": "ok", "db": "ok", "redis": "ok"}`
- Worker health: check ECS service `runningCount` matches `desiredCount`
- Redis: `redis-cli -u $REDIS_URL PING` — returns `PONG`

## Useful commands

```bash
# Tail production API logs
datadog-ci logs tail --service platform-api --env production

# Check current task definition
aws ecs describe-services --cluster production --services platform-api \
  --query 'services[0].taskDefinition'

# Count events in a tenant's stream (pending processing)
redis-cli XLEN events:{tenant_id}

# Check slow queries
psql $DATABASE_URL -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 20;"
```
