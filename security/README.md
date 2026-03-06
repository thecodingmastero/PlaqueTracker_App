# Security & Compliance Notes

This document captures initial security considerations for PlaqueTracker.

- Transport: enforce TLS for all endpoints.
- Authentication: OAuth2 / JWT for users; device API keys for sensors.
- RBAC: roles `user`, `clinician`, `admin`; restrict PHI access to clinician role.
- Data protection: encrypt PII at rest; minimize retention; pseudonymize data for analytics.
- Logging: scrub PII from logs; use audit tables for sensitive events.
- HIPAA: design for Business Associate Agreement (BAA) and follow administrative safeguards.
