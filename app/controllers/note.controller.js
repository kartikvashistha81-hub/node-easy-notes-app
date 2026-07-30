const Note = require('../models/note.model.js');

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
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
