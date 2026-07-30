// Dependency-free smoke test for the new search/filter/tag logic.
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
