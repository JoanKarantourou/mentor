# Project Documentation

This document provides an overview of the project architecture and deployment guidelines.
The system is built with modern technologies and follows best practices for scalability.

## Architecture Overview

The application uses a microservices architecture with the following components:

- API Gateway for routing and authentication
- Backend services written in Python and Go
- PostgreSQL database with read replicas
- Redis for caching and session management

## Ελληνικές Σημειώσεις

Αυτή η ενότητα περιέχει σημειώσεις στην ελληνική γλώσσα για την ομάδα ανάπτυξης.
Το σύστημα πρέπει να υποστηρίζει πολλές γλώσσες και να διαχειρίζεται σωστά
τους χαρακτήρες Unicode.

## Deployment

Deploy to production using the provided Docker Compose configuration. Ensure all
environment variables are set correctly before starting the services.

```bash
docker compose up --build -d
```

Monitor logs with `docker compose logs -f` to verify all services start correctly.
