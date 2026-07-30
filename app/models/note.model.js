const mongoose = require('mongoose');

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
