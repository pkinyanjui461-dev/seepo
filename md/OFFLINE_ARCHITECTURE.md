# SEEPO Offline Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser / PWA                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  DOM / Forms (HTML Templates)                        │   │
│  │  - Add data-offline-model="X" to forms               │   │
│  │  - Add data-offline-draft-label="Y" to draft forms   │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↓ Input Events                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-form-auto-persist.js                        │ │
│  │  - Listens to input/change events                    │ │
│  │  - Saves field values to localStorage                │ │
│  │  - Restores fields on page load                      │ │
│  │  - 7-day expiry per field                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                    Form Submit ↓                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-form-handler.js                             │ │
│  │  - Intercepts form.submit() events                   │ │
│  │  - Validates form.checkValidity()                    │ │
│  │  - Calls seepoOfflineSync.saveOffline()              │ │
│  └────────────────────────────────────────────────────────┘ │
│                    saveOffline(model, record)  ↓             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-sync.js (SeepoOfflineSync class)            │ │
│  │  - Adds client_uuid + client_updated_at              │ │
│  │  - Calls seepoOfflineDb.save(model, record)          │ │
│  │  - Dispatch event "seepo:queue-status"               │ │
│  │  - Shows toast "Saved offline"                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                    save() ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-db.js (Dexie ORM)                           │ │
│  │  - IndexedDB: seepoOfflineDb (v2)                    │ │
│  │  - Tables: groups, members, monthly_forms,           │ │
│  │    expenses, users, sync_meta                        │ │
│  │  - Record fields: {client_uuid, client_updated_at,   │ │
│  │    synced=0, server_id=null, ...data}                │ │
│  │  - Index on synced, client_uuid                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                    synced=0 ↓                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-global-state.js (SeepoOfflineState)         │ │
│  │  - Monitors navigator.onLine                         │ │
│  │  - Manages green/red status indicator                │ │
│  │  - Shows/hides offline banner                        │ │
│  │  - Schedules auto-sync every 5 seconds               │ │
│  │  - Triggers syncNow() when online                    │ │
│  │  - Triggers syncNow() on online event                │ │
│  └────────────────────────────────────────────────────────┘ │
│                    triggerSync() ↓                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  offline-sync.js (SeepoOfflineSync.syncNow)          │ │
│  │  1. Check navigator.onLine                           │ │
│  │  2. For each model in order:                         │ │
│  │     - pushModel() → POST to /api/sync/push/          │ │
│  │     - pullModel() → GET from /api/sync/pull/         │ │
│  │  3. runAuxiliarySyncs() (diary, drafts)              │ │
│  │  4. updateQueueChip() display                        │ │
│  │  5. Show toast "Synced X records"                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                    /api/sync/push ↓                           │
├─────────────────────────────────────────────────────────────┤
│                     Network / HTTP                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Server: Django Views                                         │
│  - /api/sync/push/ → POST (save pending)                     │
│  - /api/sync/pull/ → GET (fetch latest)                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Form Auto-Persist (`offline-form-auto-persist.js`)

**Purpose:** Users don't lose data if browser closes.

```javascript
// Listen to input/change on all form fields
input.addEventListener('input', () => {
  localStorage.setItem(`seepoDraftField_${formAction}|${fieldName}`, value);
  localStorage.setItem(`seepoDraftExpiry_${key}`, Date.now() + 7_days);
});

// On page load, restore previous values
const draft = localStorage.getItem(key);
if (draft) input.value = draft;
```

**Storage:** localStorage (not synced)
**Expiry:** 7 days per field
**Scope:** Any form, any field (automatic)

### 2. Global State Manager (`offline-global-state.js`)

**Purpose:** Manage online/offline transitions and auto-sync.

```javascript
const STATE = {
  isOnline: navigator.onLine,
  isSyncing: false,
  lastSyncTime: null,
};

// Each 5 seconds when online
setInterval(() => {
  if (STATE.isOnline && !STATE.isSyncing) {
    triggerAutoSync();
  }
}, 5000);

// On network transitions
window.addEventListener('online', handleOnline);
window.addEventListener('offline', handleOffline);
```

**Displays:**
- Green/red dot (bottom-right)
- Red banner (shows when offline)
- Auto-syncs without user interaction

### 3. Sync Engine (`offline-sync.js`)

**Purpose:** Orchestrate data push/pull.

```javascript
async syncNow() {
  // Check online
  if (!navigator.onLine) {
    return { success: false };
  }

  // 1. PUSH: Send pending (synced=0)
  for (const model of ['group', 'member', 'monthly_form', 'expense']) {
    await this.pushModel(model);
  }

  // 2. PULL: Fetch latest
  for (const model of ['group', 'member', ...]) {
    await this.pullModel(model);
  }

  // 3. Update UI
  await this.refreshStatus();

  // 4. Show result
  return { success: true, errors: [] };
}
```

**Push Logic:**
```javascript
const pending = await table.where('synced').equals(0).toArray();
const body = { model: 'member', records: [ {...}, {...} ] };
const response = await fetch('/api/sync/push/', {
  method: 'POST',
  body: JSON.stringify(body),
  headers: { 'X-CSRFToken': csrfToken }
});

// Server responds:
// { synced: 2, records_saved: [{server_id: 123, ...}, ...] }

// Mark synced locally:
for (const saved of response.records_saved) {
  await table.update(saved._localId, {
    synced: 1,
    server_id: saved.server_id
  });
}
```

**Pull Logic:**
```javascript
const response = await fetch('/api/sync/pull/?model=member&since=123456');
const { records } = await response.json();

// Merge into local DB
for (const record of records) {
  const existing = await table.where('client_uuid').equals(
    record.client_uuid
  ).first();

  if (existing) {
    // Conflict detection via timestamps
    if (new Date(record.client_updated_at) > existing.client_updated_at) {
      await table.update(existing._localId, record);
    }
  } else {
    // New record from server
    await table.add({ ...record, synced: 1 });
  }
}
```

### 4. IndexedDB (`offline-db.js`)

**Database:** `seepoOfflineDb`

**Schema (v2):**
```javascript
db.version(2).stores({
  groups: '++_localId,&client_uuid,synced,client_updated_at,name',
  members: '++_localId,&client_uuid,synced,client_updated_at,...',
  monthly_forms: '++_localId,&client_uuid,synced,...',
  expenses: '++_localId,&client_uuid,synced,...',
  users: '++_localId,&client_uuid,synced,...',
  sync_meta: '&model,last_pull_ts',
});
```

**Record Shape:**
```javascript
{
  _localId: 1,                    // Auto-increment (local only)
  client_uuid: 'uuid-123',        // Unique identifier
  client_updated_at: '2024-04-13T10:00:00Z',  // When modified
  synced: 0,                      // 0=pending, 1=synced
  server_id: null,                // Set after successful push

  // Model data:
  name: 'Group A',
  location: 'Downtown',
  ...
}
```

### 5. Form Handler (`offline-form-handler.js`)

**Purpose:** Intercept form submits and save to IndexedDB.

```javascript
form.addEventListener('submit', async (event) => {
  const modelName = form.getAttribute('data-offline-model');

  if (!seepoOfflineSync) return;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  event.preventDefault();

  // Collect form data
  const payload = collectFormData(form);

  // Save with auto-generated UUID
  await seepoOfflineSync.saveOffline(modelName, payload);

  // Show toast
  seepoOfflineSync.showToast('Saved offline. Will sync when online.');

  // Clear form
  form.reset();
});
```

## Data Flow: Create → Sync → Server

### 1. Create Offline
```
User fills form → Submit → saveOffline()
  ↓
payload = { name: 'Group A', location: 'City' }
  ↓
record = {
  client_uuid: 'uuid-abc123',     // Generated now
  client_updated_at: '2024-04-13T10:00:00Z',
  synced: 0,
  ...payload
}
  ↓
seepoOfflineDb.groups.add(record)
  ↓
Toast: "Saved offline"
```

### 2. Auto-Sync (5 seconds later or on online)
```
triggerAutoSync() called
  ↓
Check: navigator.onLine? → YES
Check: isSyncing? → NO
  ↓
syncNow() runs
  ↓
PUSH: Get all synced=0 records
  POST /api/sync/push/ { model: 'group', records: [...] }
  ↓
Server processes:
  - Create new groups with returned server_id
  - Return { synced: 1, records_saved: [...] }
  ↓
Update local: synced=1, server_id=123
  ↓
PULL: GET /api/sync/pull/?model=group&since=123456
  ↓
Merge any server-side changes
  ↓
Toast: "Synced 1 group record"
```

### 3. Server View
```
POST /api/sync/push/

Payload:
{
  "model": "group",
  "records": [
    {
      "client_uuid": "uuid-abc123",
      "client_updated_at": "2024-04-13T10:00:00Z",
      "name": "Group A",
      "location": "City",
      ...
    }
  ]
}

Response:
{
  "synced": 1,
  "records_saved": [
    {
      "_localId": 0,        // Must match request
      "server_id": 42,      // New DB ID
      "client_uuid": "uuid-abc123"
    }
  ]
}
```

## Conflict Resolution

**Strategy:** Last-Write-Wins (LWW) via `client_updated_at` timestamp.

**Scenario:**
```
Offline Device:  Creates Group A at 10:00 AM (client_updated_at=10:00)
  ↓ (goes offline)
Server:          Creates Group A independently at 10:05 AM
  ↓ (device comes online)
Pull:            Receives server's group (client_updated_at=10:05)
  ↓
Compare:         10:05 > 10:00 (server is newer)
  ↓
Merge:           Server version wins

Result: Single group with server's data
```

**How it works:**
```javascript
async pullModel(modelName) {
  const response = await fetch(`/api/sync/pull/?model=${modelName}`);
  const { records } = await response.json();

  for (const record of records) {
    const existing = await table
      .where('client_uuid')
      .equals(record.client_uuid)
      .first();

    if (existing) {
      const serverTime = new Date(record.client_updated_at);
      const localTime = new Date(existing.client_updated_at);

      if (serverTime > localTime) {
        // Server is newer, overwrite
        await table.update(existing._localId, record);
      }
      // else: local is newer, keep local
    }
  }
}
```

## Adding Offline to Existing Forms

### Step 1: Add HTML Attribute
```html
<!-- Before: Regular form -->
<form method="POST" action="/groups/create/">

<!-- After: Offline-enabled form -->
<form method="POST" action="/groups/create/" data-offline-model="group">
```

### Step 2: Ensure Model Handler Exists
Server needs to accept POST to the form's action endpoint and:
1. Extract `data-offline-model` or check JSON for model type
2. Generate `client_uuid` if missing
3. Save record with `synced` field capability

### Step 3: Add Redirect (Optional)
```html
<form ... data-offline-redirect-url="/groups/">
  <!-- After save, user is redirected -->
</form>
```

### Step 4: Test
1. Go offline
2. Submit form
3. Should save without error
4. Form clears
5. Go online
6. Should sync automatically

## Performance Considerations

### Sync Frequency
- **Default:** Every 5 seconds when online
- **Change in:** `offline-global-state.js` line ~60
- **Impact:** Higher = faster sync, more requests; Lower = less network, more latency

### IndexedDB Limits
- Chrome: 50% of disk space (unlimited on Android)
- Firefox: 10% of disk space
- Safari: 50MB per origin
- Edge: Same as Chrome

**Our usage:** ~100KB per 100 records (small overhead)

### Compression
Currently no compression. Can add:
```javascript
// Compress large objects before storage
const compressed = JSON.stringify(record); // Already small
```

## Debugging

### Browser Console
```javascript
// Check status
window.seepoOfflineSync.getQueueStatus()
// { total: 3, breakdown: { group: 1, member: 2 } }

// Check DB
window.seepoOfflineDb.groups.toArray()
// [{ _localId: 1, client_uuid: '...', synced: 0, ... }]

// Try manual sync
window.seepoOfflineSync.syncNow()
// Promise resolves with { success: true, errors: [] }

// Check connection
navigator.onLine
// true or false
```

### Local Storage
```javascript
// View all draft fields
for (let i = 0; i < localStorage.length; i++) {
  const key = localStorage.key(i);
  if (key.startsWith('seepoDraftField_')) {
    console.log(key, localStorage.getItem(key));
  }
}
```

### Service Worker
```javascript
// View caches
caches.keys().then(names => console.log(names))
// ['seepo-offline-shell-v29', 'seepo-offline-runtime-v29']

// View cached URLs
caches.open('seepo-offline-shell-v29').then(cache => cache.keys())
```

## Deployment

### Version Bumping
When updating offline scripts, bump versions in:
- `templates/offline_sync/sw.js` - `CACHE_VERSION`, asset versions
- This forces service worker reload and cache bust

### Example
```javascript
const CACHE_VERSION = 'v29';  // v28 → v29
const OFFLINE_GLOBAL_STATE_VERSION = '1';  // New script
```

Service worker detects version change, clears old caches, re-downloads all files.

## Security

### CSRF Protection
All POST requests include `X-CSRFToken` header:
```javascript
const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
headers: { 'X-CSRFToken': csrfToken }
```

### Data Privacy
- IndexedDB is local to browser → not sent to server auto-magically
- Only synced when user is online (their choice)
- localStorage same origin policy → can't be accessed cross-site

### Model Access Control
Server `/api/sync/push/` validates `request.user` and model permissions (same as normal views).

## Future Enhancements

1. **Encryption:** Encrypt IndexedDB for sensitive data
2. **Sync Conflicts UI:** Show user when merge happened
3. **Bandwidth Limits:** Defer sync on slow connections
4. **Batch Sync:** Compress multiple records in single request
5. **Partial Sync:** Selective "sync this record now"
6. **Conflict History:** Keep old versions for audit

---

**Status:** Production-ready. Tested on Chrome, Firefox, Safari, Edge mobile.
