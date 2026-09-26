# Architecture

Django is the application core. The AI Orchestrator isolates optional external providers.
The recommendation engine remains local and deterministic.

Provider flow:
1. Try configured primary provider.
2. Check confidence.
3. Try the next provider if needed.
4. Use local fallback.
5. Store the result in the wardrobe record.

This prevents the application from becoming dependent on a single API.
