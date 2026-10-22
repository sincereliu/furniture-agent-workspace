/** Layout HTTP synchronization. This module owns versions and response ordering, not DOM or geometry. */
export class LayoutWriteError extends Error {
  constructor(status, detail, expectedVersion) {
    super(`Layout write failed (${status})`);
    this.status = status;
    this.detail = detail;
    this.expectedVersion = expectedVersion;
  }
}

export function placementChanged(before, after) {
  if (before.mode !== after.mode || (before.host_wall || null) !== (after.host_wall || null)) return true;
  if (["origin_x_mm", "origin_y_mm", "origin_z_mm"].some(key => Math.round(before[key] || 0) !== Math.round(after[key] || 0))) return true;
  const angle = value => Math.round((((value || 0) % 360 + 360) % 360) * 10);
  return angle(before.rotation_z_deg) !== angle(after.rotation_z_deg);
}

/** One controller per page; every authoritative layout enters through accept(). */
export function createLayoutPersistence({
  readUrl, editUrl, version = "", versioned,
  getLeaseToken, isInteracting, onMetadata, onDocument, request = fetch,
}) {
  let currentVersion = String(version);
  let generation = 0;
  let readSequence = 0;
  let pendingWrites = 0;
  let writeTail = Promise.resolve();
  let deferredDocument = null;
  let dirty = false;
  let notificationRead = null;

  const busy = () => pendingWrites > 0 || isInteracting();

  function accept(payload) {
    if (payload.version !== undefined) currentVersion = String(payload.version);
    onMetadata(payload);
    if (!payload.rooms && !payload.items) return;
    // Own the snapshot: neither callers nor the renderer can mutate a deferred response.
    deferredDocument = structuredClone(payload);
    applyDeferred();
  }

  function applyDeferred() {
    if (busy() || !deferredDocument) return;
    const payload = deferredDocument;
    deferredDocument = null;
    onDocument(payload);
  }

  async function refresh() {
    const epoch = generation;
    const sequence = ++readSequence;
    try {
      const response = await request(readUrl, { cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) return false;
      const payload = await response.json();
      if (epoch !== generation || sequence !== readSequence) return false;
      accept(payload);
      dirty = false;
      return true;
    } catch {
      return false;
    }
  }

  async function write(operation, url = editUrl) {
    // Take the coordinates at submission, not when the queued request finally starts.
    const op = structuredClone(operation);
    const previous = writeTail;
    let release;
    writeTail = new Promise(resolve => { release = resolve; });
    pendingWrites += 1;
    generation += 1;
    await previous;
    try {
      const headers = { "Content-Type": "application/json" };
      const token = getLeaseToken();
      if (token) headers["X-Edit-Lease"] = token;
      if (versioned) op.expected_version = currentVersion;
      const response = await request(url, { method: "POST", cache: "no-store", headers, body: JSON.stringify(op) });
      if (!response.ok) throw new LayoutWriteError(response.status, await response.json().catch(() => ({})), op.expected_version);
      const payload = await response.json();
      generation += 1;
      accept(payload);
      return payload;
    } catch (error) {
      // Read the authoritative result even if a network error hid a successful write.
      generation += 1;
      await refresh();
      throw error;
    } finally {
      pendingWrites -= 1;
      release();
      flush();
    }
  }

  function notice(payload) {
    if (!payload || typeof payload !== "object") return;
    onMetadata(payload);
    if (payload.version === undefined) return;
    if (String(payload.version) === currentVersion) {
      dirty = false;
      return;
    }
    generation += 1;
    dirty = true;
    flush();
  }

  function flush() {
    if (busy()) return;
    applyDeferred();
    if (!dirty || notificationRead) return;
    const epoch = generation;
    notificationRead = refresh().finally(() => {
      notificationRead = null;
      // A notice arriving during the GET invalidates it; fetch the newer state once.
      if (dirty && generation !== epoch) flush();
    });
  }

  return {
    get version() { return currentVersion; },
    get busy() { return busy(); },
    write, refresh, notice, flush,
  };
}
