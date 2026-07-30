module.exports = (app) => {
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
