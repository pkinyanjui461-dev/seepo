(function () {
  function showOfflineActionMessage(formElement) {
    const message =
      formElement.getAttribute('data-online-required-message') ||
      'You are offline. This action requires internet access.';

    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    alert(message);
  }

  function onUnsupportedOfflineSubmit(event) {
    const form = event.currentTarget;
    const method = (form.getAttribute('method') || 'GET').toUpperCase();

    if (form.getAttribute('data-offline-draft-form') === 'true') {
      return;
    }

    if (navigator.onLine || method !== 'POST') {
      return;
    }

    event.preventDefault();
    showOfflineActionMessage(form);
  }

  function collectFormData(formElement) {
    const formData = new FormData(formElement);
    const payload = {};

    for (const [key, value] of formData.entries()) {
      if (key === 'csrfmiddlewaretoken') {
        continue;
      }
      payload[key] = value;
    }

    formElement.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      if (!checkbox.name || checkbox.name === 'csrfmiddlewaretoken') {
        return;
      }
      if (!(checkbox.name in payload)) {
        payload[checkbox.name] = false;
      }
    });

    return payload;
  }

  async function onOfflineFormSubmit(event) {
    const form = event.currentTarget;
    const modelName = form.getAttribute('data-offline-model');

    if (!modelName || !window.seepoOfflineSync) {
      return;
    }

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    event.preventDefault();

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }

    try {
      const payload = collectFormData(form);
      const groupClientUuid = form.getAttribute('data-group-client-uuid');
      if (groupClientUuid) {
        payload.group_client_uuid = groupClientUuid;
      }

      await window.seepoOfflineSync.saveOffline(modelName, payload);
      window.seepoOfflineSync.showToast(
        navigator.onLine
          ? 'Saved locally and queued for sync.'
          : 'Saved offline. It will sync automatically when online.'
      );

      if (navigator.onLine) {
        await window.seepoOfflineSync.syncNow();
      }

      form.reset();

      const redirectUrl = form.getAttribute('data-offline-redirect-url');
      if (redirectUrl) {
        window.location.href = redirectUrl;
      }
    } catch (error) {
      console.error('Offline save failed:', error);
      if (window.seepoOfflineSync) {
        window.seepoOfflineSync.showToast('Could not save locally. Please retry.');
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!window.seepoOfflineSync) {
      return;
    }

    const forms = document.querySelectorAll('form[data-offline-form="true"]');
    forms.forEach((form) => {
      form.addEventListener('submit', onOfflineFormSubmit);
    });

    const unsupportedForms = document.querySelectorAll(
      'form:not([data-offline-form="true"]):not([data-offline-draft-form="true"])'
    );
    unsupportedForms.forEach((form) => {
      form.addEventListener('submit', onUnsupportedOfflineSubmit);
    });
  });
})();
