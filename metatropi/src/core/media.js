'use strict';

// Conversioni di immagini, audio, video e sottotitoli con ffmpeg
// (e con `sips` di macOS per HEIC, RAW e PSD).

const fs = require('fs');
const { tools, run, ConversionError } = require('./tools');

function ffmpegPath() {
  const p = tools().ffmpeg;
  if (!p) throw new ConversionError('ffmpeg non è disponibile');
  return p;
}

function stripParens(s) {
  let prev;
  do {
    prev = s;
    s = s.replace(/\([^()]*\)/g, '');
  } while (s !== prev);
  return s;
}

// Legge durata, dimensioni e trasparenza dall'output di `ffmpeg -i`.
async function probe(input, signal) {
  const { stderr } = await run(ffmpegPath(), ['-hide_banner', '-nostdin', '-i', input], { signal, allowFailure: true });
  const info = { duration: 0, width: 0, height: 0, pixFmt: '', hasVideo: false, hasAudio: false, hasAlpha: false };
  const d = stderr.match(/Duration: (\d+):(\d+):(\d+(?:\.\d+)?)/);
  if (d) info.duration = Number(d[1]) * 3600 + Number(d[2]) * 60 + Number(d[3]);
  for (const line of stderr.split('\n')) {
    if (/Stream #.*: Audio:/.test(line)) info.hasAudio = true;
    const v = line.match(/Stream #.*?: Video: (.*)$/);
    if (v && !info.hasVideo && !line.includes('(attached pic)')) {
      info.hasVideo = true;
      const parts = stripParens(v[1]).split(',').map((s) => s.trim());
      info.pixFmt = parts[1] || '';
      const size = v[1].match(/\b(\d{2,5})x(\d{2,5})\b/);
      if (size) {
        info.width = Number(size[1]);
        info.height = Number(size[2]);
      }
    }
  }
  info.hasAlpha = /rgba|bgra|argb|abgr|yuva|ya8|ya16|pal8|gbrap|rgb32/.test(info.pixFmt);
  return info;
}

function hhmmssToSeconds(t) {
  const m = String(t).match(/(\d+):(\d+):(\d+(?:\.\d+)?)/);
  return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : 0;
}

// Esegue ffmpeg riportando l'avanzamento (0..1) se la durata è nota.
async function ffmpeg(args, { signal, onProgress, duration } = {}) {
  const full = ['-hide_banner', '-nostdin', '-y', ...args.slice(0, -1), '-progress', 'pipe:1', '-nostats', args[args.length - 1]];
  let buf = '';
  return run(ffmpegPath(), full, {
    signal,
    onStdout: (chunk) => {
      if (!onProgress || !duration) return;
      buf += chunk;
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        const [k, val] = line.split('=');
        if (k === 'out_time_us' || k === 'out_time_ms') {
          const sec = Number(val) / 1e6;
          if (Number.isFinite(sec) && sec >= 0) onProgress(Math.min(0.99, sec / duration));
        } else if (k === 'out_time') {
          const sec = hhmmssToSeconds(val);
          if (sec > 0) onProgress(Math.min(0.99, sec / duration));
        }
      }
    },
  });
}

function fitFilter(max) {
  return `scale=w='min(${max},iw)':h='min(${max},ih)':force_original_aspect_ratio=decrease`;
}

const EVEN = 'scale=trunc(iw/2)*2:trunc(ih/2)*2';

// ---------- Immagini ----------

const IMAGE2_TARGETS = new Set(['jpg', 'png', 'bmp', 'tiff']);

async function ffmpegImage(input, out, targetId, opts, { signal, animated } = {}) {
  const info = await probe(input, signal);
  const quality = clamp(Number(opts.imageQuality) || 85, 1, 100);
  let max = Number(opts.maxSize) || 0;
  if (targetId === 'ico') max = max ? Math.min(max, 256) : 256;

  const chain = [];
  if (max) chain.push(fitFilter(max));
  const args = ['-i', input];
  const flatten = (targetId === 'jpg' || targetId === 'avif') && info.hasAlpha && info.width && info.height;

  if (targetId === 'gif') {
    const pre = chain.length ? `${chain.join(',')},` : '';
    args.push('-filter_complex', `[0:v]${pre}split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse=dither=sierra2_4a[out]`, '-map', '[out]');
    if (animated) args.push('-loop', '0');
  } else if (flatten) {
    const post = [...chain];
    if (targetId === 'avif') post.push(EVEN, 'format=yuv420p');
    else post.push('format=yuvj420p');
    args.push(
      '-filter_complex',
      `color=c=white:s=${info.width}x${info.height}[bg];[bg][0:v]overlay=shortest=1:format=auto,${post.join(',')}[out]`,
      '-map', '[out]',
    );
  } else {
    if (targetId === 'avif') chain.push(EVEN, 'format=yuv420p');
    if (targetId === 'jpg') chain.push('format=yuvj420p');
    if (targetId === 'ico') chain.push('format=bgra');
    if (chain.length) args.push('-vf', chain.join(','));
  }

  switch (targetId) {
    case 'jpg':
      args.push('-c:v', 'mjpeg', '-q:v', String(Math.round(2 + ((100 - quality) * 29) / 99)));
      break;
    case 'png':
      args.push('-c:v', 'png');
      break;
    case 'webp':
      args.push('-c:v', 'libwebp', '-quality', String(quality));
      if (animated) args.push('-loop', '0');
      break;
    case 'avif':
      args.push('-c:v', 'libaom-av1', '-still-picture', '1', '-crf', String(Math.round(10 + (100 - quality) * 0.45)), '-cpu-used', '6', '-f', 'avif');
      break;
    case 'bmp':
      args.push('-c:v', 'bmp');
      break;
    case 'tiff':
      args.push('-c:v', 'tiff', '-compression_algo', 'lzw');
      break;
    case 'ico':
      args.push('-c:v', 'bmp', '-f', 'ico');
      break;
    case 'gif':
      break;
    default:
      throw new ConversionError(`Formato immagine non gestito: ${targetId}`);
  }
  if (!animated) args.push('-frames:v', '1');
  if (IMAGE2_TARGETS.has(targetId)) args.push('-update', '1');
  args.push(out);
  await ffmpeg(args, { signal });
}

async function sips(input, out, format, { quality, maxSize, signal } = {}) {
  const bin = tools().sips;
  if (!bin) throw new ConversionError('sips è disponibile solo su macOS');
  const args = ['-s', 'format', format];
  if (quality && (format === 'heic' || format === 'jpeg')) args.push('-s', 'formatOptions', String(quality));
  if (maxSize) args.push('-Z', String(maxSize));
  args.push(input, '--out', out);
  try {
    await run(bin, args, { signal });
  } catch (err) {
    if (err.cancelled) throw err;
    throw new ConversionError('macOS non è riuscito a elaborare questa immagine', err.details);
  }
  if (!fs.existsSync(out)) throw new ConversionError('sips non ha prodotto alcun file');
}

// ---------- Audio ----------

function audioCodecArgs(targetId, opts) {
  const br = clamp(Number(opts.audioBitrate) || 192, 32, 320);
  switch (targetId) {
    case 'mp3':
      return ['-c:a', 'libmp3lame', '-b:a', `${br}k`, '-id3v2_version', '3'];
    case 'm4a':
      return ['-c:a', 'aac', '-b:a', `${br}k`, '-movflags', '+faststart'];
    case 'alac':
      return ['-c:a', 'alac'];
    case 'wav':
      return ['-c:a', 'pcm_s16le'];
    case 'aiff':
      return ['-c:a', 'pcm_s16be'];
    case 'flac':
      return ['-c:a', 'flac'];
    case 'ogg':
      return ['-c:a', 'libvorbis', '-b:a', `${br}k`];
    case 'opus':
      return ['-c:a', 'libopus', '-b:a', `${Math.min(br, 256)}k`];
    default:
      return null;
  }
}

async function convertAudio(input, out, targetId, opts, { signal, onProgress } = {}) {
  const info = await probe(input, signal);
  if (!info.hasAudio) throw new ConversionError('Il file non contiene una traccia audio');
  const codec = audioCodecArgs(targetId, opts);
  if (!codec) throw new ConversionError(`Formato audio non gestito: ${targetId}`);
  const args = ['-i', input, '-map', '0:a:0', '-vn', '-map_metadata', '0', ...codec, out];
  await ffmpeg(args, { signal, onProgress, duration: info.duration });
}

// ---------- Video ----------

const CRF = {
  x264: { high: 18, balanced: 23, small: 28 },
  vp9: { high: 28, balanced: 33, small: 40 },
  mpeg4: { high: 3, balanced: 5, small: 8 },
};

async function convertVideo(input, out, targetId, opts, { signal, onProgress } = {}) {
  const info = await probe(input, signal);
  if (!info.hasVideo) throw new ConversionError('Il file non contiene una traccia video');
  const q = ['high', 'balanced', 'small'].includes(opts.videoQuality) ? opts.videoQuality : 'balanced';
  const height = Number(opts.videoHeight) || 0;
  const progress = { signal, onProgress, duration: info.duration };

  if (targetId === 'gif') {
    const fps = clamp(Number(opts.gifFps) || 12, 1, 30);
    const width = Number(opts.maxSize) || 480;
    const scale = `scale=w='min(${width},iw)':h=-1:flags=lanczos`;
    await ffmpeg(
      ['-i', input, '-filter_complex', `[0:v]fps=${fps},${scale},split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4[out]`, '-map', '[out]', '-loop', '0', out],
      progress,
    );
    return;
  }

  if (opts.fastCopy) {
    try {
      await ffmpeg(['-i', input, '-map', '0:v:0', '-map', '0:a?', '-c', 'copy', ...(targetId === 'mp4' ? ['-movflags', '+faststart'] : []), out], progress);
      return;
    } catch (err) {
      if (err.cancelled) throw err;
      // Codec non compatibili con il contenitore: si ricodifica.
    }
  }

  const vf = height ? `scale=-2:'min(${height},ih)':flags=lanczos,${EVEN}` : EVEN;
  const args = ['-i', input, '-map', '0:v:0', '-map', '0:a:0?', '-vf', vf];
  switch (targetId) {
    case 'mp4':
    case 'mov':
    case 'mkv':
      args.push('-c:v', 'libx264', '-preset', 'medium', '-crf', String(CRF.x264[q]), '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k');
      if (targetId === 'mp4') args.push('-movflags', '+faststart');
      break;
    case 'webm':
      args.push('-c:v', 'libvpx-vp9', '-crf', String(CRF.vp9[q]), '-b:v', '0', '-row-mt', '1', '-deadline', 'good', '-cpu-used', '4', '-pix_fmt', 'yuv420p', '-c:a', 'libopus', '-b:a', '128k');
      break;
    case 'avi':
      args.push('-c:v', 'mpeg4', '-q:v', String(CRF.mpeg4[q]), '-tag:v', 'XVID', '-c:a', 'libmp3lame', '-b:a', '192k');
      break;
    default:
      throw new ConversionError(`Formato video non gestito: ${targetId}`);
  }
  args.push(out);
  await ffmpeg(args, progress);
}

// ---------- Sottotitoli ----------

async function convertSubtitle(input, out, { signal } = {}) {
  await ffmpeg(['-i', input, out], { signal });
}

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

module.exports = {
  probe,
  ffmpegImage,
  sips,
  convertAudio,
  convertVideo,
  convertSubtitle,
  audioCodecArgs,
};
