# Offline-First Demo & Testing Guide

## What's New

Your SEEPO app now has **seamless offline-first functionality**. No manual syncing, no "connection lost" errors, no data loss.

## 5-Minute Demo Setup

### 1. **Start the app normally**
```bash
python manage.py runserver
```

### 2. **Open DevTools & Test Offline**
- Chrome: DevTools → Network tab → **Offline** checkbox
- Work offline for a few minutes
- Uncheck **Offline** to reconnect

## What Each Page Now Does Offline

### ✅ Cached Pages (Read-only)
- Dashboard (shows cached data)
- Groups list
- Members list
- Finance/Expenses
- Reports
- Diary view

**Offline:** See all previously viewed data ✓

### ✅ Create Pages (with `data-offline-model`)
Currently enabled on:
- [Groups Create](/groups/create/) - `data-offline-model="group"`
- [Members Create](/members/create/) - `data-offline-model="member"`
- [Monthly Forms Create](/finance/monthly-forms/create/) - `data-offline-model="monthly_form"`
- [Expenses Create](/finance/create-expense/) - `data-offline-model="expense"`

**What happens offline:**
1. Fill out form (auto-drafts as you type)
2. Click Submit
3. Data saves to local IndexedDB
4. Toast: "Saved offline. Will sync when online."
5. Go back online → auto-syncs in next 5 seconds
6. See "Synced 1 group record" toast ✓

### ✅ Form Drafts (Auto-Recovery)
Every form field on the site auto-saves as you type:
1. Start filling form for a member
2. Accidentally close tab
3. Come back 5 minutes later
4. Your data is restored! ✓
5. Drafts expire after 7 days

### ✅ Inline Table Edits (Finance)
Finance table cells already support offline:
1. Click on a number cell (e.g., Member contribution)
2. Type new value offline
3. Row shows "pending" indicator
4. Go online → auto-syncs ✓

## Testing Scenarios

### Scenario 1: Create Data While Offline
**Goal:** Prove offline creation works
```
1. Go offline (DevTools → Offline)
2. Navigate to /groups/create/
3. Fill: Name="Test Group", Location="Demo", Officer="John"
4. Submit button works ✓
5. Toast: "Saved offline"
6. Navigate to /groups/ (cached)
7. Does NOT show new group yet (offline cache)
8. Go online
9. Dashboard updates, new group appears ✓
10. "Sync completed" toast
```

### Scenario 2: Form Field Recovery
**Goal:** Prove draft recovery works
```
1. Go to /members/create/
2. Fill fields: Name="Alice", Member#="005", Phone="555-1234"
3. CLOSE THE TAB (don't submit)
4. Reopen same URL
5. Fields are populated with drafted data ✓
6. Submit now
```

### Scenario 3: Auto-Sync Behavior
**Goal:** Prove background auto-sync
```
1. Go offline
2. Create 3 groups (one every 10 seconds)
3. Toast after each: "Saved offline"
4. Wait, then go back online
5. Within 5 seconds: Auto-sync triggers
6. Single toast: "Synced 3 group records" ✓
7. No manual "Sync" button needed
```

### Scenario 4: Multiple Data Types
**Goal:** Show sync orchestration
```
1. Go offline
2. Create a group
3. Create a member in that group
4. Create an expense
5. Go online
6. Watch queue chip update: "Groups: 1 | Members: 1 | Expenses: 1"
7. Auto-syncs all in dependency order ✓
```

## What You See Offline

### Online Status Indicator
- **Green dot** (bottom-right) = Online ✓
- **Red dot** (bottom-right) = Offline 🔴

### Offline Banner
When offline, red banner shows:
> 📡 You're working offline. Data is saved locally and will sync when you're back online.

"Close" button hides it, but it returns if you stay offline.

### Pending Queue Chip
Top toolbar shows pending changes:
- "No queued records" (online, all synced)
- "Groups: 2 | Members: 1" (when offline)
- Auto-updates as you create data

## Implementation Details

### Key Files Added/Modified

**New Files:**
- `static/js/offline-form-auto-persist.js` - Auto-saves form fields to localStorage
- `static/js/offline-global-state.js` - Manages online/offline state + auto-sync loop

**Modified Files:**
- `templates/base.html` - Added script loads
- `static/css/main.css` - Added offline banner styles
- `templates/offline_sync/sw.js` - Updated cache version
- `templates/accounts/login.html` - Added global state script

**Data Flow:**
```
User types form → Auto-persist to localStorage
                     ↓
User submits → Saves to IndexedDB (if offline-model)
                     ↓
Goes online → Global state triggers auto-sync (every 5s)
                     ↓
Sync engine pushes records → Shows toast on completion
```

### Sync Orchestration
1. **Check connection** - Runs every 5 seconds if online
2. **Push pending** - Sends all client_uuid records to server
3. **Pull fresh** - Gets latest from server, merges locally
4. **Mark synced** - Sets synced=1 in IndexedDB
5. **Toast confirmation** - "Synced 5 records"

## Customization Points

### Change Auto-Sync Interval
Edit `static/js/offline-global-state.js`:
```javascript
const AUTO_SYNC_INTERVAL_MS = 5000; // milliseconds
```

Change to 10000 for 10-second intervals.

### Disable Auto-Sync Banner
Edit `static/js/offline-global-state.js`, comment out line:
```javascript
// showOfflineBanner(true);
```

### Extend Form Draft Expiry
Edit `static/js/offline-form-auto-persist.js`:
```javascript
const DRAFT_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000; // Change 7 to desired days
```

### Add New Create Pages
Add `data-offline-model="modelname"` to any form:
```html
<form method="POST" data-offline-model="mytype">
  <!-- Works offline now -->
</form>
```

## Monitoring

### Browser Console (DevTools)
- `window.seepoOfflineState.isOnline()` - Current status
- `window.seepoOfflineState.isSyncing()` - Sync in progress?
- `window.seepoOfflineSync.getQueueStatus()` - Pending records

### Admin Panel
(Coming soon) - See all offline records waiting to sync

## Known Limitations

1. **Server creation endpoints** must exist for models
   - Create handler processes `data-offline-model` form posts
   - Auto-generates `client_uuid` on first pass

2. **Read-only before login**
   - Offline page cache requires prior page visit
   - First-time users see offline fallback page

3. **One device at a time**
   - Offline data per browser, not per device
   - Multiple browsers = separate offline caches

## Testing Checklist

- [ ] Visit dashboard online, then go offline
- [ ] Dashboard still works with cached data offline
- [ ] Green → Red dot transitions when network toggles
- [ ] Red offline banner shows when offline
- [ ] Can fill form fields offline (auto-drafts)
- [ ] Form submit works offline (data queues)
- [ ] Close tab, come back, fields restored
- [ ] Go online: auto-sync happens within 5 seconds
- [ ] Multiple data types sync in correct order
- [ ] Sync toast shows "Synced X records"
- [ ] Queue chip updates as you create data
- [ ] No manual refresh or retry needed
- [ ] Server shows new data after sync ✓

---

**TL;DR:** Users can now work offline seamlessly. No connection? No problem. Keep creating data. Walk to WiFi. Everything syncs automatically.
