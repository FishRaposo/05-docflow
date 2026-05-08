# Metadata Schema

## Document Metadata

Every document in DocFlow has a normalized metadata schema regardless of source format.

| Field | Type | Description | Example |
|---|---|---|---|
| `title` | str | Document title | "Company Handbook 2024" |
| `source` | str | Origin source name | "company-wiki" |
| `file_type` | str | File extension | "md", "pdf", "html" |
| `language` | str | Detected language code | "en", "pt" |
| `author` | str or None | Document author | "HR Department" |
| `created_date` | datetime or None | Document creation date | "2024-01-15" |
| `modified_date` | datetime or None | Last modified date | "2024-03-20" |
| `page_count` | int or None | Number of pages (PDF) | 42 |
| `word_count` | int | Total word count | 12500 |
| `read_time_minutes` | int | Estimated read time | 52 |
| `tags` | list[str] | Custom tags | ["handbook", "hr"] |
| `custom` | dict | Source-specific metadata | {"department": "Engineering"} |

## Chunk Metadata

Each chunk carries metadata for filtering and context:

| Field | Type | Description | Example |
|---|---|---|---|
| `chunk_index` | int | Zero-based position in document | 0, 1, 2 |
| `start_char` | int | Start position in source text | 0 |
| `end_char` | int | End position in source text | 512 |
| `section_header` | str or None | Parent section heading | "Introduction" |
| `section_level` | int or None | Heading level (1-6) | 2 |
| `page_number` | int or None | Source page (PDF) | 5 |
| `token_count` | int or None | Approximate token count | 128 |

## Version Metadata

Document versions track changes over time:

| Field | Type | Description | Example |
|---|---|---|---|
| `version` | int | Monotonically increasing version number | 1, 2, 3 |
| `fingerprint` | str | Content fingerprint (SHA-256) | "abc123..." |
| `change_type` | str | Type of change | "created", "updated", "minor" |
| `change_summary` | str or None | Human-readable change description | "Updated PTO policy" |
| `chunks_added` | int | New chunks in this version | 15 |
| `chunks_removed` | int | Removed chunks from previous | 3 |
| `chunks_modified` | int | Modified chunks | 7 |

## Custom Metadata

Sources can provide custom metadata that is preserved and searchable:

```json
{
  "custom": {
    "department": "Engineering",
    "classification": "internal",
    "review_date": "2024-12-31",
    "approved_by": "CTO"
  }
}
```

Custom metadata is stored as JSON and can be used for filtering in vector search queries.
