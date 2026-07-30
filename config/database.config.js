module.exports = {
    // Reads from the environment when available (e.g. a real MongoDB Atlas
    // cluster in production), falling back to the original local default so
    // behavior for anyone not setting MONGODB_URI is completely unchanged.
    url: process.env.MONGODB_URI || 'mongodb://localhost:27017/easy-notes'
}
