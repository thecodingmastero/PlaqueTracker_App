# PlaqueTracker — System Architecture (initial)

This document outlines the high-level microservice architecture for PlaqueTracker and explains component responsibilities and data flow.

Core services

- Authentication Service: user signup/signin, JWT/OAuth, RBAC, password reset, MFA placeholder.
- Sensor Ingestion (BLE Gateway / Ingest API): receives BLE/WiFi packets from devices (ESP32/XIAO), validates packets, applies smoothing/drift/temperature compensation, persists readings to the `sensor_readings` table.
- Image Processing Service: accepts hydrogel scan images, performs color calibration, white-balance correction, RGB extraction, and converts to pH via a trained regression model. Emits `hydrogel_scans` records.
- Analytics Service: consumes sensor and image readings, computes temporal features, Plaque Risk Index, cavity probability, and stores results in `analytics_results`.
- Reporting Service: assembles weekly/monthly reports, generates PDF exports, and provides dentist-share payloads.
- Rewards Service: computes XP/streaks/badges and enforces anti-cheat heuristics.
- Device Management: registers device metadata, firmware version, calibration state, and battery telemetry.
- Gateway / API: public endpoint used by mobile apps and web dashboards; proxies auth, rate-limits, and routes requests to microservices.

Data store

- Primary relational DB (Postgres recommended): stores `users`, `sensor_readings`, `hydrogel_scans`, `analytics_results`, `streaks_rewards`, `devices`.
- Object store (S3-compatible): stores original scan images and PDF exports.
- Message bus (Kafka/RabbitMQ): decouples ingestion → image-processing → analytics pipelines for scalability.

Security & Compliance

- TLS for all transport; role-based access control for dentist/clinician roles; encryption-at-rest for PII; HIPAA-conscious data retention and anonymization procedures for analytics.

Extensibility

- Services are independent and versioned; analytics models are exported/model-serving friendly; reporting includes dentist-sharing placeholders for future provider API integration.

See the visual diagram in `diagrams/architecture.mmd` for a compact component view.
