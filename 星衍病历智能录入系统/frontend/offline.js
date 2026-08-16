/* ============================================
   星衍AI · 离线模式模块
   功能：
   1. IndexedDB 本地存储（模板/患者/离线记录）
   2. 预加载数据包（查房前下载）
   3. 离线补录（断网可录入）
   4. 自动同步（恢复网络后上传）
   ============================================ */

(function (global) {
  'use strict';

  const DB_NAME = 'xingyan-offline';
  const DB_VERSION = 1;
  const STORES = {
    templates: 'templates',      // 预加载的模板
    patients: 'patients',        // 预加载的患者列表
    offlineRecords: 'offlineRecords',  // 离线补录的记录
    meta: 'meta',                // 元数据（上次同步时间等）
  };

  let _db = null;

  // ─── IndexedDB 初始化 ───
  function openDB() {
    return new Promise((resolve, reject) => {
      if (_db) return resolve(_db);

      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORES.templates)) {
          db.createObjectStore(STORES.templates, { keyPath: 'name' });
        }
        if (!db.objectStoreNames.contains(STORES.patients)) {
          db.createObjectStore(STORES.patients, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains(STORES.offlineRecords)) {
          const store = db.createObjectStore(STORES.offlineRecords, { keyPath: 'local_id' });
          store.createIndex('synced', 'synced');
        }
        if (!db.objectStoreNames.contains(STORES.meta)) {
          db.createObjectStore(STORES.meta, { keyPath: 'key' });
        }
      };
      req.onsuccess = () => { _db = req.result; resolve(_db); };
      req.onerror = () => reject(req.error);
    });
  }

  function tx(store, mode = 'readonly') {
    return openDB().then((db) => db.transaction(store, mode).objectStore(store));
  }

  // ─── 通用 CRUD ───
  function putAll(storeName, items) {
    return tx(storeName, 'readwrite').then((store) => {
      return Promise.all((items || []).map((item) => new Promise((resolve, reject) => {
        const req = store.put(item);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      })));
    });
  }

  function getAll(storeName) {
    return tx(storeName).then((store) => new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    }));
  }

  function deleteItem(storeName, key) {
    return tx(storeName, 'readwrite').then((store) => new Promise((resolve, reject) => {
      const req = store.delete(key);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    }));
  }

  function clearStore(storeName) {
    return tx(storeName, 'readwrite').then((store) => new Promise((resolve, reject) => {
      const req = store.clear();
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    }));
  }

  // ─── 预加载数据包 ───
  async function preloadPackage(dept = '内科') {
    try {
      const res = await fetch(`/api/offline/package?dept=${encodeURIComponent(dept)}`);
      if (!res.ok) throw new Error('预加载请求失败');

      const pkg = await res.json();
      if (!pkg.ok) throw new Error(pkg.msg || '数据包异常');

      // 存储模板
      await putAll(STORES.templates, (pkg.templates || []).map((t) => ({ ...t, dept })));

      // 存储患者
      await putAll(STORES.patients, pkg.patients || []);

      // 记录元数据
      await putAll(STORES.meta, [
        { key: 'last_preload', value: pkg.timestamp, dept },
        { key: 'preloaded_dept', value: dept },
      ]);

      console.log(`[Offline] 预加载完成: ${(pkg.templates || []).length} 模板, ${(pkg.patients || []).length} 患者`);
      return { ok: true, templates: (pkg.templates || []).length, patients: (pkg.patients || []).length };
    } catch (e) {
      console.error('[Offline] 预加载失败:', e);
      return { ok: false, error: e.message };
    }
  }

  // ─── 离线补录 ───
  async function addOfflineRecord(record) {
    const local_id = `local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const item = {
      local_id,
      content: record.content || '',
      department: record.department || '',
      created_at: new Date().toISOString(),
      synced: false,
    };
    await putAll(STORES.offlineRecords, [item]);
    return item;
  }

  // 获取未同步的离线记录
  function getUnsyncedRecords() {
    return getAll(STORES.offlineRecords).then((records) =>
      (records || []).filter((r) => !r.synced)
    );
  }

  // ─── 同步到服务器 ───
  async function syncOfflineRecords() {
    const records = await getUnsyncedRecords();
    if (!records.length) return { synced: 0, failed: 0 };

    try {
      const res = await fetch('/api/offline/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records }),
      });
      const result = await res.json();

      if (result.ok) {
        // 标记已同步
        const syncedIds = (result.synced || []).map((s) => s.local_id);
        for (const id of syncedIds) {
          await deleteItem(STORES.offlineRecords, id);
        }
        // 刷新患者列表（增量拉取）
        try {
          const pkg = await (await fetch('/api/offline/package?dept=' + encodeURIComponent(
            (await getMeta('preloaded_dept')) || '内科'
          ))).json();
          if (pkg.ok) await putAll(STORES.patients, pkg.patients || []);
        } catch (e) { /* 忽略刷新失败 */ }

        console.log(`[Offline] 同步完成: ${result.synced?.length || 0} 条`);
        return { synced: result.synced?.length || 0, failed: result.failed?.length || 0 };
      }
      return { synced: 0, failed: records.length, error: result.msg };
    } catch (e) {
      console.error('[Offline] 同步失败:', e);
      return { synced: 0, failed: records.length, error: e.message };
    }
  }

  // ─── 元数据 ───
  async function getMeta(key) {
    const items = await getAll(STORES.meta);
    const found = (items || []).find((m) => m.key === key);
    return found ? found.value : null;
  }

  // ─── 状态查询 ───
  async function getOfflineStats() {
    const [unsynced, templates, patients] = await Promise.all([
      getUnsyncedRecords(),
      getAll(STORES.templates),
      getAll(STORES.patients),
    ]);
    return {
      online: navigator.onLine,
      pendingCount: unsynced.length,
      cachedTemplates: templates.length,
      cachedPatients: patients.length,
    };
  }

  // ─── 对外 API ───
  global.XingyanOffline = {
    preloadPackage,
    addOfflineRecord,
    syncOfflineRecords,
    getOfflineStats,
    getMeta,
    getAll,
    getUnsyncedRecords,
    STORES,
  };
})(window);
