/**
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
