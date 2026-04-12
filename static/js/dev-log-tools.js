(function () {
  const MAX_LOG_ITEMS = 500;
  const LOG_LEVELS = ['log', 'info', 'warn', 'error', 'debug'];
  const logBuffer = [];
  const originalConsole = {};

  function stringifyValue(value) {
    if (typeof value === 'string') {
      return value;
    }

    if (value instanceof Error) {
      return value.stack || value.message;
    }

    try {
      return JSON.stringify(value);
    } catch (_error) {
      return String(value);
    }
  }

  function pushLog(level, args) {
    const message = args.map(stringifyValue).join(' ');
    logBuffer.push({
      time: new Date().toISOString(),
      level: level,
      message: message,
    });

    if (logBuffer.length > MAX_LOG_ITEMS) {
      logBuffer.shift();
    }
  }

  function patchConsole() {
    LOG_LEVELS.forEach(function (level) {
      const current = console[level];
      originalConsole[level] = typeof current === 'function' ? current.bind(console) : function () {};

      console[level] = function () {
        const args = Array.prototype.slice.call(arguments);
        pushLog(level, args);
        originalConsole[level].apply(console, args);
      };
    });
  }

  function showToast(message) {
    const toast = document.getElementById('sync-toast');
    if (!toast) {
      return;
    }

    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(function () {
      toast.classList.remove('show');
    }, 2600);
  }

  async function getServiceWorkerDiagnostics() {
    const supportsSw = 'serviceWorker' in navigator;

    if (!supportsSw) {
      return {
        supported: false,
        version: '',
        scope: '',
        activeState: '',
        controllerScript: '',
        cacheKeys: [],
        shellCount: 0,
        runtimeCount: 0,
      };
    }

    const registration = await navigator.serviceWorker.getRegistration('/').catch(function () {
      return null;
    });
    const cacheKeys = await caches.keys().catch(function () {
      return [];
    });
    const shellCacheKey = cacheKeys.find(function (key) {
      return key.indexOf('seepo-offline-shell-') === 0;
    }) || '';
    const runtimeCacheKey = cacheKeys.find(function (key) {
      return key.indexOf('seepo-offline-runtime-') === 0;
    }) || '';
    const version = shellCacheKey
      ? shellCacheKey.replace('seepo-offline-shell-', '')
      : (runtimeCacheKey ? runtimeCacheKey.replace('seepo-offline-runtime-', '') : '');

    let shellCount = 0;
    let runtimeCount = 0;

    if (shellCacheKey) {
      shellCount = await caches
        .open(shellCacheKey)
        .then(function (cache) {
          return cache.keys();
        })
        .then(function (items) {
          return items.length;
        })
        .catch(function () {
          return 0;
        });
    }

    if (runtimeCacheKey) {
      runtimeCount = await caches
        .open(runtimeCacheKey)
        .then(function (cache) {
          return cache.keys();
        })
        .then(function (items) {
          return items.length;
        })
        .catch(function () {
          return 0;
        });
    }

    return {
      supported: true,
      version: version,
      scope: registration && registration.scope ? registration.scope : '',
      activeState: registration && registration.active ? registration.active.state : '',
      controllerScript: navigator.serviceWorker.controller ? navigator.serviceWorker.controller.scriptURL : '',
      cacheKeys: cacheKeys,
      shellCount: shellCount,
      runtimeCount: runtimeCount,
    };
  }

  async function buildReport() {
    const sw = await getServiceWorkerDiagnostics();
    const hostBadge = document.getElementById('offline-host-ready-badge');
    const lines = [];

    lines.push('SEEPO Dev Log Export');
    lines.push('timestamp=' + new Date().toISOString());
    lines.push('url=' + window.location.href);
    lines.push('host=' + window.location.host);
    lines.push('online=' + String(navigator.onLine));
    lines.push('userAgent=' + navigator.userAgent);
    lines.push('hostBadge=' + (hostBadge ? hostBadge.textContent : 'n/a'));
    lines.push('hostBadgeClass=' + (hostBadge ? hostBadge.className : 'n/a'));
    lines.push('swSupported=' + String(sw.supported));
    lines.push('swVersion=' + (sw.version || 'unknown'));
    lines.push('swScope=' + (sw.scope || 'none'));
    lines.push('swActiveState=' + (sw.activeState || 'none'));
    lines.push('swController=' + (sw.controllerScript || 'none'));
    lines.push('shellCacheCount=' + String(sw.shellCount));
    lines.push('runtimeCacheCount=' + String(sw.runtimeCount));
    lines.push('cacheKeys=' + (sw.cacheKeys.length ? sw.cacheKeys.join(', ') : 'none'));
    lines.push('');
    lines.push('Recent Logs:');

    if (!logBuffer.length) {
      lines.push('(no logs captured yet)');
    } else {
      logBuffer.forEach(function (entry) {
        lines.push(entry.time + ' [' + entry.level.toUpperCase() + '] ' + entry.message);
      });
    }

    return lines.join('\n');
  }

  async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'readonly');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();

    let copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (_error) {
      copied = false;
    }

    document.body.removeChild(textarea);
    return copied;
  }

  async function handleCopyLogs(button) {
    const defaultLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Copying...';

    try {
      const report = await buildReport();
      const copied = await copyToClipboard(report);

      if (copied) {
        showToast('Developer logs copied to clipboard.');
      } else {
        showToast('Copy failed. Inspect window.seepoDevLogs.buildReport().');
      }
    } catch (error) {
      pushLog('error', ['copy logs failed', error]);
      showToast('Copy logs failed: ' + (error && error.message ? error.message : String(error)));
    } finally {
      button.disabled = false;
      button.textContent = defaultLabel;
    }
  }

  function bindCopyButton() {
    const button = document.getElementById('copy-dev-logs-btn');
    if (!button) {
      return;
    }

    button.addEventListener('click', function () {
      handleCopyLogs(button);
    });
  }

  patchConsole();

  window.addEventListener('error', function (event) {
    pushLog('error', [
      'window.error',
      event.message,
      event.filename + ':' + event.lineno + ':' + event.colno,
    ]);
  });

  window.addEventListener('unhandledrejection', function (event) {
    pushLog('error', ['unhandledrejection', event.reason]);
  });

  window.addEventListener('online', function () {
    pushLog('info', ['event', 'online']);
  });

  window.addEventListener('offline', function () {
    pushLog('warn', ['event', 'offline']);
  });

  window.seepoDevLogs = {
    getLogs: function () {
      return logBuffer.slice();
    },
    buildReport: buildReport,
    clear: function () {
      logBuffer.length = 0;
    },
  };

  document.addEventListener('DOMContentLoaded', bindCopyButton);
})();