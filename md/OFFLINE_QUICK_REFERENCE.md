# Quick Reference: Enable Offline on Any Form

## One-Minute Setup

Add `data-offline-model` to any form:

```html
<form method="POST" data-offline-model="member">
  <input type="text" name="name" required>
  <input type="phone" name="phone">
  <button type="submit">Create</button>
</form>
```

**That's it.** Form now works offline.

## Supported Models
- `group` — Create groups
- `member` — Create members
- `monthly_form` — Create monthly forms
- `expense` — Create expenses
- `user` — Create users

## What It Does

**Offline:**
- Form submit works ✓
- Data saves locally ✓
- Toast: "Saved offline" ✓
- No errors ✓

**Online:**
- Auto-syncs in next 5 seconds ✓
- Toast: "Synced X records" ✓
- Server DB updated ✓

## Advanced Options (Optional)

### Redirect After Save
```html
<form ... data-offline-redirect-url="/groups/">
```

### Group Context
```html
<form ... data-group-client-uuid="GROUP-UUID">
```

### Custom Submit Label
```html
<form ... data-offline-draft-label="mytype">
```

## Testing

**DevTools Online/Offline Toggle:**
1. F12 → Network tab
2. Check "Offline"
3. Submit form
4. Uncheck "Offline"
5. Auto-syncs in 5 seconds ✓

## Auto Features (No Config Needed)

### Form Field Recovery
- Type something → Auto-saves
- Close tab → Come back later
- Your data is restored ✓

### Global Status
- Green dot = Online
- Red dot = Offline
- Red banner = "You're offline..."

### Auto-Sync Loop
- Every 5 seconds (when online)
- Checks for pending data
- Sends to server
- Shows result toast
- No manual button needed

## Debugging

```javascript
// Check what's pending
window.seepoOfflineSync.getQueueStatus()
// → { total: 3, breakdown: { member: 2, expense: 1 } }

// View local DB records
window.seepoOfflineDb.members.toArray()
// → [{_localId: 1, client_uuid: '...', synced: 0, ...}]

// Manual sync
await window.seepoOfflineSync.syncNow()
// → { success: true, errors: [] }

// Check online status
navigator.onLine
// → true or false
```

## Customization

### Sync Every 10 Seconds (Instead of 5)
Edit `static/js/offline-global-state.js`:
```javascript
const AUTO_SYNC_INTERVAL_MS = 10000;  // was 5000
```

### Draft Expiry (Instead of 7 Days)
Edit `static/js/offline-form-auto-persist.js`:
```javascript
const DRAFT_EXPIRY_MS = 14 * 24 * 60 * 60 * 1000;  // 14 days
```

## Full Docs

- **User Guide:** [OFFLINE_USAGE.md](./OFFLINE_USAGE.md)
- **Testing:** [OFFLINE_DEMO.md](./OFFLINE_DEMO.md)
- **Architecture:** [OFFLINE_ARCHITECTURE.md](./OFFLINE_ARCHITECTURE.md)

## Support

Q: Where is data stored?
A: IndexedDB (`seepoOfflineDb`)

Q: Will I lose data if browser closes?
A: No. Data persists. Form fields also recovered.

Q: What if I'm offline for days?
A: Data waits locally. No expiry. Syncs when ready.

Q: Does it work on mobile?
A: Yes. Install as PWA for full offline app.

Q: Can I delete pending data?
A: Yes, from offline panel (top toolbar "Sync" button).

---

**Status:** ✅ Production Ready | All Forms Supported | Auto-Sync Enabled
