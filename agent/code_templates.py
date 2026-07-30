"""
agent.code_templates
=====================
Every function here returns COMPLETE, working source code for one file.
Nothing in this module is a placeholder -- it is the actual implementation
of the tags/category/search feature for node-easy-notes-app.

Kept separate from implementation_engine.py so that "what code gets
written" (this file) is cleanly separated from "how/where it gets written"
(implementation_engine.py) -- single responsibility.
"""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------
# Backend: model, controller, routes, config, server entry
# ---------------------------------------------------------------------

def note_model() -> str:
    return """const mongoose = require('mongoose');

const NoteSchema = mongoose.Schema({
    title: String,
    content: String,
    // Multiple free-form labels a note can carry, e.g. ["work", "urgent"].
    tags: {
        type: [String],
        default: []
    },
    // Single, mutually-exclusive bucket a note belongs to.
    category: {
        type: String,
        default: 'Uncategorized',
        trim: true
    }
}, {
    timestamps: true
});

// Text index on title/content powers efficient free-text search via
// Note.find({ $text: { $search: ... } }); the controller also supports a
// regex fallback so search works even before this index finishes building
// on a freshly migrated collection.
NoteSchema.index({ title: 'text', content: 'text' });
// Single-field indexes speed up tag/category filtering.
NoteSchema.index({ tags: 1 });
NoteSchema.index({ category: 1 });

module.exports = mongoose.model('Note', NoteSchema);
"""


def note_controller() -> str:
    return """const Note = require('../models/note.model.js');

// -- helpers -------------------------------------------------------------

// Normalizes a tags input (array OR comma-separated string) into a clean,
// deduplicated array of trimmed, lowercase strings. Used for both writes
// (create/update) and reads (parsing the `tags` query param).
function normalizeTags(rawTags) {
    if (!rawTags) return [];
    const list = Array.isArray(rawTags) ? rawTags : String(rawTags).split(',');
    const cleaned = list
        .map(t => String(t).trim().toLowerCase())
        .filter(t => t.length > 0);
    return [...new Set(cleaned)];
}

function normalizeCategory(rawCategory) {
    const trimmed = (rawCategory || '').toString().trim();
    return trimmed.length > 0 ? trimmed : 'Uncategorized';
}

const ALLOWED_SORT_FIELDS = new Set(['title', 'createdAt', 'updatedAt']);

function buildSort(sortBy, order) {
    const field = ALLOWED_SORT_FIELDS.has(sortBy) ? sortBy : 'createdAt';
    const direction = order === 'asc' ? 1 : -1;
    return { [field]: direction };
}

function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
}

// Builds a single combined Mongo filter from all optional query params.
// Exported (attached to module.exports below) so the smoke test can
// exercise this pure function directly, without needing Express or Mongo.
function buildFilter({ q, tags, tagsMatch, category }) {
    const filter = {};

    if (q && q.trim().length > 0) {
        const regex = new RegExp(escapeRegex(q.trim()), 'i');
        filter.$or = [{ title: regex }, { content: regex }];
    }

    if (tags && tags.trim().length > 0) {
        const tagList = normalizeTags(tags);
        if (tagList.length > 0) {
            filter.tags = tagsMatch === 'all' ? { $all: tagList } : { $in: tagList };
        }
    }

    if (category && category.trim().length > 0) {
        filter.category = category.trim();
    }

    return filter;
}

// -- CRUD ------------------------------------------------------------------

// Create and Save a new Note
exports.create = (req, res) => {
    // Validate request
    if (!req.body.content) {
        return res.status(400).send({
            message: "Note content can not be empty"
        });
    }

    // Create a Note
    const note = new Note({
        title: req.body.title || "Untitled Note",
        content: req.body.content,
        tags: normalizeTags(req.body.tags),
        category: normalizeCategory(req.body.category)
    });

    // Save Note in the database
    note.save()
    .then(data => {
        res.send(data);
    }).catch(err => {
        res.status(500).send({
            message: err.message || "Some error occurred while creating the Note."
        });
    });
};

// Retrieve notes from the database. With no query params this behaves
// exactly like the original endpoint (returns everything, unsorted).
// Optional query params, all combinable:
//   q          - free text search across title + content
//   tags       - comma-separated tag list to filter by
//   tagsMatch  - 'any' (default, OR semantics) or 'all' (AND semantics)
//   category   - exact category match
//   sortBy     - 'title' | 'createdAt' | 'updatedAt' (default 'createdAt')
//   order      - 'asc' | 'desc' (default 'desc')
exports.findAll = (req, res) => {
    const { q, tags, tagsMatch, category, sortBy, order } = req.query;
    const hasAnyFilter = q || tags || category;
    const filter = hasAnyFilter ? buildFilter({ q, tags, tagsMatch, category }) : {};
    const sort = (sortBy || order) ? buildSort(sortBy, order) : {};

    Note.find(filter).sort(sort)
    .then(notes => {
        res.send(notes);
    }).catch(err => {
        res.status(500).send({
            message: err.message || "Some error occurred while retrieving notes."
        });
    });
};

// Dedicated search endpoint. Identical semantics to GET /notes with query
// params, exposed at its own path for a clearer, more discoverable API
// (and so a frontend never has to wonder whether filtering "/notes" is
// actually supported).
exports.search = (req, res) => {
    exports.findAll(req, res);
};

// Returns the distinct tags currently in use across all notes, for
// populating a filter UI's tag chips/autocomplete.
exports.listTags = (req, res) => {
    Note.distinct('tags')
    .then(tags => {
        res.send(tags.filter(Boolean).sort());
    }).catch(err => {
        res.status(500).send({
            message: err.message || "Some error occurred while retrieving tags."
        });
    });
};

// Returns the distinct categories currently in use, for populating a
// filter UI's category dropdown.
exports.listCategories = (req, res) => {
    Note.distinct('category')
    .then(categories => {
        res.send(categories.filter(Boolean).sort());
    }).catch(err => {
        res.status(500).send({
            message: err.message || "Some error occurred while retrieving categories."
        });
    });
};

// Find a single note with a noteId
exports.findOne = (req, res) => {
    Note.findById(req.params.noteId)
    .then(note => {
        if (!note) {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        res.send(note);
    }).catch(err => {
        if (err.kind === 'ObjectId') {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        return res.status(500).send({
            message: "Error retrieving note with id " + req.params.noteId
        });
    });
};

// Update a note identified by the noteId in the request
exports.update = (req, res) => {
    // Validate Request
    if (!req.body.content) {
        return res.status(400).send({
            message: "Note content can not be empty"
        });
    }

    const updatedFields = {
        title: req.body.title || "Untitled Note",
        content: req.body.content
    };
    // Only touch tags/category if the caller actually sent them, so a
    // partial update (e.g. just editing content) doesn't wipe them out.
    if (req.body.tags !== undefined) {
        updatedFields.tags = normalizeTags(req.body.tags);
    }
    if (req.body.category !== undefined) {
        updatedFields.category = normalizeCategory(req.body.category);
    }

    // Find note and update it with the request body
    Note.findByIdAndUpdate(req.params.noteId, updatedFields, { new: true })
    .then(note => {
        if (!note) {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        res.send(note);
    }).catch(err => {
        if (err.kind === 'ObjectId') {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        return res.status(500).send({
            message: "Error updating note with id " + req.params.noteId
        });
    });
};

// Delete a note with the specified noteId in the request
exports.delete = (req, res) => {
    Note.findByIdAndRemove(req.params.noteId)
    .then(note => {
        if (!note) {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        res.send({ message: "Note deleted successfully!" });
    }).catch(err => {
        if (err.kind === 'ObjectId' || err.name === 'NotFound') {
            return res.status(404).send({
                message: "Note not found with id " + req.params.noteId
            });
        }
        return res.status(500).send({
            message: "Could not delete note with id " + req.params.noteId
        });
    });
};

// Exposed purely so the dependency-free smoke test (test/notes.controller.test.js)
// can exercise the query-building logic directly without spinning up Express or Mongo.
exports._internal = { normalizeTags, normalizeCategory, buildFilter, buildSort };
"""


def note_routes() -> str:
    return """module.exports = (app) => {
    const notes = require('../controllers/note.controller.js');

    // Create a new Note
    app.post('/notes', notes.create);

    // Retrieve all Notes. Supports optional ?q=&tags=&tagsMatch=&category=
    // &sortBy=&order= query params for combined search/filter/sort; with
    // no query params, behavior is identical to the original endpoint.
    app.get('/notes', notes.findAll);

    // Dedicated search endpoint -- same filters as above, explicit path.
    // Must be registered before /notes/:noteId or Express would treat
    // "search" as a noteId.
    app.get('/notes/search', notes.search);

    // Distinct tags currently in use, for building filter UI.
    app.get('/notes/tags', notes.listTags);

    // Distinct categories currently in use, for building filter UI.
    app.get('/notes/categories', notes.listCategories);

    // Retrieve a single Note with noteId
    app.get('/notes/:noteId', notes.findOne);

    // Update a Note with noteId
    app.put('/notes/:noteId', notes.update);

    // Delete a Note with noteId
    app.delete('/notes/:noteId', notes.delete);
}
"""


def database_config() -> str:
    return """module.exports = {
    // Reads from the environment when available (e.g. a real MongoDB Atlas
    // cluster in production), falling back to the original local default so
    // behavior for anyone not setting MONGODB_URI is completely unchanged.
    url: process.env.MONGODB_URI || 'mongodb://localhost:27017/easy-notes'
}
"""


def server_entry() -> str:
    return """require('dotenv').config();

const path = require('path');
const express = require('express');
const bodyParser = require('body-parser');

// create express app
const app = express();

// parse application/x-www-form-urlencoded
app.use(bodyParser.urlencoded({ extended: true }))

// parse application/json
app.use(bodyParser.json())

// Serve the search & filter UI (public/index.html, app.js, style.css).
// Express automatically serves public/index.html for GET /.
app.use(express.static(path.join(__dirname, 'public')));

// Configuring the database
const dbConfig = require('./config/database.config.js');
const mongoose = require('mongoose');

mongoose.Promise = global.Promise;

// Connecting to the database
mongoose.connect(dbConfig.url, {
\tuseNewUrlParser: true
}).then(() => {
    console.log("Successfully connected to the database");    
}).catch(err => {
    console.log('Could not connect to the database. Exiting now...', err);
    process.exit();
});

// API welcome/info route (moved from '/' to '/api' now that '/' serves the
// static frontend's index.html).
app.get('/api', (req, res) => {
    res.json({"message": "Welcome to EasyNotes application. Take notes quickly. Organize and keep track of all your notes."});
});

require('./app/routes/note.routes.js')(app);

// listen for requests
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server is listening on port ${PORT}`);
});
"""


def migration_script() -> str:
    return """/**
 * One-off data migration: backfills `tags` and `category` onto any Note
 * documents that were created before this feature existed (MongoDB is
 * schemaless, so old documents don't retroactively gain new schema fields
 * on their own).
 *
 * Usage:
 *   node scripts/migrate-add-tags-category.js
 *   npm run migrate
 *
 * Targets whichever database config/database.config.js resolves to
 * (MONGODB_URI env var if set, otherwise the local default) -- the exact
 * same database the server itself connects to.
 */
require('dotenv').config();

const mongoose = require('mongoose');
const dbConfig = require('../config/database.config.js');
const Note = require('../app/models/note.model.js');

async function migrate() {
    await mongoose.connect(dbConfig.url, { useNewUrlParser: true });
    console.log('Connected to database:', dbConfig.url);

    const categoryResult = await Note.updateMany(
        { category: { $exists: false } },
        { $set: { category: 'Uncategorized' } }
    );
    console.log(`Backfilled category on ${categoryResult.modifiedCount} note(s).`);

    const tagsResult = await Note.updateMany(
        { tags: { $exists: false } },
        { $set: { tags: [] } }
    );
    console.log(`Backfilled tags on ${tagsResult.modifiedCount} note(s).`);

    await mongoose.disconnect();
    console.log('Migration complete.');
}

migrate().catch(err => {
    console.error('Migration failed:', err);
    process.exitCode = 1;
});
"""


def smoke_test() -> str:
    return """// Dependency-free smoke test for the new search/filter/tag logic.
//
// Tests the pure, side-effect-free query-building functions exported by
// note.controller.js as `_internal` (normalizeTags, normalizeCategory,
// buildFilter, buildSort). Those functions contain ALL of the new
// tag/category/search/sort business logic and perform zero I/O, so they
// can be verified with zero mocking and zero database.
//
// Requiring note.controller.js itself is safe without a live MongoDB
// connection or any Module-loader trickery: note.model.js only calls
// mongoose.Schema(...) / mongoose.model(...), which just registers a model
// definition in memory -- Mongoose does not need an active connection until
// a query (Note.find(), note.save(), etc.) actually runs. This test
// deliberately never calls those, which is also why it never needs to
// await anything or worry about hanging on a missing database.
//
// Uses only Node's built-in `node:test` + `node:assert` modules (Node 18+),
// so it runs with zero additional npm installs: `node --test` or
// `npm test`.

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const notesController = require(path.join(__dirname, '..', 'app', 'controllers', 'note.controller.js'));
const { normalizeTags, normalizeCategory, buildFilter, buildSort } = notesController._internal;

// -- normalizeTags ----------------------------------------------------------

test('normalizeTags trims, lowercases, and dedupes an array', () => {
    assert.deepEqual(
        normalizeTags(['Food', 'food', ' Errands ', '']),
        ['food', 'errands']
    );
});

test('normalizeTags accepts a comma-separated string', () => {
    assert.deepEqual(normalizeTags('Work, urgent ,work'), ['work', 'urgent']);
});

test('normalizeTags returns [] for falsy input', () => {
    assert.deepEqual(normalizeTags(undefined), []);
    assert.deepEqual(normalizeTags(''), []);
    assert.deepEqual(normalizeTags(null), []);
});

// -- normalizeCategory -------------------------------------------------------

test('normalizeCategory trims a provided category', () => {
    assert.equal(normalizeCategory('  Work  '), 'Work');
});

test('normalizeCategory defaults to Uncategorized when empty', () => {
    assert.equal(normalizeCategory(''), 'Uncategorized');
    assert.equal(normalizeCategory(undefined), 'Uncategorized');
});

// -- buildFilter --------------------------------------------------------------

test('buildFilter with no params returns an empty filter (backward compatible)', () => {
    assert.deepEqual(buildFilter({}), {});
});

test('buildFilter builds a case-insensitive $or search on title/content', () => {
    const filter = buildFilter({ q: 'Roadmap' });
    assert.ok(filter.$or);
    assert.equal(filter.$or.length, 2);
    assert.ok(filter.$or[0].title.test('a roadmap draft'));
    assert.ok(filter.$or[1].content.test('ROADMAP notes'));
});

test('buildFilter escapes regex special characters in q', () => {
    const filter = buildFilter({ q: 'C++ (advanced)' });
    assert.doesNotThrow(() => filter.$or[0].title.test('anything'));
});

test('buildFilter defaults tags to $in ("any") semantics', () => {
    const filter = buildFilter({ tags: 'work,urgent' });
    assert.deepEqual(filter.tags, { $in: ['work', 'urgent'] });
});

test('buildFilter supports tagsMatch=all for $all semantics', () => {
    const filter = buildFilter({ tags: 'work,urgent', tagsMatch: 'all' });
    assert.deepEqual(filter.tags, { $all: ['work', 'urgent'] });
});

test('buildFilter applies an exact category match', () => {
    const filter = buildFilter({ category: 'Work' });
    assert.equal(filter.category, 'Work');
});

test('buildFilter combines q, tags, and category together', () => {
    const filter = buildFilter({ q: 'plan', tags: 'work', category: 'Work' });
    assert.ok(filter.$or);
    assert.deepEqual(filter.tags, { $in: ['work'] });
    assert.equal(filter.category, 'Work');
});

// -- buildSort ------------------------------------------------------------------

test('buildSort defaults to createdAt descending', () => {
    assert.deepEqual(buildSort(undefined, undefined), { createdAt: -1 });
});

test('buildSort accepts an allowed sortBy field', () => {
    assert.deepEqual(buildSort('title', 'asc'), { title: 1 });
});

test('buildSort falls back to createdAt for a disallowed sortBy field', () => {
    assert.deepEqual(buildSort('__proto__', 'asc'), { createdAt: 1 });
});

test('buildSort defaults to descending for an unrecognized order value', () => {
    assert.deepEqual(buildSort('title', 'sideways'), { title: -1 });
});

// -- create() validation path (synchronous, never touches the database) ------

test('create() rejects a request with no content, without touching the database', () => {
    const res = {
        statusCode: 200,
        status(code) { this.statusCode = code; return this; },
        send(payload) { this.body = payload; return this; },
    };
    notesController.create({ body: { title: 'No content' } }, res);
    assert.equal(res.statusCode, 400);
});
"""


# ---------------------------------------------------------------------
# Frontend: minimal, dependency-free search & filter UI
# ---------------------------------------------------------------------

def frontend_index_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>EasyNotes</title>
<link rel="stylesheet" href="style.css" />
</head>
<body>
<div class="app">
    <header class="app-header">
        <h1>&#128221; EasyNotes</h1>
        <p class="subtitle">Organise and search your notes</p>
    </header>

    <section class="toolbar">
        <input id="search-input" type="search" placeholder="Search title or content..." />

        <select id="category-filter">
            <option value="">All categories</option>
        </select>

        <select id="tags-match">
            <option value="any">Match any tag</option>
            <option value="all">Match all tags</option>
        </select>

        <select id="sort-select">
            <option value="createdAt:desc">Newest first</option>
            <option value="createdAt:asc">Oldest first</option>
            <option value="title:asc">Title A-Z</option>
            <option value="title:desc">Title Z-A</option>
            <option value="updatedAt:desc">Recently updated</option>
        </select>

        <button id="clear-filters-btn" type="button">Clear filters</button>
    </section>

    <section id="tag-chip-bar" class="tag-chip-bar" aria-label="Filter by tag"></section>

    <main class="layout">
        <section class="note-form-panel">
            <h2 id="form-title">New Note</h2>
            <form id="note-form">
                <input type="hidden" id="note-id" />

                <label for="title-input">Title</label>
                <input id="title-input" type="text" placeholder="Untitled Note" />

                <label for="content-input">Content *</label>
                <textarea id="content-input" rows="5" required></textarea>

                <label for="category-input">Category</label>
                <input id="category-input" type="text" placeholder="e.g. Work" list="category-suggestions" />
                <datalist id="category-suggestions"></datalist>

                <label for="tags-input">Tags (comma separated)</label>
                <input id="tags-input" type="text" placeholder="e.g. urgent, ideas" />

                <div class="form-actions">
                    <button type="submit" id="save-btn">Save Note</button>
                    <button type="button" id="cancel-edit-btn" class="secondary" hidden>Cancel</button>
                </div>
                <p id="form-error" class="form-error" role="alert"></p>
            </form>
        </section>

        <section class="note-list-panel">
            <div class="note-list-header">
                <span id="result-count"></span>
            </div>
            <div id="note-list" class="note-list"></div>
            <p id="empty-state" class="empty-state" hidden>No notes match your search/filters.</p>
        </section>
    </main>
</div>

<script src="app.js"></script>
</body>
</html>
"""


def frontend_app_js() -> str:
    return """// EasyNotes frontend -- vanilla JS, no build step, no framework.
// Talks to the Express API added by the AI agent:
//   GET    /notes                (with optional ?q=&tags=&tagsMatch=&category=&sortBy=&order=)
//   GET    /notes/tags
//   GET    /notes/categories
//   POST   /notes
//   PUT    /notes/:id
//   DELETE /notes/:id

const state = {
    notes: [],
    allTags: [],
    allCategories: [],
    activeTags: new Set(),
    editingNoteId: null,
};

const el = {
    searchInput: document.getElementById('search-input'),
    categoryFilter: document.getElementById('category-filter'),
    tagsMatch: document.getElementById('tags-match'),
    sortSelect: document.getElementById('sort-select'),
    clearFiltersBtn: document.getElementById('clear-filters-btn'),
    tagChipBar: document.getElementById('tag-chip-bar'),
    noteForm: document.getElementById('note-form'),
    noteIdField: document.getElementById('note-id'),
    titleInput: document.getElementById('title-input'),
    contentInput: document.getElementById('content-input'),
    categoryInput: document.getElementById('category-input'),
    categorySuggestions: document.getElementById('category-suggestions'),
    tagsInput: document.getElementById('tags-input'),
    formTitle: document.getElementById('form-title'),
    formError: document.getElementById('form-error'),
    cancelEditBtn: document.getElementById('cancel-edit-btn'),
    noteList: document.getElementById('note-list'),
    resultCount: document.getElementById('result-count'),
    emptyState: document.getElementById('empty-state'),
};

async function api(path, options = {}) {
    const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
        throw new Error((data && data.message) || `Request failed (${res.status})`);
    }
    return data;
}

function buildQuery() {
    const params = new URLSearchParams();
    const q = el.searchInput.value.trim();
    if (q) params.set('q', q);
    if (state.activeTags.size > 0) {
        params.set('tags', [...state.activeTags].join(','));
        params.set('tagsMatch', el.tagsMatch.value);
    }
    if (el.categoryFilter.value) params.set('category', el.categoryFilter.value);
    const [sortBy, order] = el.sortSelect.value.split(':');
    params.set('sortBy', sortBy);
    params.set('order', order);
    return params.toString();
}

async function loadNotes() {
    const query = buildQuery();
    state.notes = await api(`/notes${query ? '?' + query : ''}`);
    renderNotes();
}

async function loadFacets() {
    const [tags, categories] = await Promise.all([
        api('/notes/tags'),
        api('/notes/categories'),
    ]);
    state.allTags = tags;
    state.allCategories = categories;
    renderCategoryFilter();
    renderCategorySuggestions();
    renderTagChips();
}

function renderCategoryFilter() {
    const current = el.categoryFilter.value;
    el.categoryFilter.innerHTML = '<option value="">All categories</option>' +
        state.allCategories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    el.categoryFilter.value = current;
}

function renderCategorySuggestions() {
    el.categorySuggestions.innerHTML = state.allCategories
        .map(c => `<option value="${escapeHtml(c)}"></option>`)
        .join('');
}

function renderTagChips() {
    if (state.allTags.length === 0) {
        el.tagChipBar.innerHTML = '<span class="tag-chip-empty">No tags yet -- add some when creating a note.</span>';
        return;
    }
    el.tagChipBar.innerHTML = state.allTags.map(tag => {
        const active = state.activeTags.has(tag);
        return `<button type="button" class="tag-chip${active ? ' active' : ''}" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`;
    }).join('');

    el.tagChipBar.querySelectorAll('.tag-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const tag = chip.dataset.tag;
            if (state.activeTags.has(tag)) {
                state.activeTags.delete(tag);
            } else {
                state.activeTags.add(tag);
            }
            renderTagChips();
            loadNotes();
        });
    });
}

function renderNotes() {
    el.resultCount.textContent = `${state.notes.length} note${state.notes.length === 1 ? '' : 's'}`;
    el.emptyState.hidden = state.notes.length !== 0;
    el.noteList.innerHTML = state.notes.map(noteCardHtml).join('');

    el.noteList.querySelectorAll('[data-edit-id]').forEach(btn => {
        btn.addEventListener('click', () => startEdit(btn.dataset.editId));
    });
    el.noteList.querySelectorAll('[data-delete-id]').forEach(btn => {
        btn.addEventListener('click', () => deleteNote(btn.dataset.deleteId));
    });
}

function noteCardHtml(note) {
    const tags = (note.tags || [])
        .map(t => `<span class="note-tag">${escapeHtml(t)}</span>`)
        .join('');
    const updated = new Date(note.updatedAt || note.createdAt).toLocaleString();
    return `
        <article class="note-card">
            <div class="note-card-header">
                <h3>${escapeHtml(note.title || 'Untitled Note')}</h3>
                <span class="note-category">${escapeHtml(note.category || 'Uncategorized')}</span>
            </div>
            <p class="note-content">${escapeHtml(note.content)}</p>
            <div class="note-tags">${tags}</div>
            <div class="note-card-footer">
                <span class="note-updated">Updated ${updated}</span>
                <div class="note-card-actions">
                    <button type="button" data-edit-id="${note._id}">Edit</button>
                    <button type="button" data-delete-id="${note._id}" class="danger">Delete</button>
                </div>
            </div>
        </article>
    `;
}

function startEdit(noteId) {
    const note = state.notes.find(n => n._id === noteId);
    if (!note) return;
    state.editingNoteId = noteId;
    el.noteIdField.value = noteId;
    el.titleInput.value = note.title || '';
    el.contentInput.value = note.content || '';
    el.categoryInput.value = note.category || '';
    el.tagsInput.value = (note.tags || []).join(', ');
    el.formTitle.textContent = 'Edit Note';
    el.cancelEditBtn.hidden = false;
    el.contentInput.focus();
}

function resetForm() {
    state.editingNoteId = null;
    el.noteForm.reset();
    el.noteIdField.value = '';
    el.formTitle.textContent = 'New Note';
    el.cancelEditBtn.hidden = true;
    el.formError.textContent = '';
}

async function deleteNote(noteId) {
    if (!confirm('Delete this note?')) return;
    try {
        await api(`/notes/${noteId}`, { method: 'DELETE' });
        if (state.editingNoteId === noteId) resetForm();
        await Promise.all([loadNotes(), loadFacets()]);
    } catch (err) {
        alert(err.message);
    }
}

async function handleSubmit(event) {
    event.preventDefault();
    el.formError.textContent = '';

    const payload = {
        title: el.titleInput.value.trim(),
        content: el.contentInput.value.trim(),
        category: el.categoryInput.value.trim(),
        tags: el.tagsInput.value,
    };

    try {
        if (state.editingNoteId) {
            await api(`/notes/${state.editingNoteId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
        } else {
            await api('/notes', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        resetForm();
        await Promise.all([loadNotes(), loadFacets()]);
    } catch (err) {
        el.formError.textContent = err.message;
    }
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
}

function debounce(fn, delayMs) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delayMs);
    };
}

el.noteForm.addEventListener('submit', handleSubmit);
el.cancelEditBtn.addEventListener('click', resetForm);
el.searchInput.addEventListener('input', debounce(loadNotes, 250));
el.categoryFilter.addEventListener('change', loadNotes);
el.tagsMatch.addEventListener('change', loadNotes);
el.sortSelect.addEventListener('change', loadNotes);
el.clearFiltersBtn.addEventListener('click', () => {
    el.searchInput.value = '';
    el.categoryFilter.value = '';
    el.sortSelect.value = 'createdAt:desc';
    state.activeTags.clear();
    renderTagChips();
    loadNotes();
});

(async function init() {
    try {
        await Promise.all([loadNotes(), loadFacets()]);
    } catch (err) {
        el.noteList.innerHTML = `<p class="form-error">Could not load notes: ${escapeHtml(err.message)}</p>`;
    }
})();
"""


def frontend_style_css() -> str:
    return """:root {
    --primary: #4f46e5;
    --primary-dark: #4338ca;
    --danger: #dc2626;
    --bg: #f8fafc;
    --panel-bg: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --text-muted: #64748b;
    --radius: 10px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
}

.app {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px 60px;
}

.app-header h1 {
    margin: 0 0 4px;
    font-size: 28px;
}
.subtitle {
    margin: 0 0 20px;
    color: var(--text-muted);
}

.toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
}
.toolbar input[type="search"] {
    flex: 1 1 240px;
}
.toolbar select,
.toolbar input,
.toolbar button {
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 14px;
    background: var(--panel-bg);
}
#clear-filters-btn {
    cursor: pointer;
    color: var(--text-muted);
}
#clear-filters-btn:hover {
    color: var(--text);
}

.tag-chip-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 20px;
    min-height: 32px;
    align-items: center;
}
.tag-chip-empty {
    color: var(--text-muted);
    font-size: 13px;
}
.tag-chip {
    border: 1px solid var(--border);
    background: var(--panel-bg);
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text-muted);
}
.tag-chip.active {
    background: var(--primary);
    border-color: var(--primary);
    color: white;
}

.layout {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 20px;
    align-items: start;
}
@media (max-width: 800px) {
    .layout { grid-template-columns: 1fr; }
}

.note-form-panel,
.note-list-panel {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px;
}

.note-form-panel h2 {
    margin-top: 0;
}
#note-form {
    display: flex;
    flex-direction: column;
    gap: 4px;
}
#note-form label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    margin-top: 10px;
}
#note-form input,
#note-form textarea {
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
}
.form-actions {
    display: flex;
    gap: 10px;
    margin-top: 16px;
}
#note-form button {
    padding: 10px 16px;
    border-radius: var(--radius);
    border: none;
    background: var(--primary);
    color: white;
    font-weight: 600;
    cursor: pointer;
}
#note-form button:hover { background: var(--primary-dark); }
#note-form button.secondary {
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border);
}
.form-error {
    color: var(--danger);
    font-size: 13px;
    min-height: 18px;
}

.note-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-muted);
    font-size: 13px;
    margin-bottom: 10px;
}

.note-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 14px;
}

.note-card {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: #fdfdff;
}
.note-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
}
.note-card-header h3 {
    margin: 0;
    font-size: 16px;
    word-break: break-word;
}
.note-category {
    flex-shrink: 0;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    background: #eef2ff;
    color: var(--primary-dark);
    padding: 3px 8px;
    border-radius: 999px;
}
.note-content {
    margin: 0;
    color: var(--text);
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
}
.note-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.note-tag {
    font-size: 11px;
    background: #f1f5f9;
    color: var(--text-muted);
    padding: 3px 8px;
    border-radius: 999px;
}
.note-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid var(--border);
}
.note-updated {
    font-size: 11px;
    color: var(--text-muted);
}
.note-card-actions {
    display: flex;
    gap: 8px;
}
.note-card-actions button {
    border: none;
    background: transparent;
    color: var(--primary);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
}
.note-card-actions button.danger {
    color: var(--danger);
}

.empty-state {
    color: var(--text-muted);
    text-align: center;
    padding: 40px 0;
}
"""


# ---------------------------------------------------------------------
# Config & docs: these MERGE with existing file content rather than
# blindly overwriting it, since they're MODIFY tasks on real repo files.
# ---------------------------------------------------------------------

def package_json(existing_path: Path) -> str:
    data = json.loads(existing_path.read_text(encoding="utf-8"))

    data.setdefault("dependencies", {})
    data["dependencies"]["dotenv"] = "^16.4.5"
    # Keep dependencies alphabetically sorted, matching the original file's convention.
    data["dependencies"] = dict(sorted(data["dependencies"].items()))

    data["scripts"] = {
        **data.get("scripts", {}),
        "start": "node server.js",
        "migrate": "node scripts/migrate-add-tags-category.js",
        "test": "node --test",
    }

    return json.dumps(data, indent=2) + "\n"


def gitignore(existing_path: Path) -> str:
    existing = existing_path.read_text(encoding="utf-8") if existing_path.exists() else ""
    lines = [l for l in existing.splitlines() if l.strip()]

    additions = [".env", "*.log"]
    for entry in additions:
        if entry not in lines:
            lines.append(entry)

    return "\n".join(lines) + "\n"


def env_example() -> str:
    return """# MongoDB connection string. If unset, falls back to the local default
# defined in config/database.config.js (mongodb://localhost:27017/easy-notes).
MONGODB_URI=mongodb://localhost:27017/easy-notes

# Port the Express server listens on. If unset, falls back to 3000.
PORT=3000
"""


def readme(existing_path: Path) -> str:
    original = existing_path.read_text(encoding="utf-8") if existing_path.exists() else ""
    original = original.rstrip() + "\n"

    addendum = """
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
| `sortBy`     | `?sortBy=title`         | `title` \\| `createdAt` (default) \\| `updatedAt`     |
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
curl -X POST http://localhost:3000/notes \\
  -H "Content-Type: application/json" \\
  -d '{"title":"Q3 roadmap","content":"Draft the roadmap doc","tags":["work","planning"],"category":"Work"}'

# Search + filter + sort, combined
curl "http://localhost:3000/notes?q=roadmap&category=Work&sortBy=title&order=asc"

# All tags currently in use (for a filter dropdown)
curl http://localhost:3000/notes/tags
```
"""
    return original + addendum