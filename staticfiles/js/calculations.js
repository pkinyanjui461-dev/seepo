document.addEventListener('DOMContentLoaded', () => {
    const table = document.getElementById('financeTable');
    if (!table) return;

    const saveUrlBase = table.dataset.saveUrl.replace('/0/', '/ID/');
    let saveTimeout;

    // Attach input listeners
    table.querySelectorAll('.calc-input').forEach(input => {
        if (!input.readOnly) {
            input.addEventListener('input', (e) => {
                const tr = e.target.closest('tr');
                performRowCalculations(tr);
                calculateTotals();
                
                // Debounce save
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => {
                    saveRowData(tr);
                }, 800); // Save after 800ms of typing stop
            });
        }
    });

    function getVal(tr, field) {
        const input = tr.querySelector(`[data-field="${field}"]`);
        return parseFloat(input.value) || 0;
    }

    function setVal(tr, field, val) {
        const input = tr.querySelector(`[data-field="${field}"]`);
        if (!input) return;
        input.value = val === 0 ? '' : val.toFixed(0);
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
        const fines    = Math.round(getVal(tr, 'fines_charges'));

        // Calculated fields
        const loanInterest = Math.round(loanBf * 0.015);
        const shares       = repaid - (principal + loanInterest);  // Shares This Month
        const savCf        = savBf + shares;
        const loanCf       = loanBf - principal;

        // Only update the calculated read-only cells — never overwrite user-input cells
        setVal(tr, 'loan_interest', loanInterest);
        setVal(tr, 'shares_this_month', shares);
        setVal(tr, 'savings_share_cf', savCf);
        setVal(tr, 'loan_balance_cf', loanCf);

        // Client-side visual validation
        validateRow(tr, savBf, shares, savCf, loanBf, principal, loanCf);
    }

    function checkNegative(val, name, errors) {
        if (val < 0) {
            errors.push(`${name} cannot be negative.`);
            return true;
        }
        return false;
    }

    function validateRow(tr, savBf, shares, savCf, loanBf, principal, loanCf) {
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

        const expectedSavCf = savBf + shares;
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
                        'loan_interest', 'shares_this_month', 'fines_charges', 'savings_share_cf', 'loan_balance_cf'];
        
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

        const expTotalSav = totals['savings_share_bf'] + totals['shares_this_month'];
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
                // Show brief save toast
                const toast = document.getElementById('saveStatus');
                toast.style.display = 'block';
                setTimeout(() => toast.style.display = 'none', 1500);
            }
        } catch (e) {
            console.error("Failed to save row", e);
        }
    }

    // ── Run initial setup on page load ─────────────────────────────────
    // 1. Clear "0" from all user-editable (non-readonly) cells so they appear blank
    table.querySelectorAll('.calc-input:not([readonly])').forEach(input => {
        if (input.value === '0' || input.value === '0.00' || input.value === '') {
            input.value = '';
        }
    });

    // 2. Recalculate all computed fields (Loan Interest, Shares, Savings C/F, Loan C/F)
    //    using the saved data already in the DOM. This ensures calculated fields like
    //    "Shares This Month" are freshly derived on every page load, not stale DB values.
    document.querySelectorAll('.record-row').forEach(tr => {
        performRowCalculations(tr);
    });

    // 3. Update footer totals
    calculateTotals();
});
