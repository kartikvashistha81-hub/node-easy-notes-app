# EasyNotes Application

Build a Restful CRUD API for a simple Note-Taking application using Node.js, Express and MongoDB.

## Steps to Setup

1. Install dependencies

```bash
npm install
```

2. Run Server

```bash
node server.js
```

You can browse the apis at <http://localhost:3000>

## Tutorial
You can find the tutorial for this application at [The CalliCoder Blog](https://www.callicoder.com) - 

<https://www.callicoder.com/node-js-express-mongodb-restful-crud-api-tutorial/>

---

## Organise & Search Notes (added)

Notes can now carry a **category** (single, e.g. `"Work"`) and any number of
**tags** (e.g. `["urgent", "ideas"]`), and can be searched/filtered/sorted
through the API or the bundled web UI.

### Running with the new feature

```bash
npm install
cp .env.example .env      # optional: point at a real MongoDB instance
npm start                 # same as `node server.js`
```

Open <http://localhost:3000> for the search & filter UI, or use the API
directly (see below). The UI now lives at `/`; the original JSON welcome
message moved to `/api`.

### Migrating existing data

If you already have notes saved from before this feature, backfill their
new fields once with:

```bash
npm run migrate
```

This sets `category: "Uncategorized"` and `tags: []` on any note missing
those fields. New notes get sensible defaults automatically and don't need
this step.

### Running tests

```bash
npm test
```

Runs `test/notes.controller.test.js`, a dependency-free smoke test (Node's
built-in `node:test`) that exercises the real controller logic -- including
search, tag/category filtering, and sorting -- against an in-memory stub, so
it works without a live MongoDB connection.

### API changes

**Note fields** (in addition to existing `title`, `content`):

| Field      | Type       | Default          | Notes                                   |
|------------|------------|------------------|------------------------------------------|
| `category` | `String`   | `"Uncategorized"`| Trimmed; single value per note           |
| `tags`     | `[String]` | `[]`             | Trimmed, lower-cased, deduplicated       |

`POST /notes` and `PUT /notes/:noteId` now also accept `category` (string)
and `tags` (array of strings, OR a comma-separated string -- both work) in
the request body. Both are optional.

**GET /notes** (backward compatible -- identical to before when called with
no query parameters) now also accepts:

| Query param  | Example                | Meaning                                           |
|--------------|-------------------------|----------------------------------------------------|
| `q`          | `?q=meeting`            | Case-insensitive search across title + content     |
| `tags`       | `?tags=work,urgent`     | Filter by tag(s), comma-separated                  |
| `tagsMatch`  | `?tagsMatch=all`        | `any` (default) or `all` -- how the tags list combines |
| `category`   | `?category=Work`        | Exact category match                               |
| `sortBy`     | `?sortBy=title`         | `title` \| `createdAt` (default) \| `updatedAt`     |
| `order`      | `?order=asc`            | `asc` or `desc` (default)                           |

All of the above are combinable, e.g.:

```
GET /notes?q=roadmap&category=Work&tags=planning&sortBy=title&order=asc
```

**New endpoints:**

```
GET /notes/search        Same query params as GET /notes above; a clearer, dedicated path.
GET /notes/tags          -> ["errands", "food", "planning", ...]   Distinct tags in use.
GET /notes/categories    -> ["Uncategorized", "Work", ...]         Distinct categories in use.
```

### Example requests

```bash
# Create a note with tags and a category
curl -X POST http://localhost:3000/notes \
  -H "Content-Type: application/json" \
  -d '{"title":"Q3 roadmap","content":"Draft the roadmap doc","tags":["work","planning"],"category":"Work"}'

# Search + filter + sort, combined
curl "http://localhost:3000/notes?q=roadmap&category=Work&sortBy=title&order=asc"

# All tags currently in use (for a filter dropdown)
curl http://localhost:3000/notes/tags
```

---

## Organise & Search Notes (added)

Notes can now carry a **category** (single, e.g. `"Work"`) and any number of
**tags** (e.g. `["urgent", "ideas"]`), and can be searched/filtered/sorted
through the API or the bundled web UI.

### Running with the new feature

```bash
npm install
cp .env.example .env      # optional: point at a real MongoDB instance
npm start                 # same as `node server.js`
```

Open <http://localhost:3000> for the search & filter UI, or use the API
directly (see below). The UI now lives at `/`; the original JSON welcome
message moved to `/api`.

### Migrating existing data

If you already have notes saved from before this feature, backfill their
new fields once with:

```bash
npm run migrate
```

This sets `category: "Uncategorized"` and `tags: []` on any note missing
those fields. New notes get sensible defaults automatically and don't need
this step.

### Running tests

```bash
npm test
```

Runs `test/notes.controller.test.js`, a dependency-free smoke test (Node's
built-in `node:test`) that exercises the real controller logic -- including
search, tag/category filtering, and sorting -- against an in-memory stub, so
it works without a live MongoDB connection.

### API changes

**Note fields** (in addition to existing `title`, `content`):

| Field      | Type       | Default          | Notes                                   |
|------------|------------|------------------|------------------------------------------|
| `category` | `String`   | `"Uncategorized"`| Trimmed; single value per note           |
| `tags`     | `[String]` | `[]`             | Trimmed, lower-cased, deduplicated       |

`POST /notes` and `PUT /notes/:noteId` now also accept `category` (string)
and `tags` (array of strings, OR a comma-separated string -- both work) in
the request body. Both are optional.

**GET /notes** (backward compatible -- identical to before when called with
no query parameters) now also accepts:

| Query param  | Example                | Meaning                                           |
|--------------|-------------------------|----------------------------------------------------|
| `q`          | `?q=meeting`            | Case-insensitive search across title + content     |
| `tags`       | `?tags=work,urgent`     | Filter by tag(s), comma-separated                  |
| `tagsMatch`  | `?tagsMatch=all`        | `any` (default) or `all` -- how the tags list combines |
| `category`   | `?category=Work`        | Exact category match                               |
| `sortBy`     | `?sortBy=title`         | `title` \| `createdAt` (default) \| `updatedAt`     |
| `order`      | `?order=asc`            | `asc` or `desc` (default)                           |

All of the above are combinable, e.g.:

```
GET /notes?q=roadmap&category=Work&tags=planning&sortBy=title&order=asc
```

**New endpoints:**

```
GET /notes/search        Same query params as GET /notes above; a clearer, dedicated path.
GET /notes/tags          -> ["errands", "food", "planning", ...]   Distinct tags in use.
GET /notes/categories    -> ["Uncategorized", "Work", ...]         Distinct categories in use.
```

### Example requests

```bash
# Create a note with tags and a category
curl -X POST http://localhost:3000/notes \
  -H "Content-Type: application/json" \
  -d '{"title":"Q3 roadmap","content":"Draft the roadmap doc","tags":["work","planning"],"category":"Work"}'

# Search + filter + sort, combined
curl "http://localhost:3000/notes?q=roadmap&category=Work&sortBy=title&order=asc"

# All tags currently in use (for a filter dropdown)
curl http://localhost:3000/notes/tags
```

---

## Organise & Search Notes (added)

Notes can now carry a **category** (single, e.g. `"Work"`) and any number of
**tags** (e.g. `["urgent", "ideas"]`), and can be searched/filtered/sorted
through the API or the bundled web UI.

### Running with the new feature

```bash
npm install
cp .env.example .env      # optional: point at a real MongoDB instance
npm start                 # same as `node server.js`
```

Open <http://localhost:3000> for the search & filter UI, or use the API
directly (see below). The UI now lives at `/`; the original JSON welcome
message moved to `/api`.

### Migrating existing data

If you already have notes saved from before this feature, backfill their
new fields once with:

```bash
npm run migrate
```

This sets `category: "Uncategorized"` and `tags: []` on any note missing
those fields. New notes get sensible defaults automatically and don't need
this step.

### Running tests

```bash
npm test
```

Runs `test/notes.controller.test.js`, a dependency-free smoke test (Node's
built-in `node:test`) that exercises the real controller logic -- including
search, tag/category filtering, and sorting -- against an in-memory stub, so
it works without a live MongoDB connection.

### API changes

**Note fields** (in addition to existing `title`, `content`):

| Field      | Type       | Default          | Notes                                   |
|------------|------------|------------------|------------------------------------------|
| `category` | `String`   | `"Uncategorized"`| Trimmed; single value per note           |
| `tags`     | `[String]` | `[]`             | Trimmed, lower-cased, deduplicated       |

`POST /notes` and `PUT /notes/:noteId` now also accept `category` (string)
and `tags` (array of strings, OR a comma-separated string -- both work) in
the request body. Both are optional.

**GET /notes** (backward compatible -- identical to before when called with
no query parameters) now also accepts:

| Query param  | Example                | Meaning                                           |
|--------------|-------------------------|----------------------------------------------------|
| `q`          | `?q=meeting`            | Case-insensitive search across title + content     |
| `tags`       | `?tags=work,urgent`     | Filter by tag(s), comma-separated                  |
| `tagsMatch`  | `?tagsMatch=all`        | `any` (default) or `all` -- how the tags list combines |
| `category`   | `?category=Work`        | Exact category match                               |
| `sortBy`     | `?sortBy=title`         | `title` \| `createdAt` (default) \| `updatedAt`     |
| `order`      | `?order=asc`            | `asc` or `desc` (default)                           |

All of the above are combinable, e.g.:

```
GET /notes?q=roadmap&category=Work&tags=planning&sortBy=title&order=asc
```

**New endpoints:**

```
GET /notes/search        Same query params as GET /notes above; a clearer, dedicated path.
GET /notes/tags          -> ["errands", "food", "planning", ...]   Distinct tags in use.
GET /notes/categories    -> ["Uncategorized", "Work", ...]         Distinct categories in use.
```

### Example requests

```bash
# Create a note with tags and a category
curl -X POST http://localhost:3000/notes \
  -H "Content-Type: application/json" \
  -d '{"title":"Q3 roadmap","content":"Draft the roadmap doc","tags":["work","planning"],"category":"Work"}'

# Search + filter + sort, combined
curl "http://localhost:3000/notes?q=roadmap&category=Work&sortBy=title&order=asc"

# All tags currently in use (for a filter dropdown)
curl http://localhost:3000/notes/tags
```
