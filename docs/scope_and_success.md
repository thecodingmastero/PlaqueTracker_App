# PlaqueTracker — Scope & Success Criteria (Prototype)

Scope (prototype):
- End-to-end demo pipeline for pH capture: simulated BLE/HTTP ingest → smoothing → image-based hydrogel scanning → analytics (plaque risk) → PDF reporting → reward assignment.
- Mobile demo: camera guidance overlay + image upload flow (scaffold).
- Security: prototype JWT auth, role model for clinician access, and basic device keys for ingestion.

Success criteria (MVP prototype):
- Ingest service accepts telemetry and applies smoothing; data can be replayed for analytics.
- Hydrogel CV produces a pH estimate from an image and saves metadata.
- Analytics service computes a Plaque Risk Index and can be invoked via an HTTP endpoint.
- Reporting service can generate a simple PDF summary from analytics output.
- Rewards subsystem awards XP/badges based on analytics outputs and streaks.

Non-goals for prototype:
- Full HIPAA-compliant deployment (production controls, BAAs). Implementation will document required steps.
- Clinical validation of models — requires external dental datasets and IRB/consent.
