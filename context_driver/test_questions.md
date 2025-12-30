# ReAct Agent Test Questions

Multi-hop questions designed to test the ReAct agent's reasoning capabilities against the knowledge base.

---

## 1. Infrastructure & Security

**Question:**
> What is the specific procedure for emergency SSL certificate rotation, and how does cert-manager interact with Istio gateways during this process to ensure zero downtime?

**Source Documents:**
- `Emergency_SSL_Certificate_Rotation_Procedure.md`
- `SSL_Certificate_Management.md`

**Expected Answer:**

The emergency SSL certificate rotation procedure involves both organizational and technical steps:

**Organizational Response:**
1. Incident Commander declares SEV-2 or SEV-1 incident
2. Security Lead approval is required before rotation (within 1 hour for SEV-1, 4 hours for SEV-2)
3. Teams are notified via Slack #incidents channel

**Technical Implementation (Zero Downtime):**
1. **cert-manager** (Kubernetes add-on) automatically requests a new certificate from Let's Encrypt
2. The new certificate is stored as a Kubernetes Secret
3. **Istio** detects the Secret change via Secret Discovery Service (SDS)
4. Istio Envoy proxies perform a **hot-reload** of the new certificate without restart
5. Active connections continue with the old cert while new connections use the new cert (ensuring zero downtime)
6. Certificate metrics are monitored in Grafana during rollout

**Key Commands:**
```bash
kubectl annotate certificate <cert-name> -n <namespace> cert-manager.io/issue-temporary-certificate="true"
openssl s_client -connect api.acme.cloud:443 -servername api.acme.cloud | openssl x509 -noout -dates
```

**RTO:** Certificate rotation completed within 15 minutes of approval.

---

## 2. Database Reliability

**Question:**
> Explain the backup strategy for the primary PostgreSQL database, specifically how Point-in-Time Recovery (PITR) is implemented using pgBackRest and WAL archives.

**Source Documents:**
- `Database_Backup_Procedures.md`

**Expected Answer:**

**Backup Strategy for PostgreSQL (prod):**

| Type | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| Full backup | Daily at 02:00 UTC | 30 days | S3 + Glacier |
| WAL archives | Continuous | 7 days | S3 |

**pgBackRest Implementation:**
- Automated backups run via Kubernetes CronJob at 02:00 daily
- Command: `pgbackrest backup --type=full --stanza=main`
- Manual backups can be triggered before major changes

**Point-in-Time Recovery (PITR) Procedure:**
1. **Stop application traffic** - Update ingress to maintenance page
2. **Scale down apps** - `kubectl scale deployment --replicas=0 -l tier=app`
3. **Perform recovery** - `pgbackrest restore --type=time --target="2024-01-15 14:30:00"`
4. **Verify data** - Run consistency checks
5. **Resume traffic** - Scale apps back up

**Recovery Objectives:**
| Scenario | RTO | RPO |
|----------|-----|-----|
| Single table corruption | 30 min | 0 (WAL) |
| Full database loss | 2 hours | 1 hour |
| Complete region failure | 4 hours | 1 hour |

---

## 3. Incident Management

**Question:**
> In the event of a SEV-1 outage, what are the distinct responsibilities of the Incident Commander versus the Communication Lead, and which specific Slack channel is designated for primary coordination?

**Source Documents:**
- `Incident_Response_Procedures.md`
- `Emergency_SSL_Certificate_Rotation_Procedure.md`

**Expected Answer:**

**SEV-1 Definition:** Complete outage with 5-minute response time and immediate all-hands escalation.

**Incident Commander (IC) Responsibilities:**
1. **Declare severity** in #incident Slack channel
2. **Create war room** for SEV-1/SEV-2 incidents
3. **Assign roles**: Communications, Technical Lead, Scribe
4. **Coordinate response** until resolution

**Communication Lead Responsibilities:**
- Assigned by the Incident Commander as the "Communications" role
- Manages external and internal communications during the incident
- Provides status updates to stakeholders

**Primary Slack Channel:** `#incident` (also referenced as `#incidents` in some procedures)

**Note:** The Incident Commander is the first responder who coordinates the overall response, while the Communication Lead focuses specifically on stakeholder communication as a delegated role.

---

## 4. API Gateway Architecture

**Question:**
> How does the Kong API Gateway enforce rate limiting for the partner-api, and which specific Redis instance is utilized for tracking these limits to avoid contention with the main cache?

**Source Documents:**
- `API_Gateway_Configuration.md`

**Expected Answer:**

**Rate Limiting Tiers:**

| Tier | Requests/minute | Burst |
|------|-----------------|-------|
| Anonymous | 60 | 10 |
| Authenticated | 1000 | 100 |
| **Partner** | **5000** | **500** |
| Internal | Unlimited | - |

**Kong Rate Limiting Configuration for partner-api:**
```yaml
plugins:
- name: rate-limiting
  route: payment-api  # Similar pattern for partner routes
  config:
    minute: 100
    policy: redis
    redis_host: redis-ratelimit
```

**Dedicated Redis Instance:** `redis-ratelimit`

This is a dedicated Redis instance specifically for rate limiting counters, separate from the main application cache to avoid contention.

**Partner API Authentication:**
```yaml
plugins:
- name: key-auth
  route: partner-api
  config:
    key_names: ["X-API-Key"]
    hide_credentials: true
```

**Troubleshooting Rate Limits:**
- Check rate limit counters: `redis-cli GET rate-limit::<client_id>`
- Verify client tier classification
- For legitimate traffic spikes, temporarily increase limits