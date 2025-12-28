# Sub-Brains: Scoped Knowledge Areas

Sub-brains allow you to scope knowledge base operations to specific subdirectories of your brain. This is useful for:

- **Different apps**: Scope to `projects/myapp/` for app-specific documentation
- **Different modes**: Scope to `modes/debug/` for debugging runbooks
- **Teams or domains**: Scope to `teams/frontend/` for frontend docs

## How It Works

1. **Directory structure is your sub-brain structure**: Any subdirectory in your brain can become a sub-brain
2. **Search and list operations accept `sub_path`**: Filter results to only include documents from that path
3. **`BRAIN_SUBDIR` environment variable**: Set a default sub-brain for all operations
4. **`.brainignore` prevents duplicate indexing**: If a sub-brain should be indexed separately, add it to `.brainignore` in the parent

## Configuration

### Environment Variable: `BRAIN_SUBDIR`

Set a default sub-brain path that applies to all operations when no explicit `sub_path` is provided:

```bash
# In .env file
BRAIN_SUBDIR=projects/myapp
```

This is useful when deploying multiple instances of the context-driver, each scoped to a different sub-brain:

```yaml
# docker-compose.yml example - multiple sub-brain instances
services:
  context-driver-myapp:
    environment:
      - BRAIN_SUBDIR=projects/myapp
    ports:
      - "8001:8000"
  
  context-driver-debug:
    environment:
      - BRAIN_SUBDIR=modes/debug
    ports:
      - "8002:8000"
```

**Note**: Request-level `sub_path` always overrides `BRAIN_SUBDIR`.

## Using Sub-Brains

### Via API

```bash
# Search only within a sub-brain
curl -X POST "http://localhost:8000/tools/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "SSL certificates", "sub_path": "projects/myapp"}'

# List articles in a sub-brain
curl "http://localhost:8000/tools/articles?sub_path=projects/myapp"

# Discover available sub-brains
curl "http://localhost:8000/tools/sub-brains"
```

### Via Python Tools (brain_rag.py)

```python
from brain_rag import Tools

# Create a scoped instance (all operations use this sub_path)
myapp_brain = Tools(sub_path="projects/myapp")
results = myapp_brain.search_knowledge_base("SSL certificates")

# Or scope a single call
tools = Tools()
results = tools.search_knowledge_base("SSL certificates", sub_path="projects/myapp")

# Create child instances for different scopes
debug_brain = tools.scoped("modes/debug")
```

## `.brainignore` - Excluding Sub-Brains

When the root brain is scanned, you may want to exclude sub-brains that should be indexed independently. Create a `.brainignore` file in any directory to exclude subdirectories from that scan.

### Format

```text
# .brainignore - placed in brain root or any subdirectory

# Ignore these sub-brains (one per line)
projects/myapp
modes/debug

# Comments start with #
# Blank lines are ignored
```

### Example Directory Structure

```
brain/
├── .brainignore          # Contains: projects/myapp
├── general/
│   └── readme.md
├── projects/
│   ├── myapp/            # Ignored from root scan, indexed separately
│   │   ├── setup.md
│   │   └── api.md
│   └── other/
│       └── docs.md       # Included in root scan
└── modes/
    └── debug/
        └── runbook.md
```

With this setup:
- Root brain indexes: `general/readme.md`, `projects/other/docs.md`, `modes/debug/runbook.md`
- `projects/myapp` sub-brain indexes: `setup.md`, `api.md` (independently)

### Nested `.brainignore`

Each directory can have its own `.brainignore`. Patterns are relative to that directory.

```
brain/
├── projects/
│   ├── .brainignore      # Contains: experimental
│   ├── myapp/
│   └── experimental/     # Ignored when scanning projects/
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /tools/search` | Search with optional `sub_path` |
| `GET /tools/search` | GET search with optional `sub_path` query param |
| `GET /tools/articles` | List articles with optional `sub_path` filter |
| `GET /tools/sub-brains` | Discover available sub-brains |

## Best Practices

1. **Keep sub-brain paths meaningful**: Use descriptive names like `projects/`, `modes/`, `domains/`
2. **Use `.brainignore` for independent sub-brains**: If a sub-brain needs its own isolated index
3. **Consider search strategies**: Sub-brains with fewer documents might benefit from `semantic` over `super_hybrid`
4. **Document your sub-brain structure**: Maintain a guide for your team on what sub-brains exist
