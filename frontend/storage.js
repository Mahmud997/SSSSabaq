// Этап 10: IndexedDB вместо localStorage для ключа рабочего пространства
const IDB_NAME = "ustaz_ai_pro_max";
const IDB_STORE = "secure";
const IDB_VER = 1;

function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VER);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error("IndexedDB недоступен"));
  });
}

async function idbGet(key) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readonly");
    const r = tx.objectStore(IDB_STORE).get(key);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

async function idbSet(key, value) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readwrite");
    tx.objectStore(IDB_STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbDel(key) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readwrite");
    tx.objectStore(IDB_STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/** Миграция: если ключ ещё в localStorage — перенести в IndexedDB и удалить из LS. */
async function loadWorkspaceCredentials() {
  try {
    let key = await idbGet("workspace_key");
    let id = await idbGet("workspace_id");
    const lsKey = localStorage.getItem("ustaz_workspace_key");
    const lsId = localStorage.getItem("ustaz_workspace_id");
    if (!key && lsKey) {
      key = lsKey;
      id = lsId || "";
      await idbSet("workspace_key", key);
      if (id) await idbSet("workspace_id", id);
      localStorage.removeItem("ustaz_workspace_key");
      localStorage.removeItem("ustaz_workspace_id");
    }
    return { key: key || "", workspaceId: id || "" };
  } catch (e) {
    // fallback localStorage
    return {
      key: localStorage.getItem("ustaz_workspace_key") || "",
      workspaceId: localStorage.getItem("ustaz_workspace_id") || "",
    };
  }
}

async function saveWorkspaceCredentials(key, workspaceId) {
  try {
    await idbSet("workspace_key", key);
    await idbSet("workspace_id", workspaceId || "");
    localStorage.removeItem("ustaz_workspace_key");
    localStorage.removeItem("ustaz_workspace_id");
  } catch (e) {
    localStorage.setItem("ustaz_workspace_key", key);
    if (workspaceId) localStorage.setItem("ustaz_workspace_id", workspaceId);
  }
}

async function clearWorkspaceCredentials() {
  try {
    await idbDel("workspace_key");
    await idbDel("workspace_id");
  } catch (_) {}
  localStorage.removeItem("ustaz_workspace_key");
  localStorage.removeItem("ustaz_workspace_id");
}

window.ustazStorage = {
  loadWorkspaceCredentials,
  saveWorkspaceCredentials,
  clearWorkspaceCredentials,
};
