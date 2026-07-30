# Execution Plan

**User request:** Improve the application so users can better organise and search their notes.

**Feature selected:** Tagging, Categorization & Combined Search/Filter/Sort for Notes

Add `tags` (many-valued) and `category` (single-valued) to notes, expose combined search/filter/sort over title, content, tags and category via the API, and ship a minimal server-served UI that exercises all of it end to end.

## Repository Understanding

- Language: `javascript`
- Framework: `express`
- Database / ORM: `mongodb` / `mongoose`
- Frontend present: `True`
- Entry point: `server.js`

**Existing endpoints discovered:**

- `POST /notes` -> `notes.create` (in `app\routes\note.routes.js`)
- `GET /notes` -> `notes.findAll` (in `app\routes\note.routes.js`)
- `GET /notes/search` -> `notes.search` (in `app\routes\note.routes.js`)
- `GET /notes/tags` -> `notes.listTags` (in `app\routes\note.routes.js`)
- `GET /notes/categories` -> `notes.listCategories` (in `app\routes\note.routes.js`)
- `GET /notes/:noteId` -> `notes.findOne` (in `app\routes\note.routes.js`)
- `PUT /notes/:noteId` -> `notes.update` (in `app\routes\note.routes.js`)
- `DELETE /notes/:noteId` -> `notes.delete` (in `app\routes\note.routes.js`)

**Existing models discovered:**

- `Note`: title: String, content: String, type: [String], type: String

<details><summary>Full directory tree</summary>

```
node-easy-notes-app/
├── app/
│   ├── controllers/
│   │   └── note.controller.js
│   ├── models/
│   │   └── note.model.js
│   └── routes/
│       └── note.routes.js
├── config/
│   └── database.config.js
├── public/
│   ├── app.js
│   ├── index.html
│   └── style.css
├── scripts/
│   └── migrate-add-tags-category.js
├── test/
│   └── notes.controller.test.js
├── .env.example
├── .gitignore
├── execution_plan.md
├── package-lock.json
├── package.json
├── Readme.md
└── server.js
```

</details>

## Decision Making

1. The Note model currently only has `title` and `content`. There is no structured way to group or filter notes, so free-text search alone would not satisfy 'better organise' -- organisation requires new structured fields, not just a smarter query.
2. Chose BOTH tags (many-to-many, free-form) and category (one-per-note, constrained) rather than either alone: tags answer 'what is this note about' (multiple facets), category answers 'which bucket does this note live in' (single, mutually-exclusive grouping). Real note apps (Evernote, Notion, Google Keep) all converge on this same combination.
3. Existing GET /notes endpoint is left backward compatible: with no query parameters it behaves exactly as before. Search/filter/sort are added as *optional* query parameters on the same endpoint, plus a dedicated GET /notes/search alias for clarity, so no existing client integration breaks.
4. Because MongoDB is schemaless, existing documents saved before this change won't have `tags`/`category` fields. A migration script is added to backfill sane defaults (`tags: []`, `category: 'Uncategorized'`) on existing data rather than leaving old notes to silently behave differently from new ones.
5. The DB connection string was hardcoded in config/database.config.js. Externalized it to read from an environment variable (via dotenv, a single lightweight dependency) with the original hardcoded value kept as the fallback default -- this is a drive-by improvement that doesn't change runtime behavior for anyone who doesn't set the env var, but unblocks deploying against a real database (e.g. MongoDB Atlas) without editing source.

## Alternatives Considered

- Considered a single 'folder' hierarchy instead of category+tags -- rejected because it doesn't support a note belonging to more than one logical grouping, which tags explicitly need to allow.
- Considered MongoDB full-text $text index only, without regex fallback -- kept regex-based search as well because $text indexes require an explicit index creation step that may not exist on older deployments of this exact database; regex $or search works with zero extra setup and is combined with the text index for performance when available.

## Task Breakdown

| ID | Action | Title | Target |
|----|--------|-------|--------|
| T1 | modify | Extend Note schema with tags and category | `note_model` |
| T2 | modify | Accept tags/category on create and update | `note_controller` |
| T3 | modify | Implement combined search/filter/sort controller logic | `note_controller` |
| T4 | modify | Wire new routes | `note_routes` |
| T5 | modify | Externalize DB config via dotenv | `db_config` |
| T6 | modify | Load dotenv and serve static frontend from server entry | `server_entry` |
| T7 | create | Build search & filter UI | `frontend_root` |
| T8 | create | Add data migration script | `migration_script` |
| T9 | modify | Add dotenv dependency and npm scripts | `package_manifest` |
| T10 | create | Add automated smoke tests for the new feature | `test_suite` |
| T11 | modify | Update README with new API documentation | `readme` |
| T12 | create | Add .env.example | `env_example` |
| T13 | modify | Extend .gitignore | `gitignore` |

### T1. Extend Note schema with tags and category

Add `tags: [String]` (indexed) and `category: String` (default 'Uncategorized', indexed) fields to the Note Mongoose schema, plus a text index across title/content for efficient search.

*Why:* Structured fields are required before any search/filter logic can use them.

### T2. Accept tags/category on create and update

Update the create and update controller functions to accept, validate, and normalize `tags` (array of trimmed, deduped, lower-cased strings) and `category` (trimmed string, defaults to 'Uncategorized') from the request body.

*Why:* Users need to actually set tags/category when creating or editing a note.

### T3. Implement combined search/filter/sort controller logic

Add a `search` controller function supporting: free-text `q` across title+content, `tags` filter (comma-separated, with `tagsMatch=any|all` semantics), exact `category` filter, and `sortBy`/`order` sorting -- all combinable in a single query. Also add `listTags` and `listCategories` controller functions returning the distinct values currently in use, for populating filter UI dropdowns.

*Why:* This is the core of the requested feature: organising AND searching.

### T4. Wire new routes

Add GET /notes/search (explicit alias), GET /notes/tags, and GET /notes/categories. Enhance the existing GET /notes to apply the same optional filters when query params are present, while remaining byte-for-byte identical in behavior when they are absent.

*Why:* New controller logic needs HTTP routes to be reachable.

### T5. Externalize DB config via dotenv

Read the MongoDB connection URL from process.env.MONGODB_URI, falling back to the original hardcoded local URL.

*Why:* Enables running against a real database without editing source; zero behavior change by default.

### T6. Load dotenv and serve static frontend from server entry

Require and configure `dotenv` at the top of the server entry file, and add `express.static('public')` so the new frontend is served.

*Why:* Both the env config and the new UI need to be wired into the running server.

### T7. Build search & filter UI

Create a minimal, dependency-free static frontend (index.html + app.js + style.css) under public/: note list, create/edit form with a tags input and category select, a search box, tag filter chips, a category dropdown, and a sort control -- all wired to the new API endpoints with no build step.

*Why:* The assignment explicitly asks for search UI and filtering UI; none currently exists.

### T8. Add data migration script

Create scripts/migrate-add-tags-category.js: a standalone Node script that connects to the configured database and backfills `tags: []` / `category: 'Uncategorized'` onto any existing Note documents missing those fields.

*Why:* MongoDB is schemaless -- old documents won't retroactively gain the new fields on their own.

### T9. Add dotenv dependency and npm scripts

Add `dotenv` to package.json dependencies, and add `start`, `migrate`, and `test` npm scripts.

*Why:* Required so `npm start` / `npm run migrate` / `npm test` work out of the box.

### T10. Add automated smoke tests for the new feature

Create test/notes.controller.test.js: a dependency-free Node test (uses only Node's built-in `assert` and `node:test` modules) that stubs the Mongoose Note model in-memory and exercises create/search/filter/sort/tag logic end to end.

*Why:* Verifies the new business logic actually works without requiring a live MongoDB instance -- important for CI and for grading environments that may not have MongoDB installed.

### T11. Update README with new API documentation

Document the new fields, the new/enhanced endpoints with example requests, the migration script, and how to run the new UI and tests.

*Why:* Existing README only documents the original 5 CRUD endpoints.

### T12. Add .env.example

Create .env.example documenting MONGODB_URI and PORT with sane defaults matching the fallback values used in code.

*Why:* Required scaffolding so contributors know which env vars the new dotenv config reads.

### T13. Extend .gitignore

Add `.env` to the existing .gitignore (currently only lists node_modules/) so real credentials are never committed.

*Why:* A .env file will now plausibly contain a real MongoDB connection string.
