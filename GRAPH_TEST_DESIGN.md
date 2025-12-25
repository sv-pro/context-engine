# Graph-Only Test Cases

Test cases designed to **break semantic search** while **enabling graph traversal**.

## Design Principles
1. **Zero keyword overlap** between query and answer document
2. Connection **only** via entity links (WikiLinks)
3. At least **2 hops** required

---

## Test Case: gt001 - The Architect
**Query**: "Who designed the weapon used in Operation Nightfall?"

**Documents**:
- `operation_nightfall.md`: "Operation Nightfall deployed the EMP device codenamed Blackout."
- `blackout_device.md`: "Blackout was engineered by Dr. Helena Vance."
- `dr_helena_vance.md`: Entity node for Dr. Helena Vance.

**Why Semantic Fails**: Query mentions "weapon" and "Operation Nightfall". Neither term appears in `dr_helena_vance.md`.

**Why Graph Succeeds**: Nightfall -> Blackout -> Dr. Helena Vance

---

## Test Case: gt002 - The Location
**Query**: "What is the current status of the research conducted at Site Omega?"

**Documents**:
- `site_omega.md`: "Site Omega hosts Project Helios."
- `project_helios.md`: "Project Helios was terminated in 2024 due to budget cuts."

**Why Semantic Fails**: "current status" and "research" don't appear in `project_helios.md` termination notice.

**Why Graph Succeeds**: Site Omega -> Project Helios -> "terminated"

---

## Test Case: gt003 - The Predecessor
**Query**: "Who was the mentor of the current CEO of Nexus Corp?"

**Documents**:
- `nexus_corp.md`: "Nexus Corp is led by CEO Diana Ross."
- `diana_ross.md`: "Diana Ross was mentored by Victor Stone during her early career."
- `victor_stone.md`: Entity node for Victor Stone.

**Why Semantic Fails**: "mentor" appears in `diana_ross.md`, but query asks about "CEO of Nexus Corp" - no direct link.

**Why Graph Succeeds**: Nexus Corp -> Diana Ross -> Victor Stone

---

## Test Case: gt004 - The Supply Chain
**Query**: "Where are the raw materials for the Titan Rocket sourced from?"

**Documents**:
- `titan_rocket.md`: "The Titan Rocket uses the Prometheus Engine."
- `prometheus_engine.md`: "The Prometheus Engine is manufactured using rare earth metals from the Kobani Mine."
- `kobani_mine.md`: Entity node for Kobani Mine.

**Why Semantic Fails**: Query mentions "raw materials" and "Titan Rocket". Answer is in `kobani_mine.md` which mentions neither.

**Why Graph Succeeds**: Titan Rocket -> Prometheus Engine -> Kobani Mine
