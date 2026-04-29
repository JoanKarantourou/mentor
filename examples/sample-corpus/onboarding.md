# New Engineer Onboarding Guide

Welcome to the team. This guide covers the first two weeks and gives you the context you need to be productive.

## Week 1: Setup and orientation

### Development environment

Prerequisites: Docker Desktop, Git, a terminal, VS Code (or your preferred editor).

```bash
git clone https://github.com/your-org/platform.git
cd platform
cp .env.example .env
docker compose up
```

The full stack (API, worker, database, cache) starts in Docker. First build takes about 5 minutes. After that:
- API: http://localhost:4000
- Worker dashboard: http://localhost:4000/admin/queues
- Database: `postgresql://localhost:5432/platform_dev` (user: `app`, pass: `dev`)

### Getting access

Open a ticket in #it-access Slack channel to request:
- AWS console access (read-only for dev, full for production requires on-call rotation)
- Datadog (monitoring and logs)
- PagerDuty (required before your first on-call shift)
- GitHub org membership (invite goes to your work email)

### Key repositories

| Repo | Purpose |
|------|---------|
| `platform` | Main API and data model |
| `platform-worker` | Background job processor |
| `platform-infra` | Terraform and Kubernetes manifests |
| `platform-frontend` | React frontend |
| `platform-shared` | Shared TypeScript types and clients |

## Code review process

All changes go through pull requests. Baseline expectations:

- Branch from `main`. Name your branch `yourname/short-description`.
- Keep PRs small. Under 400 lines of diff is easier to review; over 800 lines rarely gets thorough review.
- Write a description. Explain what changed and why, not just what the diff shows.
- Link the Jira ticket if the change comes from one.
- One approval required for non-production-path changes. Two required for changes to auth, billing, or database migrations.

Reviews should happen within one business day. If your PR is stuck, nudge in #engineering on Slack.

### Automated checks

The CI pipeline runs on every PR:
- Unit tests (`pytest`, `jest`)
- Integration tests (against a test database)
- Lint (`ruff`, `eslint`)
- Type checking (`pyright`, `tsc`)
- Secrets scan (prevents committing credentials)

All checks must pass before merging. If a check fails for reasons unrelated to your change, open a separate bug for it rather than skipping.

## On-call rotation

The engineering team rotates on-call weekly. You join the rotation after your first month.

- Primary on-call responds to alerts within 15 minutes during business hours, 30 minutes outside.
- Secondary on-call escalates if primary is unreachable.
- Runbooks are in Notion under Engineering → Runbooks. The most important ones are also in this corpus.

Before your first on-call shift, shadow the current primary and review the [deployment runbook](runbook.md).

## Communication norms

- **Slack** for async communication. `#engineering` is the main channel.
- **Jira** for tracking work. New tickets go to the backlog; sprint planning happens every two weeks.
- **Notion** for documentation. Code-adjacent docs (ADRs, runbooks) live here in this corpus.
- **GitHub Discussions** for proposals that need async feedback from the whole team.

Video calls are for decisions that would take too long in text, not for status updates.

## First week checklist

- [ ] Dev environment running locally
- [ ] Access granted (AWS, Datadog, PagerDuty, GitHub)
- [ ] First PR merged (aim for a small bug fix or doc improvement)
- [ ] Met with your assigned buddy
- [ ] Read the [architecture overview](architecture.md)
- [ ] Read the [API reference](api_reference.md)
