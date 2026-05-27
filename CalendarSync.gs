/**
 * ============================================================
 * Google Apps Script — Bidirectional Calendar Availability Sync
 * ============================================================
 *
 * Mirrors busy time slots across three Google Calendar accounts
 * as "Occupato" blocking events.
 *
 * Anti-loop protection uses TWO complementary markers on every mirror:
 *   1. Description tag         : [SYNC_MIRROR]  ← primary gate
 *   2. Private extendedProperty: syncMirror="true"  ← secondary gate
 *
 * Any event carrying either marker is immediately skipped — it is
 * never treated as an original, never re-synced, never fanned out.
 *
 * Persistent state is stored via PropertiesService (one JSON blob).
 * All in-run mutations accumulate in memory; a single write flushes
 * them at the very end of syncCalendars().
 *
 * ── PREREQUISITES ─────────────────────────────────────────────
 *   1. Open the Apps Script editor.
 *   2. Go to Extensions → Apps Script → Services (+).
 *   3. Add "Google Calendar API" (advanced service, v3).
 *   4. The running account must have write access to all 3 calendars.
 *
 * ── FIRST-RUN ORDER ───────────────────────────────────────────
 *   1. Run setup()            – validates access, initialises map
 *   2. Run createTimeTrigger() – installs the recurring trigger
 *
 * After that, syncCalendars() runs automatically every 10 minutes.
 * ============================================================
 */

// ─── CONFIGURATION ────────────────────────────────────────────────────────────

const CONFIG = {
  /** The three calendar IDs to keep in sync (order is irrelevant). */
  CALENDARS: [
    'elvio@seoperstartup.it',
    'elvio.leonardi@intarget.net',
    'elvio@rankwit.ai',
  ],

  /** Fixed title for every mirror — never the original event title. */
  MIRROR_TITLE: 'Occupato',

  /**
   * Description tag embedded in every mirror.
   * PRIMARY anti-loop gate: any event whose description contains this
   * string is skipped entirely before any other logic runs.
   */
  MIRROR_TAG: '[SYNC_MIRROR]',

  /**
   * Private extendedProperty added to every mirror.
   * SECONDARY anti-loop gate: redundant protection against any
   * scenario where the description is accidentally cleared.
   */
  MIRROR_EXT_KEY: 'syncMirror',
  MIRROR_EXT_VAL: 'true',

  /** PropertiesService key for the persistent original→mirror JSON map. */
  MAP_KEY: 'SYNC_MAP',

  /** Sync window: events from now to now + N days. */
  SYNC_DAYS: 30,

  /** Default timezone used when the original event lacks one. */
  TIMEZONE: 'Europe/Rome',

  /** Name of the function the time-based trigger will call. */
  TRIGGER_FUNCTION: 'syncCalendars',

  /** Trigger interval in minutes (must be 1, 5, 10, 15, or 30). */
  TRIGGER_INTERVAL_MINUTES: 10,
};

// ─── MAIN ENTRY POINTS ────────────────────────────────────────────────────────

/**
 * Validates access to all three calendars and initialises the PropertiesService
 * sync map if it does not yet exist.
 *
 * Run ONCE manually after deploying the script.
 */
function setup() {
  Logger.log('=== setup() start ===');

  CONFIG.CALENDARS.forEach(calId => {
    try {
      const cal = Calendar.Calendars.get(calId);
      Logger.log(`[OK] Reachable: ${calId} (name: "${cal.summary}")`);
    } catch (e) {
      Logger.log(`[ERROR] Could not access calendar ${calId} — check sharing/delegation permissions. Detail: ${e.message}`);
    }
  });

  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty(CONFIG.MAP_KEY)) {
    props.setProperty(CONFIG.MAP_KEY, JSON.stringify({}));
    Logger.log('[MAP] SYNC_MAP initialised (empty).');
  } else {
    Logger.log('[MAP] SYNC_MAP already exists — left unchanged.');
  }

  Logger.log('=== setup() end ===');
}

/**
 * Main sync loop.
 *
 * For each of the 3 calendars:
 *   – Fetches events in the +30-day window.
 *   – Skips any event tagged as a mirror (both gates checked).
 *   – For each original event, creates or updates mirrors in the
 *     other two calendars.
 *
 * After the main scan, cleans up map entries whose originals have
 * been deleted or have moved into the past.
 *
 * All SYNC_MAP mutations accumulate in memory during the run.
 * A single PropertiesService.setProperty() call writes them at the end.
 */
function syncCalendars() {
  Logger.log('=== syncCalendars() start ===');

  const now       = new Date();
  const windowEnd = new Date(now.getTime() + CONFIG.SYNC_DAYS * 24 * 60 * 60 * 1000);

  // One PropertiesService read for the entire run
  const props   = PropertiesService.getScriptProperties();
  const syncMap = loadMap(props);  // plain JS object, mutated in place throughout

  // Mirror IDs touched in this run — prevents processing the same mirror twice
  // if it somehow appears in multiple iterations within one execution.
  const touchedThisRun = new Set();

  // Map keys of original events found alive in the current window.
  // Used by cleanupStaleEntries() to detect deleted originals.
  const foundOriginals = new Set();

  // ── MAIN SCAN ─────────────────────────────────────────────────────────────

  CONFIG.CALENDARS.forEach(sourceCalId => {
    Logger.log(`\n[SCAN] Calendar: ${sourceCalId}`);

    let originals;
    try {
      originals = fetchOriginalEvents(sourceCalId, now, windowEnd);
    } catch (e) {
      Logger.log(`[ERROR] Failed to fetch events from ${sourceCalId}: ${e.message}`);
      return; // skip this calendar, continue with the others
    }

    Logger.log(`[SCAN] ${originals.length} original event(s) to process in ${sourceCalId}`);

    originals.forEach(event => {
      const mapKey = buildMapKey(sourceCalId, event.id);
      foundOriginals.add(mapKey);

      // Fan out to the other two calendars
      CONFIG.CALENDARS
        .filter(id => id !== sourceCalId)
        .forEach(targetCalId => {
          try {
            upsertMirror(event, sourceCalId, targetCalId, syncMap, touchedThisRun);
          } catch (e) {
            Logger.log(`[ERROR] upsertMirror failed — original ${event.id} → ${targetCalId}: ${e.message}`);
          }
        });

      // Log the full map entry for this original after both targets are resolved
      if (syncMap[mapKey]) {
        Logger.log(`[MAP] Stored: ${mapKey} → ${JSON.stringify(syncMap[mapKey])}`);
      }
    });
  });

  // ── STALE ENTRY CLEANUP ───────────────────────────────────────────────────

  cleanupStaleEntries(syncMap, foundOriginals, now, windowEnd);

  // ── SINGLE FINAL MAP WRITE ────────────────────────────────────────────────
  // This is the ONLY PropertiesService write in the entire run.

  saveMap(props, syncMap);

  Logger.log('=== syncCalendars() end ===');
}

/**
 * Installs a recurring time-based trigger for syncCalendars().
 * No-ops if a trigger for that function already exists.
 * Safe to run multiple times.
 */
function createTimeTrigger() {
  const alreadyExists = ScriptApp.getProjectTriggers()
    .some(t => t.getHandlerFunction() === CONFIG.TRIGGER_FUNCTION);

  if (alreadyExists) {
    Logger.log(`[TRIGGER] Trigger for "${CONFIG.TRIGGER_FUNCTION}" already exists — no action taken.`);
    return;
  }

  ScriptApp.newTrigger(CONFIG.TRIGGER_FUNCTION)
    .timeBased()
    .everyMinutes(CONFIG.TRIGGER_INTERVAL_MINUTES)
    .create();

  Logger.log(`[TRIGGER] Created: ${CONFIG.TRIGGER_FUNCTION} every ${CONFIG.TRIGGER_INTERVAL_MINUTES} min.`);
}

/**
 * Removes ALL project triggers.
 * Safe to run multiple times.
 */
function removeTriggers() {
  const triggers = ScriptApp.getProjectTriggers();

  if (triggers.length === 0) {
    Logger.log('[TRIGGER] No triggers found — nothing to remove.');
    return;
  }

  triggers.forEach(t => {
    ScriptApp.deleteTrigger(t);
    Logger.log(`[TRIGGER] Removed trigger for: ${t.getHandlerFunction()}`);
  });
}

// ─── FETCH & FILTER ───────────────────────────────────────────────────────────

/**
 * Fetches all events from a calendar in [start, end], then filters down to
 * only original (non-mirror) busy events.
 *
 * Filtering rules (all three must pass):
 *   1. Description does NOT contain CONFIG.MIRROR_TAG      ← primary gate
 *   2. Private extendedProperty syncMirror is not "true"   ← secondary gate
 *   3. Transparency is not "transparent" (i.e., event is busy)
 *
 * Handles API pagination automatically.
 *
 * @param {string} calId
 * @param {Date}   start
 * @param {Date}   end
 * @returns {Array<Object>}  Calendar API event objects
 */
function fetchOriginalEvents(calId, start, end) {
  const items = [];
  let pageToken = null;

  do {
    const options = {
      timeMin:      start.toISOString(),
      timeMax:      end.toISOString(),
      singleEvents: true,   // expand recurring events into individual instances
      orderBy:      'startTime',
      showDeleted:  false,
      maxResults:   250,
    };
    if (pageToken) options.pageToken = pageToken;

    const response = Calendar.Events.list(calId, options);
    (response.items || []).forEach(e => items.push(e));
    pageToken = response.nextPageToken || null;
  } while (pageToken);

  return items.filter(event => {
    // ── Primary gate ─────────────────────────────────────────────────────────
    const desc = event.description || '';
    if (desc.includes(CONFIG.MIRROR_TAG)) {
      Logger.log(`[SKIP] Event id=${event.id} in ${calId} — [SYNC_MIRROR] tag in description`);
      return false;
    }

    // ── Secondary gate ────────────────────────────────────────────────────────
    const privateProps = ((event.extendedProperties || {}).private) || {};
    if (privateProps[CONFIG.MIRROR_EXT_KEY] === CONFIG.MIRROR_EXT_VAL) {
      Logger.log(`[SKIP] Event id=${event.id} in ${calId} — syncMirror extendedProperty present`);
      return false;
    }

    // ── Busy-only filter ──────────────────────────────────────────────────────
    // Absence of transparency defaults to 'opaque' (busy) per the Calendar API spec.
    if (event.transparency === 'transparent') {
      return false;
    }

    // ── Video call filter ─────────────────────────────────────────────────────
    // Only mirror events that have an active video call link (Meet, Zoom, Teams).
    // Work blocks, focus time, and other personal slots are intentionally excluded.
    if (!hasVideoCall(event)) {
      return false;
    }

    return true;
  });
}

// ─── UPSERT LOGIC ─────────────────────────────────────────────────────────────

/**
 * Creates or updates a mirror in targetCalId for the given original event.
 *
 * Decision tree:
 *   – No map entry              → create mirror, store ID in map
 *   – Map entry, mirror exists  → update mirror to match original's time slot
 *   – Map entry, mirror gone    → create replacement, update map ID
 *
 * All changes are applied to syncMap in memory only. No PropertiesService
 * write happens here.
 *
 * @param {Object} original       Calendar API event object (the original)
 * @param {string} sourceCalId
 * @param {string} targetCalId
 * @param {Object} syncMap        In-memory map (mutated in place)
 * @param {Set}    touchedThisRun IDs touched in this run
 */
function upsertMirror(original, sourceCalId, targetCalId, syncMap, touchedThisRun) {
  const mapKey = buildMapKey(sourceCalId, original.id);

  if (!syncMap[mapKey]) {
    syncMap[mapKey] = {};
  }

  const existingMirrorId = syncMap[mapKey][targetCalId];

  if (existingMirrorId) {
    // Intra-run guard: skip if we already processed this mirror ID
    if (touchedThisRun.has(existingMirrorId)) {
      return;
    }

    const updated = tryUpdateMirror(existingMirrorId, original, targetCalId);

    if (updated) {
      touchedThisRun.add(existingMirrorId);
      Logger.log(`[UPDATE] Mirror in ${targetCalId} for original ${original.id} → updated time slot`);
    } else {
      // Mirror was externally deleted — replace it
      const newId = createMirror(original, targetCalId);
      syncMap[mapKey][targetCalId] = newId;
      touchedThisRun.add(newId);
      Logger.log(`[CREATE] Mirror in ${targetCalId} for original ${original.id} → new mirrorId ${newId} (replaced stale ${existingMirrorId})`);
    }
  } else {
    // No existing mirror — create fresh
    const newId = createMirror(original, targetCalId);
    syncMap[mapKey][targetCalId] = newId;
    touchedThisRun.add(newId);
    Logger.log(`[CREATE] Mirror in ${targetCalId} for original ${original.id} → new mirrorId ${newId}`);
  }
}

/**
 * Inserts a new mirror event. Returns the created event ID.
 *
 * @param {Object} original
 * @param {string} targetCalId
 * @returns {string}
 */
function createMirror(original, targetCalId) {
  const created = Calendar.Events.insert(
    buildMirrorResource(original),
    targetCalId,
    { sendUpdates: 'none' }
  );
  return created.id;
}

/**
 * Attempts a full update of an existing mirror to match the original's time slot.
 * Returns true on success, false if the mirror no longer exists (404 / 410).
 * Re-throws unexpected errors so callers can log them.
 *
 * @param {string} mirrorId
 * @param {Object} original
 * @param {string} targetCalId
 * @returns {boolean}
 */
function tryUpdateMirror(mirrorId, original, targetCalId) {
  try {
    Calendar.Events.update(
      buildMirrorResource(original),
      targetCalId,
      mirrorId,
      { sendUpdates: 'none' }
    );
    return true;
  } catch (e) {
    const msg = e.message || '';
    if (msg.includes('404') || msg.includes('410') ||
        msg.includes('Not Found') || msg.includes('Gone')) {
      return false; // mirror was deleted externally — caller will replace it
    }
    throw e;
  }
}

/**
 * Deletes a mirror event. Tolerates 404 / 410 (mirror already gone).
 *
 * @param {string} mirrorId
 * @param {string} targetCalId
 * @param {string} originalId   Used only for log context — never logged as content
 */
function deleteMirror(mirrorId, targetCalId, originalId) {
  try {
    Calendar.Events.remove(targetCalId, mirrorId);
    Logger.log(`[DELETE] Mirror in ${targetCalId} removed — original eventId ${originalId} no longer exists`);
  } catch (e) {
    const msg = e.message || '';
    if (msg.includes('404') || msg.includes('410') ||
        msg.includes('Not Found') || msg.includes('Gone')) {
      Logger.log(`[DELETE] Mirror ${mirrorId} in ${targetCalId} was already gone — original ${originalId}`);
    } else {
      Logger.log(`[ERROR] Failed to delete mirror ${mirrorId} in ${targetCalId}: ${msg}`);
    }
  }
}

/**
 * Deletes all mirrors referenced in a single map entry, then logs each removal.
 *
 * @param {Object} mirrorEntry  e.g. { "calB@x.com": "id1", "calC@y.com": "id2" }
 * @param {string} originalId  For log context only
 */
function deleteAllMirrors(mirrorEntry, originalId) {
  Object.keys(mirrorEntry).forEach(targetCalId => {
    const mirrorId = mirrorEntry[targetCalId];
    if (mirrorId) {
      deleteMirror(mirrorId, targetCalId, originalId);
    }
  });
}

// ─── RESOURCE BUILDER ─────────────────────────────────────────────────────────

/**
 * Builds the Calendar API event resource for a mirror event.
 *
 * Copies ONLY the time slot (start, end, all-day flag).
 * Everything else is fixed: title = "Occupato", description = "[SYNC_MIRROR]",
 * transparency = "opaque", extendedProperties.private.syncMirror = "true".
 *
 * Intentionally omits: original title, attendees, location, conferencing data,
 * organiser, colour, reminders, recurrence rules, and any other metadata.
 *
 * @param {Object} original  Calendar API event object
 * @returns {Object}         Calendar API event resource ready for insert/update
 */
function buildMirrorResource(original) {
  const resource = {
    summary:      CONFIG.MIRROR_TITLE,
    description:  CONFIG.MIRROR_TAG,
    transparency: 'opaque',  // always blocks time; never "free"
    extendedProperties: {
      private: {
        [CONFIG.MIRROR_EXT_KEY]: CONFIG.MIRROR_EXT_VAL,
      },
    },
  };

  // All-day events use date strings; timed events use dateTime + timezone.
  if (original.start.date) {
    resource.start = { date: original.start.date };
    resource.end   = { date: original.end.date };
  } else {
    resource.start = {
      dateTime: original.start.dateTime,
      timeZone: original.start.timeZone || CONFIG.TIMEZONE,
    };
    resource.end = {
      dateTime: original.end.dateTime,
      timeZone: original.end.timeZone || CONFIG.TIMEZONE,
    };
  }

  return resource;
}

// ─── STALE ENTRY CLEANUP ─────────────────────────────────────────────────────

/**
 * Identifies SYNC_MAP entries whose originals are no longer present in the
 * current window and removes their mirrors.
 *
 * Three cases trigger cleanup:
 *   a) Original event not found by the Calendar API (deleted / access revoked)
 *   b) Original event status is "cancelled"
 *   c) Original event start is in the past (< windowStart) — mirrors no longer needed
 *
 * Events beyond windowEnd are intentionally left untouched; they will enter
 * the window in a future run.
 *
 * @param {Object} syncMap
 * @param {Set}    foundOriginals  Map keys seen alive during this run
 * @param {Date}   windowStart
 * @param {Date}   windowEnd
 */
function cleanupStaleEntries(syncMap, foundOriginals, windowStart, windowEnd) {
  const keysToDelete = [];

  Object.keys(syncMap).forEach(mapKey => {
    // If the original was found alive in this scan, nothing to clean up
    if (foundOriginals.has(mapKey)) return;

    const colonIdx = mapKey.indexOf(':');
    const calId    = mapKey.substring(0, colonIdx);
    const eventId  = mapKey.substring(colonIdx + 1);

    // Only process entries that belong to our managed calendars
    if (!CONFIG.CALENDARS.includes(calId)) return;

    // Attempt to fetch the original event directly from the API
    let original = null;
    try {
      original = Calendar.Events.get(calId, eventId);
    } catch (_) {
      // Any error (404, auth, etc.) means we treat the event as gone
      original = null;
    }

    // Case a & b: event is gone or cancelled
    if (!original || original.status === 'cancelled') {
      Logger.log(`[CLEANUP] Original ${eventId} in ${calId} is gone — removing mirrors`);
      deleteAllMirrors(syncMap[mapKey], eventId);
      keysToDelete.push(mapKey);
      return;
    }

    // Determine start as a Date for range comparisons
    const eventStart = original.start.dateTime
      ? new Date(original.start.dateTime)
      : new Date(original.start.date);

    // Event exists but is beyond the current window — leave it alone for now
    if (eventStart >= windowEnd) return;

    // Case c: event is now in the past — mirrors no longer serve a purpose
    if (eventStart < windowStart) {
      Logger.log(`[CLEANUP] Original ${eventId} in ${calId} is in the past — removing mirrors`);
      deleteAllMirrors(syncMap[mapKey], eventId);
      keysToDelete.push(mapKey);
    }
  });

  keysToDelete.forEach(key => delete syncMap[key]);

  if (keysToDelete.length > 0) {
    Logger.log(`[CLEANUP] Removed ${keysToDelete.length} stale map entry/entries.`);
  }
}

// ─── VIDEO CALL DETECTION ────────────────────────────────────────────────────

/**
 * Returns true if the event has a video call link from a supported provider:
 *   – Google Meet  : event.hangoutLink is present
 *   – Zoom         : a conferenceData entry point URI contains "zoom.us"
 *   – Microsoft Teams: a conferenceData entry point URI contains "teams.microsoft.com"
 *                      or "teams.live.com"
 *
 * Checking entry point URIs is more reliable than conferenceSolution.name,
 * which can vary by locale or third-party integration label.
 *
 * @param {Object} event  Calendar API event object
 * @returns {boolean}
 */
function hasVideoCall(event) {
  // Google Meet
  if (event.hangoutLink) return true;

  // Zoom or Teams via conferenceData entry points
  const entryPoints = ((event.conferenceData || {}).entryPoints) || [];
  return entryPoints.some(ep => {
    const uri = (ep.uri || '').toLowerCase();
    return uri.includes('zoom.us') ||
           uri.includes('teams.microsoft.com') ||
           uri.includes('teams.live.com');
  });
}

// ─── MAP HELPERS ─────────────────────────────────────────────────────────────

/**
 * Builds the unique map key for an original event: "calendarId:eventId".
 *
 * @param {string} calId
 * @param {string} eventId
 * @returns {string}
 */
function buildMapKey(calId, eventId) {
  return `${calId}:${eventId}`;
}

/**
 * Reads the SYNC_MAP JSON from PropertiesService into a plain JS object.
 * Returns {} if the property is missing or corrupt (and logs the error).
 *
 * @param {PropertiesService.Properties} props
 * @returns {Object}
 */
function loadMap(props) {
  const raw = props.getProperty(CONFIG.MAP_KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (e) {
    Logger.log(`[ERROR] SYNC_MAP is corrupt — resetting to empty. Detail: ${e.message}`);
    return {};
  }
}

/**
 * Serialises the in-memory SYNC_MAP back to PropertiesService.
 * Called exactly ONCE per syncCalendars() run — the single flush point.
 *
 * @param {PropertiesService.Properties} props
 * @param {Object} syncMap
 */
function saveMap(props, syncMap) {
  props.setProperty(CONFIG.MAP_KEY, JSON.stringify(syncMap));
  Logger.log(`[MAP] SYNC_MAP saved. Tracked originals: ${Object.keys(syncMap).length}`);
}
