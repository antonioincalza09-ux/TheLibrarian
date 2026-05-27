# Knowledge Graph Schema

The Librarian builds an offline directed graph from `manifest.json`, sidecar YAML, plan data, notes, runbooks, and runnable helper scripts.

## JSON Shape

`.librarian/graph.json` is the machine-readable source for graph exports:

```json
{
  "nodes": [
    {
      "id": "node_id",
      "type": "File",
      "label": "main.py",
      "properties": {}
    }
  ],
  "edges": [
    {
      "source": "source_id",
      "target": "target_id",
      "type": "HAS_TAG",
      "confidence": 1.0,
      "reason": "Tag declared in sidecar metadata.",
      "properties": {}
    }
  ]
}
```

Each node has `id`, `label`, `type`, and `properties`. Each edge has `source`, `target`, `type`, `confidence`, `reason`, and `properties`.

## Node Types

- Filesystem: `File`, `Directory`, `OriginalPath`, `CurrentPath`, `ProposedPath`
- Metadata: `Tag`, `Entity`, `Person`, `Organization`, `Place`, `Date`, `Domain`, `Category`, `MIMEType`, `Extension`
- Code intelligence: `CodeFile`, `Module`, `Package`, `Function`, `Class`, `Method`, `Import`, `ExternalDependency`, `Entrypoint`, `Test`, `Framework`, `ConfigFile`, `GeneratedFile`, `VendorFile`, `LockFile`
- Developer experience: `MarkdownNote`, `Runbook`, `RunnableScript`, `Risk`, `Warning`, `AgentContext`, `PromptPack`
- Project inference: `Project`, `Component`, `Feature`, `Cluster`

## Edge Types

- Filesystem: `CONTAINS`, `ORIGINAL_PARENT`, `CURRENT_PARENT`, `PROPOSED_PARENT`, `MOVED_TO`
- Metadata: `HAS_TAG`, `MENTIONS_PERSON`, `MENTIONS_ORGANIZATION`, `MENTIONS_PLACE`, `MENTIONS_DATE`, `CLASSIFIED_AS`, `BELONGS_TO_DOMAIN`, `HAS_MIME_TYPE`, `HAS_EXTENSION`, `PART_OF_PROJECT`, `SIMILAR_TO`
- Code: `DEFINES`, `IMPORTS`, `PART_OF_PACKAGE`, `HAS_ENTRYPOINT`, `TESTS`, `USES_FRAMEWORK`, `HAS_CONFIG`, `GENERATED_FROM`, `SHOULD_NOT_MODIFY`, `HAS_RISK`
- Developer experience: `DOCUMENTED_BY`, `EXPLAINED_IN`, `HAS_RUNBOOK`, `HAS_RUNNABLE_HELPER`, `SCRIPT_READS`, `AGENT_SHOULD_START_FROM`

Inferred edges always include `confidence` and `reason`.

## Generated Files

```text
.librarian/
  graph.json
  graph.graphml
  graph.cypher
  graph.ttl
  graph_index.sqlite
  graph_report.md
  validation_report.json
  validation_report.md
  graph_notes/
```

GraphML is intended for tools such as Gephi, yEd, and NetworkX. Cypher uses sanitized labels, ids, paths, quotes, and newlines for Neo4j import review. Turtle is emitted with a compact local schema prefix and requires no `rdflib` dependency. `graph_index.sqlite` contains `nodes` and `edges` tables for quick local inspection.
