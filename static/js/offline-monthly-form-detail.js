(function () {
  if (!window.seepoOfflineDb) {
    return;
  }

  const context = window.seepoOfflineMonthlyFormContext || {};
  const STORAGE_KEY = 'seepoOfflineMonthlyFormSheetQueueV1';
  const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const editableFields = [
    'savings_share_bf',
    'loan_balance_bf',
    'total_repaid',
    'principal',
    'withdrawals',
    'fines_charges'
  ];

  const table = document.getElementById('offlineFinanceTable');
  const tableBody = document.getElementById('offline-finance-table-body');
  const emptyRow = document.getElementById('offline-finance-empty-row');
  const emptyMessage = document.getElementById('offline-finance-empty-message');
  const saveButton = document.getElementById('offlineManualSaveBtn');
  const syncNowButton = document.getElementById('offlineSyncNowBtn');
  const performanceButton = document.getElementById('offlinePerformanceBtn');
  const backLink = document.getElementById('offline-sheet-back-link');
  const statusBadge = document.getElementById('offline-sheet-status-badge');
  const contextLine = document.getElementById('offline-sheet-context-line');
  const mockBanner = document.getElementById('offline-sheet-mock-banner');
  const pageGroupTitle = document.getElementById('offline-sheet-page-group');
  const pagePeriodTitle = document.getElementById('offline-sheet-page-period');

  if (!table || !tableBody) {
    return;
  }

  const state = {
    groupClientUuid: normalizeText(context.groupClientUuid),
    formClientUuid: normalizeText(context.formClientUuid),
    group: null,
    form: null,
    members: [],
    hydrationAttempted: false,
    autoSaveTimer: null,
    isSaving: false,
  };

  function normalizeText(value) {
    return String(value || '').trim();
  }

  function htmlEscape(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function parseNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function integerString(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return '';
    }
    return String(Math.round(number));
  }

  function monthLabel(month) {
    const index = Number(month) - 1;
    if (index < 0 || index >= MONTH_NAMES.length) {
      return String(month || '?');
    }
    return MONTH_NAMES[index];
  }

  function updateOfflineCopyVisibility() {
    const offline = !navigator.onLine;

    if (mockBanner) {
      mockBanner.classList.toggle('d-none', !offline);
    }

    if (contextLine) {
      contextLine.classList.toggle('d-none', !offline);
      if (!offline) {
        contextLine.textContent = '';
      }
    }
  }

  function updateEmptyStateMessage() {
    if (!emptyRow) {
      return;
    }

    const isOffline = !navigator.onLine;
    let messageHtml = '';

    if (isOffline) {
      messageHtml = '<i class="fas fa-folder-open fs-3 mb-3 d-block opacity-50"></i>Connect once online so this group can cache its members on this device.';
    } else if (state.hydrationAttempted) {
      messageHtml = '<i class="fas fa-triangle-exclamation fs-3 mb-3 d-block text-warning opacity-75"></i>No cached members matched this group on this device yet. Copy logs to inspect the synced UUIDs.';
    } else {
      messageHtml = '<i class="fas fa-spinner fa-spin fs-3 mb-3 d-block text-primary opacity-75"></i>Members are syncing to this device. Stay online while the cache refreshes.';
    }

    if (emptyMessage) {
      emptyMessage.innerHTML = messageHtml;
    } else {
      const cell = emptyRow.querySelector('td');
      if (cell) {
        cell.innerHTML = messageHtml;
      }
    }

    emptyRow.classList.toggle('d-none', state.members.length > 0);
  }

  function showToast(message, isError) {
    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    const statusToast = document.getElementById('offlineSaveStatus');
    if (!statusToast) {
      if (isError) {
        console.error(message);
      } else {
        console.info(message);
      }
      return;
    }

    const toastBody = statusToast.querySelector('.toast-body span');
    const toastCard = statusToast.querySelector('.toast');
    if (toastBody) {
      toastBody.innerHTML = isError
        ? '<i class="fas fa-exclamation-triangle me-2"></i> ' + htmlEscape(message)
        : '<i class="fas fa-check-circle me-2"></i> ' + htmlEscape(message);
    }
    if (toastCard) {
      toastCard.classList.remove('bg-success', 'bg-danger');
      toastCard.classList.add(isError ? 'bg-danger' : 'bg-success');
    }

    statusToast.style.display = 'block';
    window.setTimeout(function () {
      statusToast.style.display = 'none';
    }, 2200);
  }

  function getCookie(name) {
    const prefix = name + '=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(prefix)) {
        return decodeURIComponent(cookie.slice(prefix.length));
      }
    }
    return '';
  }

  function notifyQueueChanged() {
    const pending = getQueue().length;
    window.dispatchEvent(
      new CustomEvent('seepo:monthly-sheet-queue-updated', {
        detail: { pending: pending }
      })
    );

    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.refreshStatus === 'function') {
      window.seepoOfflineSync.refreshStatus();
    }
  }

  function getQueue() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function setQueue(queue) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.isArray(queue) ? queue : []));
    notifyQueueChanged();
    updateRowPendingState();
  }

  function queueKey(item) {
    return normalizeText(item && (item.formClientUuid || item.id));
  }

  function getQueueEntry(formClientUuid) {
    const key = normalizeText(formClientUuid);
    if (!key) {
      return null;
    }

    const queue = getQueue();
    return queue.find(function (item) {
      return queueKey(item) === key;
    }) || null;
  }

  function upsertQueueEntry(entry) {
    const key = normalizeText(entry && entry.formClientUuid);
    if (!key) {
      return;
    }

    const queue = getQueue();
    const payload = {
      id: key,
      formClientUuid: key,
      groupClientUuid: normalizeText(entry.groupClientUuid),
      groupName: normalizeText(entry.groupName),
      month: entry.month,
      year: entry.year,
      status: normalizeText(entry.status) || 'draft',
      rows: Array.isArray(entry.rows) ? entry.rows : [],
      updatedAt: new Date().toISOString(),
    };

    const existingIndex = queue.findIndex(function (item) {
      return queueKey(item) === key;
    });

    if (existingIndex >= 0) {
      queue[existingIndex] = payload;
    } else {
      queue.push(payload);
    }

    setQueue(queue);
  }

  function removeQueueEntries(keys) {
    const keySet = new Set((Array.isArray(keys) ? keys : []).map(normalizeText).filter(Boolean));
    if (!keySet.size) {
      return 0;
    }

    const queue = getQueue();
    const remaining = queue.filter(function (item) {
      return !keySet.has(queueKey(item));
    });

    const deleted = queue.length - remaining.length;
    if (deleted > 0) {
      setQueue(remaining);
    }

    return deleted;
  }

  function getSelectionItems() {
    return getQueue().map(function (item) {
      const period = monthLabel(item.month) + ' ' + String(item.year || '?');
      return {
        key: queueKey(item),
        label: 'Monthly Sheet ' + period,
        updatedAt: item.updatedAt || '',
      };
    });
  }

  function buildBackUrl() {
    const source = normalizeText(context.source).toLowerCase();
    const groupName = normalizeText(state.group && state.group.name ? state.group.name : context.groupName);

    if (source === 'workspace' || (!navigator.onLine && state.groupClientUuid)) {
      const workspaceBase = context.urls && context.urls.offlineWorkspace ? context.urls.offlineWorkspace : '/groups/offline/workspace/';
      return (
        workspaceBase +
        '?group_client_uuid=' + encodeURIComponent(state.groupClientUuid || '') +
        '&group_name=' + encodeURIComponent(groupName)
      );
    }

    if (state.group && Number(state.group.server_id || 0) > 0) {
      return '/finance/group/' + String(state.group.server_id) + '/forms/';
    }

    return context.urls && context.urls.groupList ? context.urls.groupList : '/groups/';
  }

  function setStatusBadge(formRecord) {
    if (!statusBadge) {
      return;
    }

    const status = normalizeText(formRecord && formRecord.status ? formRecord.status : context.status).toLowerCase() || 'draft';
    const isPending = !formRecord || Number(formRecord.synced || 0) === 0;

    statusBadge.className = 'badge fs-6';

    if (isPending) {
      statusBadge.classList.add('bg-warning', 'text-dark');
      statusBadge.textContent = 'Offline Pending';
      return;
    }

    if (status === 'approved') {
      statusBadge.classList.add('bg-success');
      statusBadge.textContent = 'Approved';
      return;
    }

    if (status === 'submitted') {
      statusBadge.classList.add('bg-info', 'text-dark');
      statusBadge.textContent = 'Submitted';
      return;
    }

    statusBadge.classList.add('bg-warning', 'text-dark');
    statusBadge.textContent = 'Draft';
  }

  function updateHeaderAndActions() {
    const groupName = normalizeText(state.group && state.group.name ? state.group.name : context.groupName) || 'Offline Group';
    const month = state.form ? state.form.month : context.month;
    const year = state.form ? state.form.year : context.year;
    const period = monthLabel(month) + ' ' + String(year || '?');

    if (pageGroupTitle) {
      pageGroupTitle.textContent = groupName + ' / ';
    }
    if (pagePeriodTitle) {
      pagePeriodTitle.textContent = period;
    }

    if (backLink) {
      backLink.href = buildBackUrl();
    }

    setStatusBadge(state.form);

    updateOfflineCopyVisibility();

    if (contextLine && !navigator.onLine) {
      const sourceLabel = normalizeText(context.source) || 'direct';
      const syncState = state.form && Number(state.form.synced || 0) === 1 ? 'cached synced record' : 'local pending record';
      contextLine.innerHTML =
        '<strong>Mode:</strong> Offline accounting mock with live calculations. ' +
        '<strong>Source:</strong> ' + htmlEscape(sourceLabel) + '. ' +
        '<strong>Form State:</strong> ' + htmlEscape(syncState) + '.';
    }

    if (!performanceButton) {
      return;
    }

    const hasServerForm = state.form && Number(state.form.server_id || 0) > 0;
    if (hasServerForm) {
      performanceButton.href = '/finance/forms/' + String(state.form.server_id) + '/performance/';
      performanceButton.classList.remove('disabled');
      performanceButton.removeAttribute('aria-disabled');
      performanceButton.removeAttribute('data-online-required-message');
      return;
    }

    performanceButton.href = '#';
    performanceButton.classList.add('disabled');
    performanceButton.setAttribute('aria-disabled', 'true');
    performanceButton.setAttribute('data-online-required-message', 'Group performance opens after this monthly form syncs.');
  }

  async function resolveGroupRecord() {
    const groupsTable = window.seepoOfflineDb.tableForModel('group');

    if (state.groupClientUuid) {
      try {
        const exact = await groupsTable.where('client_uuid').equals(state.groupClientUuid).first();
        if (exact) {
          state.group = exact;
          return exact;
        }
      } catch (_error) {
        // Continue fallback resolution.
      }
    }

    const allGroups = await groupsTable.toArray();
    const hintName = normalizeText(context.groupName).toLowerCase();

    if (hintName) {
      const byName = allGroups.find(function (item) {
        return normalizeText(item.name).toLowerCase() === hintName;
      });
      if (byName) {
        state.group = byName;
        state.groupClientUuid = normalizeText(byName.client_uuid);
        return byName;
      }
    }

    return null;
  }

  async function resolveFormRecord() {
    const formsTable = window.seepoOfflineDb.tableForModel('monthly_form');

    if (state.formClientUuid) {
      try {
        const exact = await formsTable.where('client_uuid').equals(state.formClientUuid).first();
        if (exact) {
          state.form = exact;
          if (!state.groupClientUuid) {
            state.groupClientUuid = normalizeText(exact.group_client_uuid);
          }
          return exact;
        }
      } catch (_error) {
        // Continue fallback.
      }
    }

    const allForms = await formsTable.toArray();
    const month = Number(context.month || 0);
    const year = Number(context.year || 0);

    let match = null;
    if (state.groupClientUuid && month > 0 && year > 0) {
      match = allForms.find(function (item) {
        return (
          normalizeText(item.group_client_uuid) === state.groupClientUuid &&
          Number(item.month || 0) === month &&
          Number(item.year || 0) === year
        );
      }) || null;
    }

    if (!match && state.groupClientUuid) {
      const sameGroup = allForms
        .filter(function (item) {
          return normalizeText(item.group_client_uuid) === state.groupClientUuid;
        })
        .sort(function (a, b) {
          const aTime = new Date(a.client_updated_at || 0).getTime();
          const bTime = new Date(b.client_updated_at || 0).getTime();
          return bTime - aTime;
        });
      match = sameGroup[0] || null;
    }

    if (match) {
      state.form = match;
      state.formClientUuid = normalizeText(match.client_uuid);
      if (!state.groupClientUuid) {
        state.groupClientUuid = normalizeText(match.group_client_uuid);
      }
    }

    return match;
  }

  function uniqueMembers(members) {
    const seen = new Set();
    const result = [];

    members.forEach(function (member) {
      const key = normalizeText(member.client_uuid) || (String(member.member_number || '') + '|' + normalizeText(member.name));
      if (!key || seen.has(key)) {
        return;
      }
      seen.add(key);
      result.push(member);
    });

    return result;
  }

  async function resolveMembers() {
    const membersTable = window.seepoOfflineDb.tableForModel('member');
    const allMembers = await membersTable.toArray();

    const formGroupUuid = normalizeText(state.form && state.form.group_client_uuid);
    const targetGroupUuid = normalizeText(state.groupClientUuid || formGroupUuid);
    const targetServerGroupId = Math.max(
      Number((state.group && state.group.server_id) || 0),
      Number((state.form && state.form.group_id) || 0)
    );

    let filtered = [];

    if (targetGroupUuid) {
      filtered = allMembers.filter(function (item) {
        return normalizeText(item.group_client_uuid) === targetGroupUuid;
      });

      if (!state.groupClientUuid) {
        state.groupClientUuid = targetGroupUuid;
      }
    }

    if (!filtered.length && targetServerGroupId > 0) {
      filtered = allMembers.filter(function (item) {
        return Number(item.group_id || 0) === targetServerGroupId;
      });
    }

    filtered = filtered.filter(function (item) {
      return item.is_active !== false;
    });

    filtered = uniqueMembers(filtered).sort(function (a, b) {
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

      return normalizeText(a.name).localeCompare(normalizeText(b.name));
    });

    state.members = filtered;
    return filtered;
  }

  async function hydrateCacheForCurrentContext() {
    if (!navigator.onLine || !window.seepoOfflineSync || typeof window.seepoOfflineSync.pullModel !== 'function') {
      return false;
    }

    const models = ['group', 'member', 'monthly_form'];
    let pulledAny = false;

    for (const modelName of models) {
      try {
        await window.seepoOfflineSync.pullModel(modelName, { forceFull: true });
        pulledAny = true;
      } catch (error) {
        console.error('Context cache hydrate failed for model', modelName, error);
      }
    }

    return pulledAny;
  }

  function getDraftMapForCurrentForm() {
    const entry = getQueueEntry(state.formClientUuid);
    const map = {};

    if (!entry || !Array.isArray(entry.rows)) {
      return map;
    }

    entry.rows.forEach(function (row) {
      const byUuid = normalizeText(row.member_client_uuid);
      const byNumber = String(row.member_number || '').trim();
      if (byUuid) {
        map['uuid:' + byUuid] = row;
      }
      if (byNumber) {
        map['num:' + byNumber] = row;
      }
    });

    return map;
  }

  function getDraftForMember(draftMap, member) {
    const memberUuid = normalizeText(member.client_uuid);
    const memberNumber = String(member.member_number || '').trim();

    if (memberUuid && draftMap['uuid:' + memberUuid]) {
      return draftMap['uuid:' + memberUuid];
    }

    if (memberNumber && draftMap['num:' + memberNumber]) {
      return draftMap['num:' + memberNumber];
    }

    return null;
  }

  function renderRows() {
    tableBody.querySelectorAll('tr[data-offline-row="true"]').forEach(function (row) {
      row.remove();
    });

    if (!state.members.length) {
      updateEmptyStateMessage();
      updateRowPendingState();
      return;
    }

    if (emptyRow) {
      emptyRow.classList.add('d-none');
    }

    const draftMap = getDraftMapForCurrentForm();

    const rowsHtml = state.members.map(function (member) {
      const memberNumber = String(member.member_number || '').trim();
      const draft = getDraftForMember(draftMap, member) || {};

      const values = {
        savings_share_bf: integerString(draft.savings_share_bf),
        loan_balance_bf: integerString(draft.loan_balance_bf),
        total_repaid: integerString(draft.total_repaid),
        principal: integerString(draft.principal),
        loan_interest: integerString(draft.loan_interest),
        shares_this_month: integerString(draft.shares_this_month),
        withdrawals: integerString(draft.withdrawals),
        fines_charges: integerString(draft.fines_charges),
        savings_share_cf: integerString(draft.savings_share_cf),
        loan_balance_cf: integerString(draft.loan_balance_cf),
      };

      return (
        '<tr data-offline-row="true" class="record-row" data-member-client-uuid="' + htmlEscape(member.client_uuid || '') + '" data-member-number="' + htmlEscape(memberNumber) + '">' +
          '<td class="text-center text-muted small align-middle" style="background-color: #f8f9fa;">' + htmlEscape(memberNumber || '-') + '</td>' +
          '<td class="fw-bold bg-light text-wrap" style="position: sticky; left: 0; border-right: 2px solid #ccc; z-index: 5; font-size: 0.85rem; line-height: 1.2;">' + htmlEscape(member.name || 'Member') + '</td>' +
          '<td><input type="number" step="1" class="form-control calc-input" data-field="savings_share_bf" value="' + htmlEscape(values.savings_share_bf) + '"></td>' +
          '<td class="tooltip-custom" data-role="loan-bf-cell"><input type="number" step="1" class="form-control calc-input" data-field="loan_balance_bf" value="' + htmlEscape(values.loan_balance_bf) + '"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input" data-field="total_repaid" value="' + htmlEscape(values.total_repaid) + '"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input" data-field="principal" value="' + htmlEscape(values.principal) + '"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input text-primary fw-bold" data-field="loan_interest" value="' + htmlEscape(values.loan_interest) + '" readonly tabindex="-1"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input fw-bold text-info" data-field="shares_this_month" value="' + htmlEscape(values.shares_this_month) + '" readonly tabindex="-1"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input text-danger" data-field="withdrawals" value="' + htmlEscape(values.withdrawals) + '"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input" data-field="fines_charges" value="' + htmlEscape(values.fines_charges) + '"></td>' +
          '<td class="tooltip-custom" data-role="savings-cf-cell"><input type="number" step="1" class="form-control calc-input fw-bold text-success" data-field="savings_share_cf" value="' + htmlEscape(values.savings_share_cf) + '" readonly tabindex="-1"></td>' +
          '<td><input type="number" step="1" class="form-control calc-input fw-bold text-warning" data-field="loan_balance_cf" value="' + htmlEscape(values.loan_balance_cf) + '" readonly tabindex="-1"></td>' +
        '</tr>'
      );
    }).join('');

    tableBody.insertAdjacentHTML('afterbegin', rowsHtml);
  }

  function getVal(tr, fieldName) {
    const input = tr.querySelector('[data-field="' + fieldName + '"]');
    return parseNumber(input ? input.value : 0);
  }

  function setVal(tr, fieldName, value) {
    const input = tr.querySelector('[data-field="' + fieldName + '"]');
    if (!input) {
      return;
    }

    const rounded = Math.round(parseNumber(value));
    input.value = rounded === 0 ? '' : String(rounded);

    const td = input.closest('td');
    if (td) {
      td.classList.toggle('cell-negative', rounded < 0);
    }
  }

  function validateRow(tr, savBf, shares, withdrawals, savCf, loanBf, principal, loanCf) {
    const loanCell = tr.querySelector('[data-role="loan-bf-cell"]');
    const savingsCell = tr.querySelector('[data-role="savings-cf-cell"]');

    const loanExpected = principal + loanCf;
    const savingsExpected = savBf + shares - withdrawals;

    if (loanCell) {
      const loanInvalid = loanBf !== loanExpected || loanBf < 0 || loanCf < 0;
      loanCell.classList.toggle('cell-error', loanInvalid);
    }

    if (savingsCell) {
      const savingsInvalid = savCf !== savingsExpected || savBf < 0 || savCf < 0;
      savingsCell.classList.toggle('cell-error', savingsInvalid);
    }
  }

  function performRowCalculations(tr) {
    const savBf = Math.round(getVal(tr, 'savings_share_bf'));
    const loanBf = Math.round(getVal(tr, 'loan_balance_bf'));
    const repaid = Math.round(getVal(tr, 'total_repaid'));
    const principal = Math.round(getVal(tr, 'principal'));
    const withdrawals = Math.round(getVal(tr, 'withdrawals'));

    const loanInterest = Math.round(loanBf * 0.015);

    let shares = 0;
    if (repaid <= 0) {
      shares = 0;
    } else if (principal === 0 || withdrawals > 0) {
      shares = repaid;
    } else {
      shares = Math.max(0, repaid - (principal + loanInterest));
    }

    const savCf = savBf + shares - withdrawals;
    const loanCf = loanBf - principal;

    setVal(tr, 'loan_interest', loanInterest);
    setVal(tr, 'shares_this_month', shares);
    setVal(tr, 'savings_share_cf', savCf);
    setVal(tr, 'loan_balance_cf', loanCf);

    validateRow(tr, savBf, shares, withdrawals, savCf, loanBf, principal, loanCf);
  }

  function calculateTotals() {
    const fields = [
      'savings_share_bf',
      'loan_balance_bf',
      'total_repaid',
      'principal',
      'loan_interest',
      'shares_this_month',
      'withdrawals',
      'fines_charges',
      'savings_share_cf',
      'loan_balance_cf'
    ];

    const totalMap = {};
    fields.forEach(function (field) {
      totalMap[field] = 0;
    });

    tableBody.querySelectorAll('tr.record-row').forEach(function (tr) {
      fields.forEach(function (field) {
        totalMap[field] += getVal(tr, field);
      });
    });

    const totalIds = {
      savings_share_bf: 'tot-savings-bf',
      loan_balance_bf: 'tot-loan-bf',
      total_repaid: 'tot-repaid',
      principal: 'tot-principal',
      loan_interest: 'tot-interest',
      shares_this_month: 'tot-shares',
      withdrawals: 'tot-withdrawals',
      fines_charges: 'tot-fines',
      savings_share_cf: 'tot-savings-cf',
      loan_balance_cf: 'tot-loan-cf'
    };

    fields.forEach(function (field) {
      const cell = document.getElementById(totalIds[field]);
      if (!cell) {
        return;
      }
      const rounded = Math.round(totalMap[field]);
      cell.textContent = rounded === 0 ? '' : String(rounded);
    });

    const loanCell = document.getElementById('tot-loan-bf');
    const savingsCell = document.getElementById('tot-savings-cf');

    const expectedLoan = totalMap.principal + totalMap.loan_balance_cf;
    const expectedSavings = totalMap.savings_share_bf + totalMap.shares_this_month - totalMap.withdrawals;

    if (loanCell) {
      loanCell.classList.toggle('cell-error', Math.round(totalMap.loan_balance_bf) !== Math.round(expectedLoan));
    }
    if (savingsCell) {
      savingsCell.classList.toggle('cell-error', Math.round(totalMap.savings_share_cf) !== Math.round(expectedSavings));
    }
  }

  function collectRowsPayload() {
    return Array.from(tableBody.querySelectorAll('tr.record-row')).map(function (tr) {
      const payload = {
        member_client_uuid: normalizeText(tr.getAttribute('data-member-client-uuid')),
        member_number: normalizeText(tr.getAttribute('data-member-number')),
      };

      editableFields.forEach(function (fieldName) {
        payload[fieldName] = Math.round(getVal(tr, fieldName));
      });

      payload.loan_interest = Math.round(getVal(tr, 'loan_interest'));
      payload.shares_this_month = Math.round(getVal(tr, 'shares_this_month'));
      payload.savings_share_cf = Math.round(getVal(tr, 'savings_share_cf'));
      payload.loan_balance_cf = Math.round(getVal(tr, 'loan_balance_cf'));
      payload.updated_at = new Date().toISOString();
      return payload;
    });
  }

  function updateRowPendingState() {
    const hasQueued = !!getQueueEntry(state.formClientUuid);
    tableBody.querySelectorAll('tr.record-row').forEach(function (row) {
      row.classList.toggle('row-pending-sync', hasQueued);
    });
  }

  function saveCurrentSheet(silent) {
    if (!state.formClientUuid) {
      if (!silent) {
        showToast('Missing monthly form identifier for offline save.', true);
      }
      return false;
    }

    const rows = collectRowsPayload();
    upsertQueueEntry({
      formClientUuid: state.formClientUuid,
      groupClientUuid: state.groupClientUuid,
      groupName: state.group ? state.group.name : context.groupName,
      month: state.form ? state.form.month : context.month,
      year: state.form ? state.form.year : context.year,
      status: state.form ? state.form.status : context.status,
      rows: rows,
    });

    if (!silent) {
      showToast('Offline sheet saved on this device.', false);
    }

    return true;
  }

  function scheduleAutoSave() {
    window.clearTimeout(state.autoSaveTimer);
    state.autoSaveTimer = window.setTimeout(function () {
      saveCurrentSheet(true);
    }, 600);
  }

  async function syncQueuedSheets() {
    if (!navigator.onLine) {
      return { synced: 0, remaining: getQueue().length };
    }

    const syncUrl = context.urls && context.urls.syncSheet ? context.urls.syncSheet : '/finance/forms/offline/sync-sheet/';
    const queue = getQueue();
    if (!queue.length) {
      return { synced: 0, remaining: 0 };
    }

    const remaining = [];
    let synced = 0;

    for (const item of queue) {
      const formClientUuid = normalizeText(item.formClientUuid);
      if (!formClientUuid || !Array.isArray(item.rows) || !item.rows.length) {
        continue;
      }

      try {
        const response = await fetch(syncUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: JSON.stringify({
            form_client_uuid: formClientUuid,
            rows: item.rows,
          })
        });

        let payload = null;
        try {
          payload = await response.json();
        } catch (_error) {
          payload = null;
        }

        if (!response.ok || !payload || payload.success !== true) {
          remaining.push(item);
          continue;
        }

        if (payload.pending) {
          remaining.push(item);
          continue;
        }

        synced += 1;
      } catch (_error) {
        remaining.push(item);
      }
    }

    setQueue(remaining);

    if (synced > 0) {
      showToast('Synced ' + synced + ' offline sheet draft' + (synced === 1 ? '' : 's') + '.', false);
    }

    return { synced: synced, remaining: remaining.length };
  }

  async function refreshFromStorage() {
    await resolveGroupRecord();
    await resolveFormRecord();
    await resolveMembers();

    if (!state.members.length && !state.hydrationAttempted && navigator.onLine) {
      state.hydrationAttempted = true;
      const hydrated = await hydrateCacheForCurrentContext();
      if (hydrated) {
        await resolveGroupRecord();
        await resolveFormRecord();
        await resolveMembers();
      }
    }

    if (!state.groupClientUuid && state.group && state.group.client_uuid) {
      state.groupClientUuid = normalizeText(state.group.client_uuid);
    }

    if (!state.formClientUuid && state.form && state.form.client_uuid) {
      state.formClientUuid = normalizeText(state.form.client_uuid);
    }

    updateHeaderAndActions();
    renderRows();

    tableBody.querySelectorAll('tr.record-row').forEach(function (row) {
      performRowCalculations(row);
    });
    calculateTotals();
    updateRowPendingState();

    bindRowInputs();
  }

  async function handleSyncComplete() {
    if (state.members.length > 0) {
      return;
    }

    state.hydrationAttempted = false;
    await refreshFromStorage();
  }

  function bindRowInputs() {
    tableBody.querySelectorAll('tr.record-row .calc-input').forEach(function (input) {
      if (input.readOnly) {
        return;
      }

      input.addEventListener('input', function (event) {
        const row = event.target.closest('tr.record-row');
        if (!row) {
          return;
        }

        performRowCalculations(row);
        calculateTotals();
        scheduleAutoSave();
      });
    });
  }

  async function handleManualSave() {
    if (state.isSaving) {
      return;
    }

    state.isSaving = true;
    const originalText = saveButton ? saveButton.innerHTML : '';

    if (saveButton) {
      saveButton.disabled = true;
      saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Saving...';
    }

    try {
      const saved = saveCurrentSheet(false);
      if (!saved) {
        return;
      }

      if (navigator.onLine) {
        if (window.seepoOfflineSync && typeof window.seepoOfflineSync.syncNow === 'function') {
          await window.seepoOfflineSync.syncNow();
        } else {
          await syncQueuedSheets();
        }
      }
    } finally {
      if (saveButton) {
        saveButton.disabled = false;
        saveButton.innerHTML = originalText;
      }
      state.isSaving = false;
    }
  }

  async function handleSyncNow() {
    if (!navigator.onLine) {
      showToast('You are offline. Connect to internet to sync.', true);
      return;
    }

    const saved = saveCurrentSheet(true);
    if (!saved) {
      return;
    }

    const originalText = syncNowButton ? syncNowButton.innerHTML : '';
    if (syncNowButton) {
      syncNowButton.disabled = true;
      syncNowButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Syncing...';
    }

    try {
      if (window.seepoOfflineSync && typeof window.seepoOfflineSync.syncNow === 'function') {
        await window.seepoOfflineSync.syncNow();
      } else {
        await syncQueuedSheets();
      }

      state.hydrationAttempted = false;
      await refreshFromStorage();
    } finally {
      if (syncNowButton) {
        syncNowButton.disabled = false;
        syncNowButton.innerHTML = originalText;
      }
    }
  }

  async function handleConnectivityChange() {
    state.hydrationAttempted = false;
    await refreshFromStorage();
  }

  function handlePerformanceButton(event) {
    if (!performanceButton) {
      return;
    }

    const hasServerForm = state.form && Number(state.form.server_id || 0) > 0;
    if (hasServerForm) {
      return;
    }

    event.preventDefault();
    showToast('Group performance opens after this monthly form syncs.', true);
  }

  window.seepoOfflineMonthlyFormSheet = {
    getQueue: getQueue,
    getSelectionItems: getSelectionItems,
    deleteSelectionItems: function (keys) {
      return removeQueueEntries(keys);
    },
    pendingCount: function () {
      return getQueue().length;
    },
    syncNow: syncQueuedSheets,
    clear: function () {
      setQueue([]);
    }
  };

  if (saveButton) {
    saveButton.addEventListener('click', function () {
      handleManualSave();
    });
  }

  if (syncNowButton) {
    syncNowButton.addEventListener('click', function () {
      handleSyncNow();
    });
  }

  if (performanceButton) {
    performanceButton.addEventListener('click', handlePerformanceButton);
  }

  window.addEventListener('seepo:online', function () {
    handleConnectivityChange();
  });

  window.addEventListener('seepo:offline', function () {
    handleConnectivityChange();
  });

  window.addEventListener('seepo:sync-complete', function () {
    handleSyncComplete().catch(function (error) {
      console.error('Offline sheet refresh after sync failed', error);
    });
  });

  window.addEventListener('seepo:queue-status', function () {
    updateRowPendingState();
  });

  document.addEventListener('DOMContentLoaded', function () {
    refreshFromStorage();
    if (navigator.onLine) {
      syncQueuedSheets();
    }
  });
})();
