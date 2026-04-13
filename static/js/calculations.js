document.addEventListener('DOMContentLoaded', () => {
    const table = document.getElementById('financeTable');
    if (!table) return;

    const OFFLINE_ROW_QUEUE_KEY = 'seepoMemberRecordRowQueueV1';
    const saveUrlBase = table.dataset.saveUrl.replace('/0/', '/ID/');
    const rowTimeouts = {};
    const saveStatusToast = document.getElementById('saveStatus');

    function showSyncToast(message, isError) {
        if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
            window.seepoOfflineSync.showToast(message);
            return;
        }

        if (!saveStatusToast) {
            if (isError) {
                console.error(message);
            } else {
                console.info(message);
            }
            return;
        }

        const toastBody = saveStatusToast.querySelector('.toast-body span');
        const toastCard = saveStatusToast.querySelector('.toast');
        if (toastBody) {
            toastBody.innerHTML = isError
                ? '<i class="fas fa-exclamation-triangle me-2"></i> ' + message
                : '<i class="fas fa-check-circle me-2"></i> ' + message;
        }
        if (toastCard) {
            toastCard.classList.remove('bg-success', 'bg-danger');
            toastCard.classList.add(isError ? 'bg-danger' : 'bg-success');
        }
        saveStatusToast.style.display = 'block';
        setTimeout(() => (saveStatusToast.style.display = 'none'), 2200);
    }

    function getRowQueue() {
        try {
            const raw = localStorage.getItem(OFFLINE_ROW_QUEUE_KEY);
            if (!raw) {
                return [];
            }

            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (_error) {
            return [];
        }
    }

    function setRowQueue(queue) {
        localStorage.setItem(OFFLINE_ROW_QUEUE_KEY, JSON.stringify(queue));
    }

    function queueRowPayload(recordId, url, data) {
        const dedupeKey = String(recordId || '') + '|' + String(url || '');
        const queue = getRowQueue();

        const payload = {
            id: dedupeKey,
            recordId: String(recordId || ''),
            url: url,
            data: data,
            updatedAt: new Date().toISOString(),
        };

        const existingIndex = queue.findIndex((item) => item.id === dedupeKey);
        if (existingIndex >= 0) {
            queue[existingIndex] = payload;
        } else {
            queue.push(payload);
        }

        setRowQueue(queue);
        markRowPending(recordId, true);
    }

    function clearQueuedRow(recordId, url) {
        const dedupeKey = String(recordId || '') + '|' + String(url || '');
        const queue = getRowQueue();
        const filtered = queue.filter((item) => item.id !== dedupeKey);

        if (filtered.length !== queue.length) {
            setRowQueue(filtered);
        }

        const stillPendingForRecord = filtered.some((item) => String(item.recordId) === String(recordId));
        markRowPending(recordId, stillPendingForRecord);
    }

    function markRowPending(recordId, isPending) {
        const row = document.querySelector('.record-row[data-record-id="' + String(recordId) + '"]');
        if (!row) {
            return;
        }

        if (isPending) {
            row.classList.add('row-pending-sync');
        } else {
            row.classList.remove('row-pending-sync');
        }
    }

    function applyQueuedDraftsToRows() {
        const queue = getRowQueue();
        queue.forEach((item) => {
            const row = document.querySelector('.record-row[data-record-id="' + String(item.recordId) + '"]');
            if (!row || !item.data) {
                return;
            }

            Object.keys(item.data).forEach((fieldName) => {
                const input = row.querySelector('[data-field="' + fieldName + '"]');
                if (input) {
                    input.value = item.data[fieldName];
                }
            });

            markRowPending(item.recordId, true);
        });
    }

    async function syncQueuedRows() {
        if (!navigator.onLine) {
            return { synced: 0, remaining: getRowQueue().length };
        }

        const queue = getRowQueue();
        if (!queue.length) {
            return { synced: 0, remaining: 0 };
        }

        const remaining = [];
        let synced = 0;

        for (const item of queue) {
            try {
                const res = await fetch(item.url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify(item.data || {}),
                });

                const result = await res.json();
                if (!res.ok || !result.success) {
                    remaining.push(item);
                    continue;
                }

                synced += 1;
                markRowPending(item.recordId, false);
            } catch (_error) {
                remaining.push(item);
            }
        }

        setRowQueue(remaining);

        remaining.forEach((item) => markRowPending(item.recordId, true));

        if (synced > 0) {
            showSyncToast('Synced ' + synced + ' queued row change' + (synced === 1 ? '' : 's') + '.', false);
        }

        return { synced: synced, remaining: remaining.length };
    }

    // Attach input listeners
    table.querySelectorAll('.calc-input').forEach(input => {
        if (!input.readOnly) {
            input.addEventListener('input', (e) => {
                const tr = e.target.closest('tr');
                const rowId = tr.dataset.recordId;

                performRowCalculations(tr);
                calculateTotals();

                // Debounce save per row
                clearTimeout(rowTimeouts[rowId]);
                rowTimeouts[rowId] = setTimeout(() => {
                    saveRowData(tr);
                    delete rowTimeouts[rowId];
                }, 500); // Save after 500ms of typing stop
            });
        }
    });

    // Manual save button functionality
    const manualSaveBtn = document.getElementById('manualSaveBtn');
    if (manualSaveBtn) {
        manualSaveBtn.addEventListener('click', async () => {
            const originalHTML = manualSaveBtn.innerHTML;
            manualSaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Saving...';
            manualSaveBtn.disabled = true;

            const rows = document.querySelectorAll('.record-row');
            if (!navigator.onLine) {
                rows.forEach((tr) => {
                    saveRowData(tr);
                });
                showSyncToast('Saved offline and queued. Changes will sync automatically when online.', false);
            } else {
                const promises = [];
                rows.forEach(tr => {
                    promises.push(saveRowData(tr));
                });

                await Promise.all(promises);
                await syncQueuedRows();
            }

            // Clear any pending debounced row saves
            Object.keys(rowTimeouts).forEach(rowId => clearTimeout(rowTimeouts[rowId]));
            for (let prop in rowTimeouts) { delete rowTimeouts[prop]; }

            manualSaveBtn.innerHTML = '<i class="fas fa-check me-1"></i> Saved';
            showSyncToast('Saved', false);

            setTimeout(() => {
                manualSaveBtn.innerHTML = originalHTML;
                manualSaveBtn.disabled = false;
            }, 2000);
        });
    }

    // Warn if leaving with unsaved changes
    window.addEventListener('beforeunload', (e) => {
        if (Object.keys(rowTimeouts).length > 0) {
            e.preventDefault();
            e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        }
    });

    function getVal(tr, field) {
        const input = tr.querySelector(`[data-field="${field}"]`);
        return parseFloat(input.value) || 0;
    }

    function setVal(tr, field, val) {
        const input = tr.querySelector(`[data-field="${field}"]`);
        if (!input) return;
        input.value = val.toFixed(0);
        const td = input.closest('td');
        // Flag negative calculated results with blinking red cell
        if (val < 0) {
            if (td) td.classList.add('cell-negative');
            input.style.color = '';   // let CSS control colour
        } else {
            if (td) td.classList.remove('cell-negative');
            input.style.color = '';
        }
    }

    function performRowCalculations(tr) {
        // Fetch raw values, parse to float, then round to nearest whole number
        const savBf    = Math.round(getVal(tr, 'savings_share_bf'));
        const loanBf   = Math.round(getVal(tr, 'loan_balance_bf'));
        const principal = Math.round(getVal(tr, 'principal'));
        const repaid   = Math.round(getVal(tr, 'total_repaid'));
        const withdrawals = Math.round(getVal(tr, 'withdrawals'));
        const fines    = Math.round(getVal(tr, 'fines_charges'));

        // Calculated fields
        const loanInterest = Math.round(loanBf * 0.015);

        // NEW LOGIC: If total repaid is 0, shares this month is 0.
        // If principal is 0 OR there are withdrawals, interest/principal is NOT deducted from repaid.
        let shares = 0;
        if (repaid <= 0) {
            shares = 0;
        } else if (principal === 0 || withdrawals > 0) {
            shares = repaid;
        } else {
            // Deduct principal and interest, but don't let shares go negative
            shares = Math.max(0, repaid - (principal + loanInterest));
        }

        const savCf        = savBf + shares - withdrawals;
        const loanCf       = loanBf - principal;

        // Only update the calculated read-only cells — never overwrite user-input cells
        setVal(tr, 'loan_interest', loanInterest);
        setVal(tr, 'shares_this_month', shares);
        setVal(tr, 'savings_share_cf', savCf);
        setVal(tr, 'loan_balance_cf', loanCf);

        // Client-side visual validation
        validateRow(tr, savBf, shares, withdrawals, savCf, loanBf, principal, loanCf);
    }

    function checkNegative(val, name, errors) {
        if (val < 0) {
            errors.push(`${name} cannot be negative.`);
            return true;
        }
        return false;
    }

    function validateRow(tr, savBf, shares, withdrawals, savCf, loanBf, principal, loanCf) {
        const recordId = tr.dataset.recordId;
        const loanCell = document.getElementById(`loan-bf-cell-${recordId}`);
        const savCell = document.getElementById(`savings-cf-cell-${recordId}`);

        let rowHasError = false;

        // Collect accumulated errors per cell
        let loanErrors = [];
        let savErrors = [];

        // Check for negatives in related logic for loans
        checkNegative(loanBf, "Loan B/F", loanErrors);
        checkNegative(loanCf, "Loan C/F", loanErrors);

        const expectedLoanBf = principal + loanCf;
        if (loanBf !== expectedLoanBf) {
            loanErrors.push(`Mismatch\nExpected: ${expectedLoanBf}\nCurrent: ${loanBf}`);
        }

        if (loanErrors.length > 0) {
            loanCell.classList.add('cell-error');
            loanCell.setAttribute('data-error', loanErrors.join('\n'));
            rowHasError = true;
        } else {
            loanCell.classList.remove('cell-error');
            loanCell.removeAttribute('data-error');
        }

        // Check for negatives in related logic for savings
        checkNegative(savBf, "Savings B/F", savErrors);
        checkNegative(savCf, "Savings C/F", savErrors);

        const expectedSavCf = savBf + shares - withdrawals;
        if (savCf !== expectedSavCf) {
            savErrors.push(`Mismatch\nExpected: ${expectedSavCf}\nCurrent: ${savCf}`);
        }

        if (savErrors.length > 0) {
            savCell.classList.add('cell-error');
            savCell.setAttribute('data-error', savErrors.join('\n'));
            rowHasError = true;
        } else {
            savCell.classList.remove('cell-error');
            savCell.removeAttribute('data-error');
        }

        if (rowHasError) tr.classList.add('row-error');
        else tr.classList.remove('row-error');
    }

    function calculateTotals() {
        const fields = ['savings_share_bf', 'loan_balance_bf', 'total_repaid', 'principal',
                        'loan_interest', 'shares_this_month', 'withdrawals', 'fines_charges', 'savings_share_cf', 'loan_balance_cf'];

        const totals = {};
        fields.forEach(f => totals[f] = 0);

        // Sum columns
        document.querySelectorAll('.record-row').forEach(tr => {
            fields.forEach(f => totals[f] += getVal(tr, f));
        });

        // Update footer UI
        const tdMap = {
            'savings_share_bf': 'tot-savings-bf',
            'loan_balance_bf': 'tot-loan-bf',
            'total_repaid': 'tot-repaid',
            'principal': 'tot-principal',
            'loan_interest': 'tot-interest',
            'shares_this_month': 'tot-shares',
            'withdrawals': 'tot-withdrawals',
            'fines_charges': 'tot-fines',
            'savings_share_cf': 'tot-savings-cf',
            'loan_balance_cf': 'tot-loan-cf'
        };

        fields.forEach(f => {
            const td = document.getElementById(tdMap[f]);
            if (td) td.innerText = totals[f] === 0 ? '' : totals[f].toFixed(0);
        });

        // Validate Footer Totals
        const loanTd = document.getElementById('tot-loan-bf');
        const savTd = document.getElementById('tot-savings-cf');

        const expTotalLoan = totals['principal'] + totals['loan_balance_cf'];
        if (totals['loan_balance_bf'] !== expTotalLoan) {
            loanTd.classList.add('cell-error', 'text-danger');
            loanTd.setAttribute('data-error', `Totals Mismatch\nExpected: ${expTotalLoan.toFixed(0)}`);
        } else {
            loanTd.classList.remove('cell-error', 'text-danger');
            loanTd.removeAttribute('data-error');
        }

        const expTotalSav = totals['savings_share_bf'] + totals['shares_this_month'] - totals['withdrawals'];
        if (totals['savings_share_cf'] !== expTotalSav) {
            savTd.classList.add('cell-error', 'text-danger');
            savTd.setAttribute('data-error', `Totals Mismatch\nExpected: ${expTotalSav.toFixed(0)}`);
        } else {
            savTd.classList.remove('cell-error', 'text-danger');
            savTd.removeAttribute('data-error');
        }
    }

    async function saveRowData(tr) {
        const recordId = tr.dataset.recordId;
        const url = saveUrlBase.replace('ID', recordId);

        const data = {};
        tr.querySelectorAll('.calc-input').forEach(input => {
            data[input.dataset.field] = input.value || "0";
        });

        if (!navigator.onLine) {
            queueRowPayload(recordId, url, data);
            return { queued: true };
        }

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(data)
            });
            const result = await res.json();

            if (result.success) {
                clearQueuedRow(recordId, url);
            }
        } catch (e) {
            queueRowPayload(recordId, url, data);
            console.error("Failed to save row", e);
        }

        return { queued: false };
    }

    // ── Run initial setup on page load ─────────────────────────────────
    // 1. Clear "0" from all user-editable (non-readonly) cells so they appear blank
    table.querySelectorAll('.calc-input:not([readonly])').forEach(input => {
        if (input.value === '0' || input.value === '0.00' || input.value === '') {
            input.value = '';
        }
    });

    // 2. Apply offline queued row drafts before recalculating.
    applyQueuedDraftsToRows();

    // 3. Recalculate all computed fields (Loan Interest, Shares, Savings C/F, Loan C/F)
    //    using the saved data already in the DOM. This ensures calculated fields like
    //    "Shares This Month" are freshly derived on every page load, not stale DB values.
    document.querySelectorAll('.record-row').forEach(tr => {
        performRowCalculations(tr);
    });

    // 4. Update footer totals
    calculateTotals();

    if (navigator.onLine) {
        syncQueuedRows();
    }

    window.addEventListener('online', () => {
        syncQueuedRows();
    });
});
