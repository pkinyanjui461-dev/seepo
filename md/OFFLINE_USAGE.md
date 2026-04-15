# SEEPO Seamless Offline Guide

All pages now support automatic offline-first functionality with zero additional code required beyond adding HTML attributes.

## How It Works

### 1. **Automatic Online/Offline Detection** ✅
- Green dot (bottom-right) = Online
- Red dot = Offline
- Red banner shows when you go offline
- Data auto-syncs when reconnected

### 2. **Automatic Form Drafts** ✅
- Any form field you start typing in is saved locally
- If you close the browser/tab, come back later, your data is restored
- Drafts expire after 7 days of inactivity

### 3. **Create/Submit Forms Offline** (with data-offline-model)
Add this attribute to forms to enable offline creation:

```html
<form method="POST" data-offline-model="member">
  <input type="text" name="name" required>
  <input type="text" name="phone" >
  <button type="submit">Create Member</button>
</form>
```

Supported models:
- `group` - Create groups
- `member` - Create members
- `monthly_form` - Create monthly forms
- `expense` - Create expenses
- `user` - Create users

When offline:
✓ Form data saves locally
✓ Submit button works
✓ Saves to IndexedDB with `client_uuid`
✓ Toast shows "Saved offline. Will sync when online."

When online:
✓ Form submits normally
✓ Toast shows "Saved locally and queued for sync"
✓ Auto-syncs in background

### 4. **Draft Forms** (with data-offline-draft-label)
For forms that should queue for later submission:

```html
<form method="POST" action="/path/to/submit/" data-offline-draft-label="expense">
  <input type="text" name="description">
  <input type="number" name="amount">
  <button type="submit">Save Draft</button>
</form>
```

When offline:
✓ Form queues for retry
✓ Shows in "Drafts" pending count
✓ Retries automatically when online
✓ Can be cleared from offline panel

### 5. **Auto-Sync Behavior**
- Every 5 seconds (if online), checks for pending changes
- On first page load, syncs all pending data in background
- When transitioning from offline→online, syncs immediately
- Shows pending count in top toolbar

### 6. **Read-Only Pages Work Offline**
- All cached pages work offline
- View groups, members, finance data from offline cache
- Finance form table updates queue locally even when offline

## Adding Offline to New Forms

### Option A: Full CRUD (Create/Update/Delete)
```html
<form method="POST"
      data-offline-model="member"
      data-group-client-uuid="GROUP-UUID">
  <input type="text" name="name" required>
  <input type="text" name="member_number" required>
  <button type="submit">Create Member</button>
</form>
```

### Option B: Draft Queue (Save for Later)
```html
<form method="POST"
      action="/members/create/"
      data-offline-draft-label="member"
      data-offline-draft-key="create-member">
  <input type="text" name="name">
  <input type="text" name="phone">
  <button type="submit">Queue Entry</button>
</form>
```

### Option C: Inline Table Edits (Finance)
Already implemented. Just use normal inputs in table cells with:
```html
<input type="number" class="calc-input" data-save-url="/finance/performance/0/update/">
```

## Testing Offline

**DevTools simulation:**
1. Open Chrome DevTools → Network tab
2. Check "Offline" box
3. Create a group/member/form
4. Watch data save to local storage
5. Uncheck "Offline"
6. See data auto-sync

**Real app test:**
1. Go offline in settings
2. Create test data
3. Go back online
4. Watch pending sync happen automatically

## Customization

### Auto-Save Behavior
Files control auto-saves:
- `offline-form-auto-persist.js` - Form field recovery (7-day expiry)
- `offline-global-state.js` - Auto-sync every 5s when online
- `offline-draft-queue.js` - Manual form queuing
- `offline-sync.js` - Core sync engine

To change sync interval, edit `offline-global-state.js`:
```javascript
const AUTO_SYNC_INTERVAL_MS = 5000; // Change to 10000 for 10 seconds
```

## What Syncs Automatically

✅ **Created locally (data-offline-model):**
- Groups
- Members
- Monthly Forms
- Expenses
- Users

✅ **Draft forms (data-offline-draft-label):**
- Any form with draft-label attr
- Detected as "Draft" type in queue

✅ **Diary updates:**
- Inline diary cell edits
- Auto-queued when offline

✅ **Finance table rows:**
- Inline calculations
- Row updates detected automatically

## Conflict Resolution

If the same record is edited on server while offline:
1. Server version is shown in pull
2. Local version in IndexedDB is marked `synced=0`
3. Next push compares `client_updated_at` timestamps
4. Later timestamp wins (LWW - Last Write Wins)

## Disabling Auto-Sync

Don't add `data-offline-model` to forms that shouldn't work offline.
Forms without the attribute:
- Block submit when offline
- Show "requires internet access" toast
- Allow reading cached data only

## FAQ

**Q: Where is offline data stored?**
A: IndexedDB (`seepoOfflineDb`) for synced models, localStorage for drafts/updates.

**Q: Does offline sync clear when I log out?**
A: No. Browser storage persists. On next login with same account, sync continues.

**Q: What if I clear browser storage?**
A: All pending changes are lost. Recommend syncing before clearing.

**Q: Can multiple team members use one device?**
A: Each must log in separately. Storage is shared per browser.

**Q: Does it work on mobile apps?**
A: Yes, this is a PWA. Install to home screen for full offline app.

---

**Summary:** The app is now truly offline-first. Users can work without interruption, and data syncs automatically when connection returns. No "syncing..." spinners or manual retry buttons needed.
