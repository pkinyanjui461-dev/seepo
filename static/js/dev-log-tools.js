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

  function pickFields(record, fields) {
    if (!record) {
      return null;
    }

    const snapshot = {};
    fields.forEach(function (field) {
      if (record[field] !== undefined && record[field] !== null && record[field] !== '') {
        snapshot[field] = record[field];
      }
    });
    return snapshot;
  }

  function sortByUpdatedAtDesc(records) {
    return records.slice().sort(function (a, b) {
      const aTime = new Date(a.client_updated_at || 0).getTime();
      const bTime = new Date(b.client_updated_at || 0).getTime();
      return bTime - aTime;
    });
  }

  function sortMembersForSample(records) {
    return records.slice().sort(function (a, b) {
      const aNum = Number(a.member_number || 0);
      const bNum = Number(b.member_number || 0);
      const hasANum = Number.isFinite(aNum) && aNum > 0;
      const hasBNum = Number.isFinite(bNum) && bNum > 0;

      if (hasANum && hasBNum && aNum !== bNum) {
        return aNum - bNum;
      }
      if (hasANum && !hasBNum) {
        return -1;
      }
      if (!hasANum && hasBNum) {
        return 1;
      }

      return String(a.name || '').localeCompare(String(b.name || ''));
    });
  }

  async function getOfflineSheetSnapshot() {
    if (!window.seepoOfflineDb || typeof window.seepoOfflineDb.tableForModel !== 'function') {
      return null;
    }

    const context = window.seepoOfflineMonthlyFormContext || {};
    const groupClientUuid = String(context.groupClientUuid || '').trim();
    const formClientUuid = String(context.formClientUuid || '').trim();

    if (!groupClientUuid && !formClientUuid) {
      return null;
    }

    const groupsTable = window.seepoOfflineDb.tableForModel('group');
    const membersTable = window.seepoOfflineDb.tableForModel('member');
    const formsTable = window.seepoOfflineDb.tableForModel('monthly_form');

    const [groupCount, memberCount, formCount, groupByUuid, formByUuid] = await Promise.all([
      groupsTable.count(),
      membersTable.count(),
      formsTable.count(),
      groupClientUuid ? groupsTable.where('client_uuid').equals(groupClientUuid).first() : Promise.resolve(null),
      formClientUuid ? formsTable.where('client_uuid').equals(formClientUuid).first() : Promise.resolve(null),
    ]);

    const resolvedGroupServerId = Number(
      (groupByUuid && groupByUuid.server_id) ||
      (formByUuid && formByUuid.group_id) ||
      0
    );

    const memberMatchesByGroupUuid = groupClientUuid
      ? await membersTable.where('group_client_uuid').equals(groupClientUuid).toArray()
      : [];
    const memberMatchesByGroupId = resolvedGroupServerId > 0
      ? await membersTable.where('group_id').equals(resolvedGroupServerId).toArray()
      : [];

    const syncedMembersByGroupUuid = memberMatchesByGroupUuid.filter(function (record) {
      return Number(record.synced || 0) === 1;
    });
    const syncedMembersByGroupId = memberMatchesByGroupId.filter(function (record) {
      return Number(record.synced || 0) === 1;
    });

    const mismatchHints = [];
    if (groupClientUuid && !memberMatchesByGroupUuid.length && syncedMembersByGroupId.length) {
      mismatchHints.push(
        'No member rows match current group_client_uuid=' + groupClientUuid + ' but ' +
        syncedMembersByGroupId.length + ' synced member row(s) exist for resolved group_id=' + resolvedGroupServerId + '.'
      );
    }
    if (groupByUuid && formByUuid && String(formByUuid.group_client_uuid || '').trim() && String(formByUuid.group_client_uuid || '').trim() !== groupClientUuid) {
      mismatchHints.push(
        'Monthly form points to group_client_uuid=' + String(formByUuid.group_client_uuid || '').trim() +
        ' while the page context uses group_client_uuid=' + groupClientUuid + '.'
      );
    }

    const sampleMemberFields = [
      'client_uuid',
      'group_client_uuid',
      'group_id',
      'member_number',
      'name',
      'synced',
      'client_updated_at',
    ];

    const sampleGroupFields = [
      'client_uuid',
      'server_id',
      'name',
      'synced',
      'client_updated_at',
    ];

    const sampleFormFields = [
      'client_uuid',
      'group_client_uuid',
      'group_id',
      'month',
      'year',
      'status',
      'synced',
      'client_updated_at',
    ];

    const sampleMembers = sortMembersForSample(syncedMembersByGroupUuid.length ? syncedMembersByGroupUuid : syncedMembersByGroupId)
      .slice(0, 5)
      .map(function (record) {
        return pickFields(record, sampleMemberFields);
      });

    return {
      context: {
        url: window.location.href,
        source: context.source || '',
        groupClientUuid: groupClientUuid,
        formClientUuid: formClientUuid,
        groupName: context.groupName || '',
        month: context.month || '',
        year: context.year || '',
        status: context.status || '',
      },
      counts: {
        groups: groupCount,
        members: memberCount,
        monthly_forms: formCount,
      },
      resolved: {
        groupByClientUuid: pickFields(groupByUuid, sampleGroupFields),
        formByClientUuid: pickFields(formByUuid, sampleFormFields),
        resolvedGroupServerId: resolvedGroupServerId,
        memberMatchSource: syncedMembersByGroupUuid.length ? 'group_client_uuid' : (syncedMembersByGroupId.length ? 'group_id' : 'none'),
        memberMatchesByGroupUuid: memberMatchesByGroupUuid.length,
        memberMatchesByGroupId: memberMatchesByGroupId.length,
        syncedMemberMatchesByGroupUuid: syncedMembersByGroupUuid.length,
        syncedMemberMatchesByGroupId: syncedMembersByGroupId.length,
        sampleSyncedMembers: sampleMembers,
      },
      hints: mismatchHints,
    };
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
    const offlineSheetSnapshot = await getOfflineSheetSnapshot();
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
    if (offlineSheetSnapshot) {
      lines.push('offlineSheetSnapshot=' + JSON.stringify(offlineSheetSnapshot));
    }
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