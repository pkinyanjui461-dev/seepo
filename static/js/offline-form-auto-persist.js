(function () {
  /**
   * Auto-persist form fields to localStorage as users type (draft recovery)
   * Survives page refresh/browser close and recovers on return
   */
  const DRAFT_PREFIX = 'seepoDraftField_';
  const DRAFT_EXPIRY_KEY = 'seepoDraftExpiry_';
  const DRAFT_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

  function getDraftKey(form, fieldName) {
    const formAction = form.getAttribute('action') || window.location.pathname;
    return DRAFT_PREFIX + formAction + '|' + fieldName;
  }

  function saveDraft(form, fieldName, value) {
    const key = getDraftKey(form, fieldName);
    const expiryKey = DRAFT_EXPIRY_KEY + key;
    localStorage.setItem(key, value);
    localStorage.setItem(expiryKey, String(Date.now() + DRAFT_EXPIRY_MS));
  }

  function loadDraft(form, fieldName) {
    const key = getDraftKey(form, fieldName);
    const expiryKey = DRAFT_EXPIRY_KEY + key;
    const expiryTime = parseInt(localStorage.getItem(expiryKey) || '0', 10);

    if (expiryTime < Date.now()) {
      localStorage.removeItem(key);
      localStorage.removeItem(expiryKey);
      return null;
    }

    return localStorage.getItem(key);
  }

  function clearDraft(form, fieldName) {
    const key = getDraftKey(form, fieldName);
    const expiryKey = DRAFT_EXPIRY_KEY + key;
    localStorage.removeItem(key);
    localStorage.removeItem(expiryKey);
  }

  function clearAllDrafts(form) {
    const formAction = form.getAttribute('action') || window.location.pathname;
    const prefix = DRAFT_PREFIX + formAction + '|';

    const keysToDelete = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix)) {
        keysToDelete.push(key);
        const expiryKey = DRAFT_EXPIRY_KEY + key;
        keysToDelete.push(expiryKey);
      }
    }

    keysToDelete.forEach((key) => localStorage.removeItem(key));
  }

  function attachAutoPersist() {
    const forms = document.querySelectorAll('form[data-offline-model], form[data-offline-draft-label]');

    forms.forEach((form) => {
      const inputs = form.querySelectorAll('input, textarea, select');

      inputs.forEach((input) => {
        const fieldName = input.name || input.id;
        if (!fieldName) return;

        // Restore draft on load
        const draft = loadDraft(form, fieldName);
        if (draft && !input.value) {
          input.value = draft;
        }

        // Auto-save on change
        input.addEventListener('input', () => {
          saveDraft(form, fieldName, input.value);
        });

        input.addEventListener('change', () => {
          saveDraft(form, fieldName, input.value);
        });
      });

      // Clear drafts on successful submit
      form.addEventListener('submit', () => {
        setTimeout(() => {
          clearAllDrafts(form);
        }, 100);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', attachAutoPersist);

  window.seepoOfflineFormPersist = {
    saveDraft: saveDraft,
    loadDraft: loadDraft,
    clearDraft: clearDraft,
    clearAllDrafts: clearAllDrafts,
  };
})();
