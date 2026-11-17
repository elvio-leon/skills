--[[
SilenceCut (versione Lua) — taglio automatico dei silenzi per DaVinci Resolve.
Non richiede Python: Lua è integrato in Resolve. Serve solo ffmpeg (brew install ffmpeg).

Installazione: copia questo file in
  ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
Uso: seleziona le clip nel Media Pool -> Workspace > Scripts > SilenceCut.
Crea una NUOVA timeline con solo le parti parlate; le clip originali non vengono toccate.
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
local ASK_PRESET = true       -- mostra la finestrina di scelta del preset
local CLIP_COLORS = { "Orange", "Teal", "Yellow", "Violet", "Green", "Pink", "Blue", "Apricot" }
local FFMPEG_CANDIDATES = { "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg" }

-- ---------------------------------------------------------------------------

local function shq(s)
  return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

local function exec(cmd)
  local p = io.popen(cmd .. " 2>&1")
  if not p then return "" end
  local out = p:read("*a") or ""
  p:close()
  return out
end

local function file_exists(path)
  local f = io.open(path, "r")
  if f then f:close() return true end
  return false
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
  exec("osascript -e " .. shq('display dialog ' .. applescript_str(msg) ..
    ' with title "SilenceCut" buttons {"OK"} default button "OK"'))
end

local function choose_preset()
  if not ASK_PRESET then return DEFAULT_PRESET end
  local items = {}
  for i, n in ipairs(PRESET_ORDER) do items[i] = '"' .. n .. '"' end
  local script = 'choose from list {' .. table.concat(items, ", ") ..
    '} with title "SilenceCut" with prompt "Quanto tagliare i silenzi?" default items {"' .. DEFAULT_PRESET .. '"}'
  local out = exec("osascript -e " .. shq(script)):gsub("%s+$", "")
  if out == "false" then return nil end   -- annullato
  if PRESETS[out] then return out end
  return DEFAULT_PRESET                   -- osascript non disponibile o risposta strana
end

local function fmt_time(sec)
  sec = math.floor(sec + 0.5)
  return string.format("%d:%02d", math.floor(sec / 60), sec % 60)
end

-- Analizza l'audio con ffmpeg e restituisce silenzi + durata
local function detect_silences(ffmpeg, path, p)
  local cmd = shq(ffmpeg) .. " -hide_banner -nostats -i " .. shq(path) ..
    " -map 0:a:" .. AUDIO_STREAM ..
    " -af " .. shq(string.format("silencedetect=noise=%sdB:d=%s", p.noise_db, p.min_silence)) ..
    " -f null -"
  local out = exec(cmd)
  local duration
  local h, m, s = out:match("Duration:%s*(%d+):(%d+):([%d%.]+)")
  if h then duration = tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s) end

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

local function to_list(t)
  local l = {}
  if type(t) ~= "table" then return l end
  for _, v in pairs(t) do l[#l + 1] = v end
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

local function main()
  local res = resolve or (Resolve and Resolve()) or (app and app:GetResolve())
  if not res then return alert("Impossibile collegarsi a DaVinci Resolve.") end
  local project = res:GetProjectManager():GetCurrentProject()
  if not project then return alert("Apri prima un progetto in DaVinci Resolve.") end
  local mp = project:GetMediaPool()

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
  if #clips == 0 then return alert("Seleziona una o più clip nel Media Pool e rilancia lo script.") end

  local ffmpeg = find_ffmpeg()
  if not ffmpeg then return alert("ffmpeg non trovato. Installalo dal Terminale con:  brew install ffmpeg") end

  local preset_name = choose_preset()
  if not preset_name then return end
  local p = PRESETS[preset_name]
  print("SilenceCut — preset " .. preset_name)

  local infos, sources, errors = {}, {}, {}
  local total_before, total_after = 0, 0
  for idx, clip in ipairs(clips) do
    local path = clip:GetClipProperty("File Path")
    local okc, silences, duration = pcall(detect_silences, ffmpeg, path, p)
    if not okc then
      errors[#errors + 1] = tostring(silences)
    else
      local fps = clip_fps(clip, project)
      local frames = tonumber(clip:GetClipProperty("Frames") or "")
      if frames and frames > 0 then duration = frames / fps end
      local segs = speech_segments(silences, duration, p)
      local kept = 0
      for _, sg in ipairs(segs) do
        local sf, ef = round(sg[1] * fps), round(sg[2] * fps) - 1   -- endFrame incluso
        if ef > sf then
          infos[#infos + 1] = { mediaPoolItem = clip, startFrame = sf, endFrame = ef }
          sources[#sources + 1] = idx
          kept = kept + (sg[2] - sg[1])
        end
      end
      total_before = total_before + (duration or 0)
      total_after = total_after + kept
      print(string.format("  %s: %d pezzi, %s -> %s", clip:GetName(), #segs, fmt_time(duration or 0), fmt_time(kept)))
    end
  end

  if #infos == 0 then return alert("Nessun parlato trovato.\n" .. table.concat(errors, "\n")) end

  local base = (#clips == 1) and clips[1]:GetName() or (#clips .. " clip")
  local tl_name = "SilenceCut - " .. base .. " - " .. os.date("%H.%M.%S")
  local timeline = mp:CreateEmptyTimeline(tl_name)
  if not timeline then return alert("Impossibile creare la timeline.") end
  project:SetCurrentTimeline(timeline)
  local items = to_list(mp:AppendToTimeline(infos))

  if #clips > 1 then
    for i, item in ipairs(items) do
      if sources[i] then pcall(function() item:SetClipColor(CLIP_COLORS[(sources[i] - 1) % #CLIP_COLORS + 1]) end) end
    end
  end
  pcall(function() res:OpenPage("edit") end)

  local msg = string.format("Timeline creata: %s\n%d pezzi — da %s a %s (preset %s).",
    tl_name, #infos, fmt_time(total_before), fmt_time(total_after), preset_name)
  if #errors > 0 then msg = msg .. "\n\nAttenzione:\n" .. table.concat(errors, "\n") end
  alert(msg)
end

local ok, err = pcall(main)
if not ok then alert("Errore: " .. tostring(err)) end
