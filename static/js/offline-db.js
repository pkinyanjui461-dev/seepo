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

  window.seepoOfflineDb = {
    db,
    modelTableMap,
    tableForModel,
    getPendingCount
  };
})();
