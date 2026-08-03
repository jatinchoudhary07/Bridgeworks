// Notes Service - Adapts MyDeskService for new Notes components
import { apiClient } from '../../../apiClient';

async function parseResponse(response) {
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) {
    let message = data?.detail || data?.message;
    if (!message && data && typeof data === 'object') {
      const [firstKey] = Object.keys(data);
      const firstValue = firstKey ? data[firstKey] : null;
      if (Array.isArray(firstValue) && firstValue.length > 0) {
        message = `${firstKey}: ${firstValue[0]}`;
      } else if (typeof firstValue === 'string') {
        message = `${firstKey}: ${firstValue}`;
      }
    }
    if (!message) message = `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

/**
 * Normalize backend note data to match component expectations
 */
function normalizeNote(backendNote) {
  const attachments = (backendNote.file_attachments || []).map((att) => ({
    id: att.id,
    filename: att.original_name || 'file',
    mime_type: att.mime_type || '',
    size: att.file_size || 0,
    url: att.file_url || null,
    created_at: att.created_at,
  }));

  const versions = (backendNote.versions || []).map((v, i, arr) => ({
    id: v.id,
    label: v.version_label || v.saved_at || 'Version',
    author: v.author || null,
    saved_at: v.saved_at,
    title: v.title,
    content_html: v.content_html,
    current: i === 0, // most recent = first (backend orders -saved_at)
  }));

  const labels = backendNote.labels || [];
  const sharedMembers = labels.filter((l) => typeof l === 'string' && l.startsWith('shared:member:'));
  const userLabels = labels.filter((l) => typeof l === 'string' && !l.startsWith('shared:member:'));

  let labelVal = '';
  if (sharedMembers.length > 0 || (backendNote.shared_with && backendNote.shared_with.length > 0)) {
    if (backendNote.is_owner === false) {
      labelVal = 'shared with';
    } else {
      labelVal = `shared by ${backendNote.created_by_name || 'other'}`;
    }
  } else {
    labelVal = userLabels[0] || '';
  }

  return {
    id: backendNote.id,
    title: backendNote.title || '',
    content: backendNote.content_html || '',
    tags: backendNote.tags || [],
    label: labelVal,
    labels: backendNote.labels || [],
    is_pinned: backendNote.is_pinned || false,
    created_at: backendNote.created_at,
    updated_at: backendNote.updated_at,
    attachments,
    versions,
    drive_links: backendNote.drive_links || [],
    created_by_name: backendNote.created_by_name || null,
    is_owner: backendNote.is_owner !== false,
    shared_with: backendNote.shared_with || [],
    ai_summary: backendNote.ai_summary || '',
  };
}

/**
 * Denormalize component data to backend format
 */
function denormalizeNote(note) {
  return {
    title: note.title,
    content_html: note.content,
    tags: note.tags || [],
    labels: note.label
      ? [note.label, ...(note.labels || []).filter((l) => l !== note.label)]
      : [],
    is_pinned: note.is_pinned || false,
    create_version: note.create_version || false,
  };
}

export const notesService = {
  // ── CRUD ──────────────────────────────────────────────────────────────────

  async getNotes() {
    const response = await apiClient('/api/mydesk/notes/', { credentials: 'include' });
    const data = await parseResponse(response);
    return Array.isArray(data) ? data.map(normalizeNote) : [];
  },

  async getNote(noteId) {
    const response = await apiClient(`/api/mydesk/notes/${noteId}/`, { credentials: 'include' });
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  async createNote(noteData) {
    const payload = denormalizeNote(noteData);
    const response = await apiClient('/api/mydesk/notes/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  async updateNote(noteId, noteData) {
    const payload = denormalizeNote(noteData);
    const response = await apiClient(`/api/mydesk/notes/${noteId}/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  async deleteNote(noteId) {
    const response = await apiClient(`/api/mydesk/notes/${noteId}/`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok && response.status !== 204) await parseResponse(response);
    return true;
  },

  // ── ATTACHMENTS ───────────────────────────────────────────────────────────

  /**
   * Upload a file attachment to an existing note.
   * Returns the updated normalized note (with new file_attachments list).
   */
  async uploadAttachment(noteId, file) {
    const formData = new FormData();
    formData.append('files', file);
    const response = await apiClient(`/api/mydesk/notes/${noteId}/`, {
      method: 'PATCH',
      credentials: 'include',
      body: formData,
    });
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  /**
   * Delete a single file attachment by its attachment ID.
   */
  async deleteAttachment(attachmentId) {
    const response = await apiClient(`/api/mydesk/notes/attachments/${attachmentId}/`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok && response.status !== 204) await parseResponse(response);
    return true;
  },

  // ── VERSIONS ──────────────────────────────────────────────────────────────

  /**
   * Restore a note to a specific version.
   * Returns the updated normalized note.
   */
  async restoreVersion(noteId, versionId) {
    const response = await apiClient(
      `/api/mydesk/notes/${noteId}/versions/${versionId}/restore/`,
      { method: 'POST', credentials: 'include' }
    );
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  /**
   * Delete a specific note version.
   * Returns the updated normalized note.
   */
  async deleteVersion(noteId, versionId) {
    const response = await apiClient(
      `/api/mydesk/notes/${noteId}/versions/${versionId}/`,
      { method: 'DELETE', credentials: 'include' }
    );
    const data = await parseResponse(response);
    return normalizeNote(data);
  },

  // ── SHARING ───────────────────────────────────────────────────────────────

  /**
   * List org members that can be shared with (for autocomplete).
   * @param {string} query - search string
   */
  async listShareRecipients(query = '') {
    const q = query ? `?q=${encodeURIComponent(query)}` : '';
    const response = await apiClient(`/api/mydesk/notes/share-recipients/${q}`, {
      credentials: 'include',
    });
    return parseResponse(response);
  },

  /**
   * Share a note with one or more org members.
   * @param {number} noteId
   * @param {number[]} recipientIds
   * @param {string} message - optional custom message
   */
  async shareNote(noteId, recipientIds, message = '') {
    const response = await apiClient(`/api/mydesk/notes/${noteId}/share/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipient_ids: recipientIds, message }),
    });
    return parseResponse(response);
  },

  // ── AI ────────────────────────────────────────────────────────────────────

  async generateAISummary(noteId) {
    const response = await apiClient(`/api/mydesk/notes/${noteId}/ai-summary/`, {
      method: 'POST',
      credentials: 'include',
    });
    return parseResponse(response);
  },

  async aiCopilot(noteId, noteTitle, noteContent, action, prompt = '') {
    const response = await apiClient('/api/mydesk/notes/ai-copilot/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        note_id: noteId,
        title: noteTitle,
        content: noteContent,
        action,
        prompt,
      }),
    });
    const data = await parseResponse(response);
    return data.result;
  },
};
