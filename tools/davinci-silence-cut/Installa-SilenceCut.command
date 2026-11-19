#!/bin/bash
# Installa SilenceCut per DaVinci Resolve (macOS). Doppio clic, oppure:  bash Installa-SilenceCut.command
set -e
FUSION="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion"
UTIL="$FUSION/Scripts/Utility"
SC="$FUSION/SilenceCut"
APP="$HOME/Applications/SilenceCut Analizza.app"
mkdir -p "$UTIL" "$SC/cache" "$HOME/Applications"

echo "== Installazione SilenceCut =="

cat > "$UTIL/SilenceCut.lua" <<'SC_EOF_LUA'
--[[
SilenceCut (versione Lua) — taglio automatico dei silenzi per DaVinci Resolve.
Non richiede Python: Lua è integrato in Resolve. Serve solo ffmpeg (brew install ffmpeg).
Se Resolve non permette agli script di avviare ffmpeg, l'audio si analizza da Terminale
con analizza.sh: lo script stampa in Console il comando esatto da incollare.

Installazione: copia questo file in
  ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
Uso: apri la timeline montata (opzionale: seleziona le clip da tagliare) ->
     Workspace > Scripts > SilenceCut.
Il parlato viene cercato su UNA traccia audio (es. il microfono) e il taglio viene
applicato a TUTTE le tracce nello stesso punto, così video e audio restano a sync.
Il risultato è una NUOVA timeline: quella originale non viene toccata.
Senza timeline aperta lavora sulle clip selezionate nel Media Pool.
]]

-- ---------------------------------------------------------------------------
-- IMPOSTAZIONI
-- noise_db: sotto questo volume è "silenzio" (più vicino a 0 = taglia di più)
-- min_silence: pausa minima (s) da tagliare
-- pad_before / pad_after: margine (s) lasciato prima/dopo ogni frase
-- merge_gap: frasi separate da meno di così (s) vengono unite
-- min_keep: scarta pezzi parlati più corti di così (s)
-- ---------------------------------------------------------------------------
local PRESET_ORDER = { "Normale", "Delicato", "Aggressivo" }
local PRESETS = {
  Normale    = { noise_db = -35, min_silence = 0.5, pad_before = 0.12, pad_after = 0.20, merge_gap = 0.30, min_keep = 0.25 },
  Delicato   = { noise_db = -40, min_silence = 0.8, pad_before = 0.20, pad_after = 0.30, merge_gap = 0.45, min_keep = 0.25 },
  Aggressivo = { noise_db = -30, min_silence = 0.3, pad_before = 0.06, pad_after = 0.10, merge_gap = 0.15, min_keep = 0.20 },
}
local DEFAULT_PRESET = "Normale"
local AUDIO_STREAM = 0        -- traccia audio da analizzare (0 = la prima)
-- Dove cercare il parlato in timeline:
--   "telefono"  = audio registrato insieme al video (di solito più pulito nelle pause)
--   "microfono" = file solo audio del microfono esterno
--   oppure il numero della traccia, es. 2 per A2
-- Si può cambiare al volo scrivendo in Console  SC_DETECT="microfono";  prima di dofile(...)
local DETECT_ON = "telefono"
local ASK_PRESET = true       -- mostra la finestrina di scelta del preset
local CLIP_COLORS = { "Orange", "Teal", "Yellow", "Violet", "Green", "Pink", "Blue", "Apricot" }
local FFMPEG_CANDIDATES = { "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg" }

-- ---------------------------------------------------------------------------

local function shq(s)
  return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

-- Esegue un comando di sistema e ne restituisce l'output.
-- Resolve a volte toglie la libreria "io" agli script: in quel caso uso LuaJIT FFI.
local run_cmd, RUN_METHOD

if io and io.popen then
  RUN_METHOD = "io.popen"
  run_cmd = function(cmd)
    local p = io.popen(cmd)
    if not p then return "" end
    local out = p:read("*a") or ""
    p:close()
    return out
  end
else
  local ok_ffi, ffi = pcall(function() return require("ffi") end)
  if not ok_ffi or type(ffi) ~= "table" then
    ok_ffi, ffi = pcall(function() return jit and package and package.loaded and package.loaded.ffi end)
  end
  if ok_ffi and type(ffi) == "table" then
    pcall(ffi.cdef, [[
      typedef struct SC_FILE SC_FILE;
      SC_FILE *popen(const char *command, const char *mode);
      int pclose(SC_FILE *stream);
      size_t fread(void *ptr, size_t size, size_t nmemb, SC_FILE *stream);
    ]])
    local ok_c = pcall(function() return ffi.C.popen end)
    if ok_c then
      RUN_METHOD = "ffi"
      run_cmd = function(cmd)
        local f = ffi.C.popen(cmd, "r")
        if f == nil then return "" end
        local buf, parts = ffi.new("char[?]", 8192), {}
        while true do
          local n = tonumber(ffi.C.fread(buf, 1, 8192, f))
          if n <= 0 then break end
          parts[#parts + 1] = ffi.string(buf, n)
        end
        ffi.C.pclose(f)
        return table.concat(parts)
      end
    end
  end
end

local function diagnostics()
  local function has(f) local ok, v = pcall(f) return ok and v ~= nil and "si" or "no" end
  return "io=" .. has(function() return io end) ..
    " os.execute=" .. has(function() return os.execute end) ..
    " require=" .. has(function() return require end) ..
    " jit=" .. has(function() return jit end) ..
    " bmd.executebg=" .. has(function() return bmd.executebg end) ..
    " bmd.readfile=" .. has(function() return bmd.readfile end)
end

local function exec(cmd)
  if not run_cmd then return "" end
  return run_cmd(cmd .. " 2>&1")
end

local function file_exists(path)
  return exec("test -x " .. shq(path) .. " && echo SI"):find("SI") ~= nil
end

local function find_ffmpeg()
  for _, p in ipairs(FFMPEG_CANDIDATES) do
    if file_exists(p) then return p end
  end
  local w = exec("command -v ffmpeg"):gsub("%s+$", "")
  if w ~= "" and file_exists(w) then return w end
  return nil
end

local function applescript_str(s)
  return '"' .. tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function alert(msg)
  print(msg)
  exec("osascript -e 'tell me to activate' -e " .. shq('display dialog ' .. applescript_str(msg) ..
    ' with title "SilenceCut" buttons {"OK"} default button "OK"'))
end

local function clean(s)
  return (tostring(s or ""):gsub('["\\]', ""))
end

-- Finestra di scelta da lista (macOS). Restituisce la voce scelta, nil se annullato.
local function choose_from_list(prompt, options, default)
  if not run_cmd then return default end   -- niente finestre: usa il predefinito
  local items = {}
  for i, o in ipairs(options) do items[i] = '"' .. clean(o) .. '"' end
  local script = 'choose from list {' .. table.concat(items, ", ") .. '} with title "SilenceCut" with prompt "' ..
    clean(prompt) .. '" default items {"' .. clean(default) .. '"}'
  print("SilenceCut: rispondi alla finestra (se non la vedi, usa Cmd+Tab)")
  local out = exec("osascript -e 'tell me to activate' -e " .. shq(script)):gsub("%s+$", "")
  if out == "false" then return nil end
  for _, o in ipairs(options) do if clean(o) == out then return o end end
  return default   -- osascript non disponibile: usa il predefinito
end

local function choose_preset()
  local forced = SC_PRESET
  if forced and PRESETS[forced] then return forced end
  if not ASK_PRESET or not run_cmd then return DEFAULT_PRESET end
  return choose_from_list("Quanto tagliare i silenzi?", PRESET_ORDER, DEFAULT_PRESET)
end

local function fmt_time(sec)
  sec = math.floor(sec + 0.5)
  return string.format("%d:%02d", math.floor(sec / 60), sec % 60)
end

-- Analizza l'audio con ffmpeg e restituisce silenzi + durata
local function detect_silences(ffmpeg, path, p, from_sec, len_sec)
  local range = ""
  if from_sec and len_sec then
    range = string.format(" -ss %.4f -t %.4f", from_sec, len_sec)
  end
  local cmd = shq(ffmpeg) .. " -hide_banner -nostats" .. range .. " -i " .. shq(path) ..
    " -map 0:a:" .. AUDIO_STREAM ..
    " -af " .. shq(string.format("silencedetect=noise=%sdB:d=%s", p.noise_db, p.min_silence)) ..
    " -f null -"
  local out = exec(cmd)
  local duration
  local h, m, s = out:match("Duration:%s*(%d+):(%d+):([%d%.]+)")
  if h then duration = tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s) end
  if len_sec then duration = len_sec end

  local silences, start = {}, nil
  local found_any = false
  for line in out:gmatch("[^\r\n]+") do
    local ss = line:match("silence_start:%s*(%-?[%d%.]+)")
    if ss then
      start = math.max(0, tonumber(ss)); found_any = true
    else
      local se = line:match("silence_end:%s*([%d%.]+)")
      if se and start then
        silences[#silences + 1] = { start, tonumber(se) }
        start = nil
      end
    end
  end
  if start and duration then silences[#silences + 1] = { start, duration } end

  if not duration and not found_any then
    local tail = out:sub(-300)
    error("ffmpeg non riesce a leggere l'audio di " .. path .. "\n" .. tail, 0)
  end
  return silences, duration
end

-- ---------------------------------------------------------------------------
-- Analisi fatta da Terminale (quando Resolve non permette di avviare ffmpeg)
-- ---------------------------------------------------------------------------
local HOME = (os and os.getenv and os.getenv("HOME")) or ""
local SC_DIR = HOME .. "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut"
local DATA_PATH = SC_DIR .. "/analisi.lua"
local ANALYZER = SC_DIR .. "/analizza.sh"

local ANALYSIS = nil
local function analysis_data()
  if ANALYSIS == nil then
    local ok, d = pcall(dofile, DATA_PATH)
    ANALYSIS = (ok and type(d) == "table") and d or {}
  end
  return ANALYSIS
end

-- Nome del file di analisi di un media: stessa regola di analizza.sh
local function cache_file(path)
  local n = tostring(path):gsub("[^A-Za-z0-9%._%-]+", "_")
  if #n > 200 then n = n:sub(-200) end
  return SC_DIR .. "/cache/" .. n .. ".lua"
end

local ENTRIES = {}
local function entry_for(path)
  if ENTRIES[path] == nil then
    local ok, d = pcall(dofile, cache_file(path))
    if ok and type(d) == "table" then
      ENTRIES[path] = d
    else
      ENTRIES[path] = analysis_data()[path] or false   -- vecchio formato (analisi.lua)
    end
  end
  return ENTRIES[path] or nil
end

-- Silenzi già calcolati per un file, ritagliati sull'intervallo usato in timeline
local function silences_from_analysis(path, p, from_sec, len_sec)
  local entry = entry_for(path)
  if not entry then return nil end
  local list, best = nil, math.huge
  for k, v in pairs(entry) do
    if type(k) == "number" and math.abs(k - p.noise_db) < best then best = math.abs(k - p.noise_db); list = v end
  end
  list = list or {}
  from_sec = from_sec or 0
  len_sec = len_sec or entry.duration or 0
  local to, out = from_sec + len_sec, {}
  for _, sl in ipairs(list) do
    if sl[2] - sl[1] >= p.min_silence then
      local a, b = math.max(sl[1], from_sec), math.min(sl[2], to)
      if b > a then out[#out + 1] = { a - from_sec, b - from_sec } end
    end
  end
  return out, len_sec
end

-- Silenzi di un file: con ffmpeg se possibile, altrimenti dall'analisi da Terminale
local FFMPEG = nil
local function get_silences(path, p, from_sec, len_sec)
  if run_cmd and FFMPEG then
    return detect_silences(FFMPEG, path, p, from_sec, len_sec)
  end
  local sil, dur = silences_from_analysis(path, p, from_sec, len_sec)
  if not sil then error("NON_ANALIZZATO", 0) end
  return sil, dur
end

local MARKER_TAG = "SilenceCut"

local function print_analyzer_command(paths, tl)
  local quoted, names = {}, {}
  for i, pth in ipairs(paths) do
    quoted[i] = shq(pth)
    names[i] = pth:match("([^/]+)$") or pth
  end
  print("")
  print("SilenceCut: >>> Questi file non sono ancora stati analizzati:")
  for _, n in ipairs(names) do print("     " .. n) end
  print("SilenceCut: >>> Trascina la loro cartella sull'app 'SilenceCut Analizza' (nel Dock),")
  print("SilenceCut: >>> oppure incolla nel Terminale questa riga:")
  print("")
  print("bash " .. shq(ANALYZER) .. " " .. table.concat(quoted, " "))
  print("")
  print("SilenceCut: >>> Poi rilancia SilenceCut.")
  -- Promemoria visibile in timeline (lo script non può aprire finestre)
  if tl then
    pcall(function() tl:DeleteMarkerByCustomData(MARKER_TAG) end)
    local note = "Analizza prima l'audio: trascina la cartella del girato sull'app SilenceCut Analizza, poi rilancia SilenceCut. File: " ..
      table.concat(names, ", ")
    for f = 0, 50 do
      local ok, added = pcall(function()
        return tl:AddMarker(f, "Red", "SilenceCut: manca l'analisi", note, 1, MARKER_TAG)
      end)
      if ok and added then break end
    end
  end
end

-- Dai silenzi ai pezzi parlati, con margini e unioni
local function speech_segments(silences, duration, p)
  local segs, cursor = {}, 0
  for _, sil in ipairs(silences) do
    if sil[1] > cursor then segs[#segs + 1] = { cursor, sil[1] } end
    cursor = math.max(cursor, sil[2])
  end
  if duration and cursor < duration then segs[#segs + 1] = { cursor, duration } end

  local padded = {}
  for _, sg in ipairs(segs) do
    local s = math.max(0, sg[1] - p.pad_before)
    local e = sg[2] + p.pad_after
    if duration then e = math.min(duration, e) end
    local last = padded[#padded]
    if last and s - last[2] <= p.merge_gap then
      last[2] = math.max(last[2], e)
    else
      padded[#padded + 1] = { s, e }
    end
  end

  local result = {}
  for _, sg in ipairs(padded) do
    if sg[2] - sg[1] >= p.min_keep then result[#result + 1] = sg end
  end
  return result
end

-- Trasforma una risposta di Resolve in un elenco di oggetti.
-- Resolve a volte mette nella tabella anche numeri (contatori) o usa gli oggetti
-- come chiavi: tengo solo gli oggetti veri, nell'ordine dei numeri se c'è.
local function is_obj(x)
  local t = type(x)
  return t == "userdata" or t == "table"
end

local function to_list(t)
  local l, seen = {}, {}
  if not is_obj(t) then return l end
  local function add(o) if not seen[o] then seen[o] = true; l[#l + 1] = o end end
  local keys = {}
  for k in pairs(t) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b)
    local na, nb = type(a) == "number", type(b) == "number"
    if na and nb then return a < b end
    return na and not nb
  end)
  for _, k in ipairs(keys) do
    local v = t[k]
    if is_obj(v) then add(v) elseif is_obj(k) then add(k) end
  end
  return l
end

local function clip_fps(clip, project)
  for _, v in ipairs({ clip:GetClipProperty("FPS"), project:GetSetting("timelineFrameRate") }) do
    local f = tonumber(tostring(v or ""):match("[%d%.]+"))
    if f and f > 0 then return f end
  end
  return 25
end

local function round(x) return math.floor(x + 0.5) end

-- ---------------------------------------------------------------------------


local function clip_is_audio_only(mpi)
  local t = tostring(mpi:GetClipProperty("Type") or "")
  return t ~= "" and not t:lower():find("video")
end

-- ---------------------------------------------------------------------------
-- Modalità TIMELINE: taglio in sync su tutte le tracce
-- ---------------------------------------------------------------------------

local function collect_timeline_items(tl)
  local all, by_id = {}, {}
  for _, kind in ipairs({ "video", "audio" }) do
    local n = tl:GetTrackCount(kind) or 0
    for t = 1, n do
      for _, it in ipairs(to_list(tl:GetItemListInTrack(kind, t))) do
        local mpi = it:GetMediaPoolItem()
        local enabled = true
        pcall(function() enabled = it:GetClipEnabled() ~= false end)
        local path = mpi and mpi:GetClipProperty("File Path") or ""
        if mpi and path ~= "" and enabled then
          local rec = { item = it, kind = kind, track = t, mpi = mpi, path = path,
                        start = it:GetStart(), dur = it:GetDuration(), left = it:GetLeftOffset() or 0,
                        name = it:GetName() or mpi:GetName() }
          rec.finish = rec.start + rec.dur
          all[#all + 1] = rec
          local okid, id = pcall(function() return it:GetUniqueId() end)
          if okid and id then by_id[id] = rec end
        end
      end
    end
  end
  return all, by_id
end

-- Clip selezionate in timeline (Resolve 21.0.4+). nil se la funzione non esiste.
local function selected_items(tl, by_id)
  local ok, sel = pcall(function() return tl:GetSelectedClips() end)
  if not ok or type(sel) ~= "table" then return nil end
  local out, seen = {}, {}
  for _, it in pairs(sel) do
    local okid, id = pcall(function() return it:GetUniqueId() end)
    if okid and id and by_id[id] and not seen[id] then
      seen[id] = true
      out[#out + 1] = by_id[id]
    end
  end
  return out
end

-- Unione di intervalli [a, b) ordinati
local function merge_ranges(r)
  table.sort(r, function(x, y) return x[1] < y[1] end)
  local out = {}
  for _, x in ipairs(r) do
    local last = out[#out]
    if last and x[1] <= last[2] then last[2] = math.max(last[2], x[2]) else out[#out + 1] = { x[1], x[2] } end
  end
  return out
end

local function run_timeline(res, project, mp, tl)
  local tl_fps = tonumber(tostring(project:GetSetting("timelineFrameRate") or ""):match("[%d%.]+")) or 25
  local all, by_id = collect_timeline_items(tl)
  local items = selected_items(tl, by_id)
  local scope
  if items and #items > 0 then
    scope = "clip selezionate (" .. #items .. ")"
  else
    items, scope = all, "tutta la timeline"
  end
  print("SilenceCut: timeline '" .. tl:GetName() .. "', lavoro su " .. scope)
  if #items == 0 then return false end

  -- Tracce audio disponibili per rilevare il parlato
  local audio_tracks, labels, default_label = {}, {}, nil
  for _, r in ipairs(items) do
    if r.kind == "audio" and not audio_tracks[r.track] then audio_tracks[r.track] = r end
  end
  local idxs = {}
  for t in pairs(audio_tracks) do idxs[#idxs + 1] = t end
  table.sort(idxs)
  if #idxs == 0 then return alert("Nelle clip scelte non c'è nessuna traccia audio da analizzare.") end
  for _, t in ipairs(idxs) do
    local r = audio_tracks[t]
    local name = ""
    pcall(function() name = tl:GetTrackName("audio", t) or "" end)
    local label = "A" .. t .. " - " .. r.name .. ((name ~= "" and name ~= ("Audio " .. t)) and (" (" .. name .. ")") or "")
    labels[#labels + 1] = label
    r.label = label
  end
  -- traccia predefinita secondo DETECT_ON (o SC_DETECT dalla Console)
  local want = SC_DETECT or DETECT_ON
  local want_n = tonumber(want)
  for i, t in ipairs(idxs) do
    local only_audio = clip_is_audio_only(audio_tracks[t].mpi)
    if not default_label and (
        (want_n and t == want_n) or
        (want == "microfono" and only_audio) or
        (want == "telefono" and not only_audio)) then
      default_label = labels[i]
    end
  end
  default_label = default_label or labels[1]
  local det_track = idxs[1]
  for i, l in ipairs(labels) do if l == default_label then det_track = idxs[i] end end
  if #labels > 1 then
    local choice = choose_from_list("Su quale traccia audio cerco il parlato?", labels, default_label)
    if not choice then return true end
    for i, l in ipairs(labels) do if l == choice then det_track = idxs[i] end end
  else
    det_track = idxs[1]
  end
  print("SilenceCut: rilevo il parlato sulla traccia A" .. det_track)

  local preset_name = choose_preset()
  if not preset_name then return true end
  local p = PRESETS[preset_name]
  print("SilenceCut — preset " .. preset_name)

  -- Senza ffmpeg: controlla che i file della traccia scelta siano già stati analizzati
  if not (run_cmd and FFMPEG) then
    local missing, seen = {}, {}
    for _, r in ipairs(items) do
      if r.kind == "audio" and r.track == det_track and not seen[r.path] then
        seen[r.path] = true
        if not entry_for(r.path) then missing[#missing + 1] = r.path end
      end
    end
    if #missing > 0 then print_analyzer_command(missing, tl); return true end
    print("SilenceCut: uso l'analisi fatta da Terminale")
  end

  -- Tratti da togliere (in fotogrammi di timeline) = silenzi sulla traccia scelta
  local cuts, errors = {}, {}
  for _, r in ipairs(items) do
    if r.kind == "audio" and r.track == det_track then
      print("SilenceCut: analizzo " .. r.name .. " ...")
      local len_sec = r.dur / tl_fps
      local okc, silences, duration = pcall(get_silences, r.path, p, r.left / tl_fps, len_sec)
      if not okc then
        errors[#errors + 1] = tostring(silences)
      else
        local segs = speech_segments(silences, len_sec, p)
        local cursor = r.start
        for _, sg in ipairs(segs) do
          local a = r.start + round(sg[1] * tl_fps)
          if a > cursor then cuts[#cuts + 1] = { cursor, a } end
          cursor = math.max(cursor, r.start + round(sg[2] * tl_fps))
        end
        if cursor < r.finish then cuts[#cuts + 1] = { cursor, r.finish } end
      end
    end
  end
  cuts = merge_ranges(cuts)

  -- Tratti da tenere = intervallo totale meno i silenzi
  local span_a, span_b = math.huge, -math.huge
  for _, r in ipairs(items) do span_a = math.min(span_a, r.start); span_b = math.max(span_b, r.finish) end
  local keep, cursor = {}, span_a
  for _, c in ipairs(cuts) do
    if c[1] > cursor then keep[#keep + 1] = { cursor, c[1] } end
    cursor = math.max(cursor, c[2])
  end
  if cursor < span_b then keep[#keep + 1] = { cursor, span_b } end
  if #keep == 0 then return alert("Nessun parlato trovato.\n" .. table.concat(errors, "\n")) end

  -- Nuova timeline con le stesse tracce
  local tl_name = tl:GetName() .. " - SilenceCut " .. os.date("%H.%M.%S")
  local new_tl = mp:CreateEmptyTimeline(tl_name)
  if not new_tl then return alert("Impossibile creare la timeline.") end
  project:SetCurrentTimeline(new_tl)
  local need = { video = 0, audio = 0 }
  for _, r in ipairs(items) do need[r.kind] = math.max(need[r.kind], r.track) end
  for _, kind in ipairs({ "video", "audio" }) do
    for t = (new_tl:GetTrackCount(kind) or 0) + 1, need[kind] do
      if kind == "audio" then
        local sub = "stereo"
        pcall(function() sub = tl:GetTrackSubType("audio", t) or "stereo" end)
        if not new_tl:AddTrack("audio", sub) then new_tl:AddTrack("audio", "stereo") end
      else
        new_tl:AddTrack("video")
      end
    end
  end
  local new_start = new_tl:GetStartFrame() or 0

  -- Ogni pezzo di ogni traccia, rimontato in sequenza
  local infos = {}
  local pos = new_start
  for k, kr in ipairs(keep) do
    for _, r in ipairs(items) do
      local a, b = math.max(kr[1], r.start), math.min(kr[2], r.finish)
      if b > a then
        infos[#infos + 1] = {
          mediaPoolItem = r.mpi,
          startFrame = r.left + (a - r.start),
          endFrame = r.left + (b - r.start),              -- escluso (Resolve non conta l'ultimo)
          mediaType = (r.kind == "video") and 1 or 2,
          trackIndex = r.track,
          recordFrame = pos + (a - kr[1]),
        }
      end
    end
    pos = pos + (kr[2] - kr[1])
  end
  pcall(function() tl:DeleteMarkerByCustomData(MARKER_TAG) end)
  local appended = to_list(mp:AppendToTimeline(infos))
  print("SilenceCut: elementi aggiunti = " .. #appended .. " su " .. #infos)

  -- Ricollega video e audio di ogni pezzo, così si spostano insieme.
  -- Raggruppo per posizione in timeline (Resolve non restituisce i pezzi in ordine).
  local ranges = {}
  local p0 = new_start
  for k, kr in ipairs(keep) do
    ranges[k] = { p0, p0 + (kr[2] - kr[1]) }
    p0 = ranges[k][2]
  end
  local chunks = {}
  for _, it in ipairs(appended) do
    local okp, st = pcall(function() return it:GetStart() end)
    if okp and type(st) == "number" then
      for k, rg in ipairs(ranges) do
        if st >= rg[1] and st < rg[2] then
          chunks[k] = chunks[k] or {}
          table.insert(chunks[k], it)
          break
        end
      end
    end
  end
  for _, list in pairs(chunks) do
    if #list > 1 and #list <= 6 then pcall(function() new_tl:SetClipsLinked(list, true) end) end
  end
  pcall(function() res:OpenPage("edit") end)

  local before, after = (span_b - span_a) / tl_fps, (pos - new_start) / tl_fps
  local msg = string.format("Timeline creata: %s\n%d pezzi — da %s a %s (preset %s, parlato cercato su A%d).\nLa timeline originale non è stata modificata.",
    tl_name, #keep, fmt_time(before), fmt_time(after), preset_name, det_track)
  if #appended < #infos then
    msg = msg .. string.format("\n\nAttenzione: inseriti %d elementi su %d.", #appended, #infos)
  end
  if #errors > 0 then msg = msg .. "\n\nAttenzione:\n" .. table.concat(errors, "\n") end
  alert(msg)
  return true
end

-- ---------------------------------------------------------------------------
-- Modalità MEDIA POOL: clip intere selezionate (nessuna timeline aperta)
-- ---------------------------------------------------------------------------

local function run_media_pool(res, project, mp)
  local clips = {}
  local ok, sel = pcall(function() return mp:GetSelectedClips() end)
  if ok then clips = to_list(sel) end
  if #clips == 0 then clips = to_list(mp:GetCurrentFolder():GetClipList()) end
  local valid = {}
  for _, c in ipairs(clips) do
    local fp = c:GetClipProperty("File Path")
    if fp and fp ~= "" then valid[#valid + 1] = c end
  end
  clips = valid
  print("SilenceCut: Media Pool, clip = " .. #clips)
  if #clips == 0 then
    return alert("Apri la timeline da tagliare, oppure seleziona delle clip nel Media Pool, e rilancia lo script.")
  end

  if not (run_cmd and FFMPEG) then
    local missing = {}
    for _, c in ipairs(clips) do
      local pth = c:GetClipProperty("File Path")
      if not entry_for(pth) then missing[#missing + 1] = pth end
    end
    if #missing > 0 then return print_analyzer_command(missing) end
  end

  local preset_name = choose_preset()
  if not preset_name then return end
  local p = PRESETS[preset_name]

  local infos, errors, before, after = {}, {}, 0, 0
  for _, clip in ipairs(clips) do
    local path = clip:GetClipProperty("File Path")
    print("SilenceCut: analizzo " .. clip:GetName() .. " ...")
    local okc, silences, duration = pcall(get_silences, path, p)
    if not okc then
      errors[#errors + 1] = tostring(silences)
    else
      local fps = clip_fps(clip, project)
      local frames = tonumber(clip:GetClipProperty("Frames") or "")
      if frames and frames > 0 then duration = frames / fps end
      for _, sg in ipairs(speech_segments(silences, duration, p)) do
        local sf, ef = round(sg[1] * fps), round(sg[2] * fps)   -- ef escluso
        if ef > sf then
          infos[#infos + 1] = { mediaPoolItem = clip, startFrame = sf, endFrame = ef }
          after = after + (sg[2] - sg[1])
        end
      end
      before = before + (duration or 0)
    end
  end
  if #infos == 0 then return alert("Nessun parlato trovato.\n" .. table.concat(errors, "\n")) end

  local base = (#clips == 1) and clips[1]:GetName() or (#clips .. " clip")
  local tl_name = base .. " - SilenceCut " .. os.date("%H.%M.%S")
  local timeline = mp:CreateEmptyTimeline(tl_name)
  if not timeline then return alert("Impossibile creare la timeline.") end
  project:SetCurrentTimeline(timeline)
  mp:AppendToTimeline(infos)
  pcall(function() res:OpenPage("edit") end)
  local msg = string.format("Timeline creata: %s\n%d pezzi — da %s a %s (preset %s).",
    tl_name, #infos, fmt_time(before), fmt_time(after), preset_name)
  if #errors > 0 then msg = msg .. "\n\nAttenzione:\n" .. table.concat(errors, "\n") end
  alert(msg)
end

-- ---------------------------------------------------------------------------

local function main()
  print("SilenceCut: avvio")
  local res = resolve or (Resolve and Resolve()) or (app and app:GetResolve())
  if not res then return alert("Impossibile collegarsi a DaVinci Resolve.") end
  local project = res:GetProjectManager():GetCurrentProject()
  if not project then return alert("Apri prima un progetto in DaVinci Resolve.") end
  local mp = project:GetMediaPool()

  if run_cmd then
    FFMPEG = find_ffmpeg()
    if not FFMPEG then return alert("ffmpeg non trovato. Installalo dal Terminale con:  brew install ffmpeg") end
    print("SilenceCut: ffmpeg = " .. FFMPEG .. " (" .. RUN_METHOD .. ")")
  else
    print("SilenceCut: Resolve non permette di avviare ffmpeg, uso l'analisi da Terminale")
  end

  local tl = project:GetCurrentTimeline()
  if tl and run_timeline(res, project, mp, tl) ~= false then return end
  run_media_pool(res, project, mp)
end

local ok, err = pcall(main)
SC_PRESET = nil
SC_DETECT = nil
if not ok then
  print("SilenceCut ERRORE: " .. tostring(err))
  pcall(alert, "Errore: " .. tostring(err))
end
SC_EOF_LUA

cat > "$UTIL/SilenceCut Aggressivo.lua" <<'SC_EOF_W1'
SC_PRESET = "Aggressivo"
dofile(os.getenv("HOME") .. "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/SilenceCut.lua")
SC_EOF_W1

cat > "$UTIL/SilenceCut Delicato.lua" <<'SC_EOF_W2'
SC_PRESET = "Delicato"
dofile(os.getenv("HOME") .. "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/SilenceCut.lua")
SC_EOF_W2

cat > "$SC/analizza.sh" <<'SC_EOF_SH'
#!/bin/bash
# SilenceCut — analisi dei silenzi da Terminale (o dall'app "SilenceCut Analizza").
# Serve perché DaVinci Resolve non permette agli script di avviare ffmpeg.
#
# Uso: bash analizza.sh [-f] file-o-cartella [altri ...]
#   Le cartelle vengono esplorate (anche le sottocartelle) cercando file audio/video.
#   I file già analizzati vengono saltati; -f li rianalizza.
# Il risultato viene letto dallo script SilenceCut dentro Resolve.

SC_DIR="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut"
CACHE="$SC_DIR/cache"
THRESHOLDS="-30 -35 -40"   # soglie in dB usate dai preset
MIN_SILENCE=0.3            # pausa più corta registrata (s)
EXTENSIONS="mp4 mov m4v mxf mts m2ts avi mkv wav aif aiff mp3 m4a aac flac caf"

FORCE=0
if [ "$1" = "-f" ]; then FORCE=1; shift; fi

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
if [ -z "$FF" ]; then
  echo "ffmpeg non trovato. Installalo con:  brew install ffmpeg"
  exit 1
fi
if [ $# -eq 0 ]; then
  echo "Uso: bash analizza.sh file-o-cartella [...]"
  exit 1
fi
mkdir -p "$CACHE"

# Nome del file di analisi: stessa regola usata dallo script in Resolve
cache_name() {
  local s
  s=$(printf '%s' "$1" | LC_ALL=C sed 's/[^A-Za-z0-9._-][^A-Za-z0-9._-]*/_/g')
  if [ ${#s} -gt 200 ]; then s=${s: -200}; fi
  printf '%s/%s.lua' "$CACHE" "$s"
}

is_media() {
  local ext
  ext=$(printf '%s' "${1##*.}" | tr '[:upper:]' '[:lower:]')
  case " $EXTENSIONS " in *" $ext "*) return 0 ;; esac
  return 1
}

analyze() {
  local f="$1" out tmp db log
  out=$(cache_name "$f")
  if [ $FORCE -eq 0 ] && [ -f "$out" ] && [ "$out" -nt "$f" ]; then
    SKIPPED=$((SKIPPED + 1))
    return
  fi
  echo "Analizzo: $(basename "$f")"
  tmp="$out.tmp"
  printf 'return {\n  path = [==[%s]==],\n' "$f" > "$tmp"
  for db in $THRESHOLDS; do
    log=$("$FF" -nostdin -hide_banner -nostats -i "$f" -map 0:a:0 \
      -af "silencedetect=noise=${db}dB:d=${MIN_SILENCE}" -f null - 2>&1)
    if printf '%s' "$log" | grep -q "matches no streams"; then
      echo "   (nessun audio, salto)"
      rm -f "$tmp"
      NOAUDIO=$((NOAUDIO + 1))
      return
    fi
    printf '%s\n' "$log" | awk -v db="$db" '
      /Duration:/ && dur == "" {
        split($2, t, ":"); gsub(",", "", t[3]); dur = t[1] * 3600 + t[2] * 60 + t[3]
      }
      /silence_start:/ { s = $NF; if (s < 0) s = 0; open = 1 }
      /silence_end:/ {
        for (i = 1; i <= NF; i++) if ($i == "silence_end:") e = $(i + 1)
        if (open) { list = list sprintf("{%s,%s},", s, e); open = 0 }
      }
      END {
        if (open && dur != "") list = list sprintf("{%s,%s},", s, dur)
        printf "  [%s] = { %s },\n", db, list
        if (db == -35 && dur != "") printf "  duration = %s,\n", dur
      }' >> "$tmp"
  done
  echo "}" >> "$tmp"
  mv "$tmp" "$out"
  DONE=$((DONE + 1))
}

DONE=0; SKIPPED=0; NOAUDIO=0
for arg in "$@"; do
  [ "$arg" != "/" ] && arg="${arg%/}"
  if [ -d "$arg" ]; then
    while IFS= read -r f; do
      f=$(printf '%s' "$f" | sed 's#//*#/#g')
      is_media "$f" && analyze "$f"
    done < <(find "$arg" -type f ! -name '._*' 2>/dev/null | sort)
  elif [ -f "$arg" ]; then
    analyze "$arg"
  else
    echo "!! Non trovato: $arg"
  fi
done

echo
echo "Fatto: $DONE file analizzati, $SKIPPED già pronti, $NOAUDIO senza audio."
SC_EOF_SH
chmod +x "$SC/analizza.sh"
echo "OK  Script per Resolve installati (menu Workspace > Scripts)"

if command -v osacompile >/dev/null 2>&1; then
  rm -rf "$APP"
  osacompile -o "$APP" <<'SC_EOF_AS'
on open theItems
	set analyzer to (POSIX path of (path to home folder)) & "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut/analizza.sh"
	set args to ""
	repeat with anItem in theItems
		set args to args & " " & quoted form of (POSIX path of anItem)
	end repeat
	display notification "Analisi dell'audio in corso..." with title "SilenceCut"
	try
		set out to do shell script "/bin/bash " & quoted form of analyzer & args
		display dialog (last paragraph of out) & return & return & "Ora in DaVinci Resolve: Workspace > Scripts > SilenceCut" buttons {"OK"} default button "OK" with title "SilenceCut"
	on error errMsg
		display dialog "Errore: " & errMsg buttons {"OK"} default button "OK" with title "SilenceCut" with icon caution
	end try
end open

on run
	set theFolder to choose folder with prompt "Scegli la cartella del girato da analizzare"
	open {theFolder}
end run
SC_EOF_AS
  echo "OK  App creata: $APP"
else
  echo "!!  osacompile non disponibile: app non creata"
fi

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
[ -n "$FF" ] && echo "OK  ffmpeg: $FF" || echo "!!  ffmpeg non trovato: esegui  brew install ffmpeg"

echo
echo "Fatto. Trascina 'SilenceCut Analizza' dalla finestra che si apre nel Dock."
echo "Poi riavvia DaVinci Resolve."
command -v open >/dev/null 2>&1 && open -R "$APP" || true
