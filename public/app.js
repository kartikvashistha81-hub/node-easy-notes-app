// EasyNotes frontend -- vanilla JS, no build step, no framework.
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
