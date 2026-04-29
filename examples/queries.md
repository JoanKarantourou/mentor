# Suggested queries for the sample corpus

Upload the files in `examples/sample-corpus/` to Mentor, wait for them to reach `indexed` status, and try these questions. They demonstrate different aspects of Mentor's retrieval and reasoning.

---

## Questions with clear answers in the corpus

These should produce confident, cited responses.

- How do I set up my development environment?
- What tools do I need before my first PR can be merged?
- How many approvals are required for changes to the auth or billing code?
- What happens when a webhook delivery fails? How many retry attempts are made?
- How does the API handle duplicate events from a producer?
- What is the schema for the `POST /events` request body?
- What Redis commands are used to consume events from the queue?
- How do I roll back a deployment in under 2 minutes?
- What is the purpose of PgBouncer in this architecture?
- What does the `field_rename` transformation step do if the field doesn't exist?
- How do I verify a webhook signature in Python?

---

## Questions that span multiple documents

These require the model to draw from more than one file.

- What is the full path an event takes from ingestion to delivery?
- Why was Kafka rejected as the event queue, and what would trigger revisiting that decision?
- How does the retry strategy for failed deliveries compare between the API client and the worker pool?
- What monitoring should I set up to know if the system is falling behind?

---

## Questions that test code understanding

These require reasoning about the Python or TypeScript source files.

- What transformation types does the pipeline support?
- What error is raised if `field_add_static` is called on a field that already exists and `overwrite` is false?
- How does the TypeScript client handle rate limit responses (HTTP 429)?
- What happens in `run_pipeline` if a step raises an unexpected exception that is not a `PipelineError`?

---

## Questions that should return low confidence (not in corpus)

These test Mentor's honesty — it should refuse to answer rather than hallucinate.

- How do I configure Kubernetes autoscaling for the worker pool?
- What is the cost of the Tavily API plan you use?
- How does the database replication work?
- What is the company's vacation policy?

For these, Mentor should say it doesn't have enough information. If you have gap analysis enabled (`GAP_ANALYSIS_ENABLED=true`), you should also see suggestions for what documents would help answer the question.
