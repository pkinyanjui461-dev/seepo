# Offline Implementation Constraints (SEEPO)

This document defines mandatory constraints for modifying the offline-first implementation in this repository.

## Scope

These constraints apply to:
- Service Worker behavior
- IndexedDB schema and sync logic
- Offline-enabled forms and templates
- Sync API contracts
- Static asset loading for offline shell

## Core Rule

The browser is the offline write/read buffer, Django is the source of truth.

## Files That Form the Offline Core

- `offline_sync/views.py`
- `offline_sync/urls.py`
- `offline_sync/registry.py`
- `templates/offline_sync/sw.js`
- `templates/offline_sync/offline.html`
- `static/js/offline-db.js`
- `static/js/offline-sync.js`
- `static/js/offline-form-handler.js`
- `static/js/sw-register.js`
- `templates/base.html`

Do not change behavior in one file without checking the others.

## Data Model Contract (Mandatory)

Every model enabled for offline sync must have:
- `client_uuid` (UUID, unique, indexed)
- `client_updated_at` (DateTime, indexed)
- `updated_at` (server-side last update)

If a model is missing these fields, do not add it to offline sync yet.

## Sync API Contract (Do Not Break)

`/api/sync/push/` request payload:
- `model`: string
- `records`: array of objects with `client_uuid`

`/api/sync/push/` response payload must keep:
- `synced`
- `conflicts`
- `errors`
- `records_saved` with `client_uuid` and `server_id`

`/api/sync/pull/` response payload must keep:
- `records`
- `count`
- `ts`

If you rename fields, update browser sync logic and tests in the same change.

## IndexedDB Contract (Do Not Break)

Database name: `seepoOfflineDb`

Current object stores:
- `groups`
- `members`
- `monthly_forms`
- `expenses`
- `sync_meta`

Required record fields for sync-managed stores:
- `client_uuid`
- `client_updated_at`
- `synced` (0 or 1)
- `server_id` (set after successful push)

Do not delete or rename stores without Dexie migration code.

## Service Worker Constraints

- Keep `/api/sync/*` out of SW interception (must hit network when online).
- Keep offline fallback route `/offline/` available.
- Keep shell pre-cache list aligned with template static imports.
- For navigation requests, use network-first with cached/fallback response.
- Bump SW cache version when changing cache strategy.

## Static Asset Constraints

All assets referenced in templates must exist under `static/`.

Current required shell assets:
- `static/css/main.css`
- `static/js/sidebar.js`
- `static/js/offline-db.js`
- `static/js/offline-sync.js`
- `static/js/offline-form-handler.js`
- `static/js/sw-register.js`
- `static/img/logo.png`
- `static/favicon.ico`

If any are removed/renamed, update:
- `templates/base.html`
- `templates/accounts/login.html`
- `templates/offline_sync/sw.js`

## Form Integration Rules

Offline-enabled forms must declare:
- `data-offline-form="true"`
- `data-offline-model="<model_name>"`
- `data-offline-redirect-url="<url>"`

If model has FK dependency by UUID, include needed `data-*` attributes (example: `data-group-client-uuid`).

## Read-Data Preload Rules

`static/js/offline-sync.js` performs preload pulls for key models.

When adding a new offline model:
1. Add it to `MODEL_ORDER`
2. Add store mapping in `offline-db.js`
3. Add backend registry spec in `offline_sync/registry.py`
4. Add/adjust tests in `offline_sync/tests.py`

Do not add a model to only one layer.

## Testing Requirements Before Merge

Minimum required:
- `python manage.py check`
- `python manage.py test offline_sync -v 2`

Manual protocol required for major offline changes:
- server kill test
- offline form save verification in IndexedDB
- reconnect replay verification to DB
- debug endpoint verification

## Migration/Deployment Workflow Constraint

Before migrations in deploy pipeline:
- Run `python pgbackup.py backup --label before-feature-x`

The backup script is engine-aware (PostgreSQL/MySQL). Do not remove this step.

## Git and Line Endings

Repository enforces LF with `.gitattributes`.

If line endings drift:
- `git add --renormalize .`

## Safe Change Process

For any offline-related change, do this order:
1. Update backend API/model contract (if needed)
2. Update IndexedDB/schema mapping
3. Update SW/template/static references
4. Update tests
5. Run checks/tests
6. Validate one manual offline round-trip
