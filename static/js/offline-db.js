(function () {
  if (!window.Dexie) {
    console.warn('Dexie is not available. Offline DB is disabled.');
    return;
  }

  const db = new Dexie('seepoOfflineDb');
  db.version(2).stores({
    groups: '++_localId,&client_uuid,synced,client_updated_at,name',
    members: '++_localId,&client_uuid,synced,client_updated_at,group_client_uuid,name,member_number',
    monthly_forms: '++_localId,&client_uuid,synced,client_updated_at,group_client_uuid,year,month',
    expenses: '++_localId,&client_uuid,synced,client_updated_at,date,name',
    users: '++_localId,&client_uuid,synced,client_updated_at,username,phone_number,role',
    sync_meta: '&model,last_pull_ts'
  });

  const modelTableMap = {
    group: 'groups',
    member: 'members',
    monthly_form: 'monthly_forms',
    expense: 'expenses',
    user: 'users'
  };

  function tableForModel(modelName) {
    const tableName = modelTableMap[modelName];
    if (!tableName) {
      throw new Error('Unsupported offline model: ' + modelName);
    }
    return db.table(tableName);
  }

  async function getPendingCount() {
    let pending = 0;
    const models = Object.keys(modelTableMap);

    for (const modelName of models) {
      const table = tableForModel(modelName);
      pending += await table.where('synced').equals(0).count();
    }

    return pending;
  }

  async function getPendingBreakdown() {
    const breakdown = {};
    const models = Object.keys(modelTableMap);

    for (const modelName of models) {
      const table = tableForModel(modelName);
      const count = await table.where('synced').equals(0).count();
      if (count > 0) {
        breakdown[modelName] = count;
      }
    }

    return breakdown;
  }

  function buildPendingLabel(modelName, record) {
    if (modelName === 'group') {
      return record.name || 'Unnamed group';
    }

    if (modelName === 'member') {
      const numberSuffix = record.member_number ? ' #' + record.member_number : '';
      return (record.name || 'Unnamed member') + numberSuffix;
    }

    if (modelName === 'monthly_form') {
      const month = record.month || '?';
      const year = record.year || '?';
      return 'Monthly form ' + month + '/' + year;
    }

    if (modelName === 'expense') {
      const amount = record.amount ? ' (' + record.amount + ')' : '';
      return (record.name || 'Expense entry') + amount;
    }

    if (modelName === 'user') {
      return record.username || record.phone_number || 'User record';
    }

    return record.client_uuid || 'Pending record';
  }

  async function getPendingRecordsForSelection() {
    const models = Object.keys(modelTableMap);
    const items = [];

    for (const modelName of models) {
      const table = tableForModel(modelName);
      const pending = await table.where('synced').equals(0).toArray();

      pending.forEach(function (record) {
        items.push({
          model: modelName,
          localId: record._localId,
          clientUuid: record.client_uuid || '',
          label: buildPendingLabel(modelName, record),
          updatedAt: record.client_updated_at || '',
        });
      });
    }

    items.sort(function (a, b) {
      if (a.model !== b.model) {
        return a.model.localeCompare(b.model);
      }

      const aTime = new Date(a.updatedAt || 0).getTime();
      const bTime = new Date(b.updatedAt || 0).getTime();
      return bTime - aTime;
    });

    return items;
  }

  async function deletePendingRecords(selections) {
    if (!Array.isArray(selections) || !selections.length) {
      return 0;
    }

    let deleted = 0;

    for (const item of selections) {
      const modelName = String(item && item.model ? item.model : '').trim();
      const localId = Number(item && item.localId);

      if (!modelTableMap[modelName] || !Number.isFinite(localId)) {
        continue;
      }

      const table = tableForModel(modelName);
      const exists = await table.get(localId);
      if (!exists || Number(exists.synced) !== 0) {
        continue;
      }

      await table.delete(localId);
      deleted += 1;
    }

    return deleted;
  }

  window.seepoOfflineDb = {
    db,
    modelTableMap,
    tableForModel,
    getPendingCount,
    getPendingBreakdown,
    getPendingRecordsForSelection,
    deletePendingRecords
  };
})();
