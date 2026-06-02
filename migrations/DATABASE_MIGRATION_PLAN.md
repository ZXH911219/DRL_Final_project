# Database Zero-Downtime Migration & Upgrade Strategy (Task 42)

## 1. Upgrades
- Use logical replication to synchronize primary (old version) with replica (new version).
- Promote replica to primary during planned 1-second failover window.

## 2. Zero-Downtime Migration
- Leverage read-replicas handling read traffic while primary is migrated.
- Queue writes in Redis/RabbitMQ message queue during failover.

## 3. Data Validation
- Post-migration scripts verify checksums and Row Counts.
- LanceDB vectors validated against subset of raw slide extractions.

## 4. Rollback Procedures
- Retain active old primary as a lagging replica for 72 hours post migration.
- Quick DNS flip-back and queue playback to old primary if corruption is detected.
