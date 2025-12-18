# Context Driver Interactive Lab 🧪

Follow these steps to experience the full power of your "Big Context" ingestion engine.

## Step 1: Open the Observation Deck
Open a terminal and run the following command to watch the driver's brain in real-time. Keep this window visible!
```bash
docker-compose logs -f context-driver
```

## Step 2: Create a Complex "Ghost" Node
Create a new file `./volumes/brain/Deep-Dive.md` with content that references things that don't exist yet:
```markdown
---
title: The Deep Dive
author: Dev User
tags: [experiment, graph]
priority: high
---
# The Deep Dive
This note tests the driver's ability to handle links to nodes that aren't yet in the database.
- It links to [[Future Concept]] (a Ghost Node).
- It links to [[System Architecture]] (an existing node).
- It has metadata fields that the driver will serialize to JSONB.
```
**Watch the logs**: You'll see the driver detect the file, parse the links, and upsert the note instantly.

## Step 3: Trigger a "Brain Update" (Metadata)
Modify the tags in `Deep-Dive.md` (e.g., change `priority: high` to `priority: critical`).
**Observation**: The driver will update the `metadata` column in Postgres without creating a duplicate.

## Step 4: Inspect the Graph State
Run this SQL query to see how the "Ghost" link and the existing link are stored:
```bash
docker-compose exec db psql -U postgres -d llmbox -c "
SELECT n.title as source, e.target_title as target 
FROM edges e 
JOIN notes n ON e.source_id = n.id 
WHERE n.title = 'The Deep Dive';"
```

## Step 5: Test Semantic Understanding (Embeddings)
The driver automatically vectorizes your notes. Let's find the ID of your new note and check its embedding:
```bash
docker-compose exec db psql -U postgres -d llmbox -c "SELECT id, title, left(embedding::text, 40) FROM notes WHERE title = 'The Deep Dive';"
```

## Step 6: Challenge the Driver (Broken YAML)
Intentionally break the YAML frontmatter in a new file (e.g., mismatched quotes).
**Watch the logs**: See how the driver handles the error gracefully and logs the failure without crashing.

---

### Key Concepts you are experiencing:
1.  **Watchdog Latency**: Notice how fast the ingestion happens after you save the file.
2.  **Schema Evolution**: Notice how `metadata` (JSONB) allows you to add arbitrary tags without changing the DB structure.
3.  **Graph Decoupling**: Notice how a link `[[Future Concept]]` is valid even if the file doesn't exist; the driver stores the *intent* of the link.
