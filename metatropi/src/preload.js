'use strict';

const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('api', {
  env: () => ipcRenderer.invoke('env'),
  describe: (paths) => ipcRenderer.invoke('describe', paths),
  pathForFile: (file) => webUtils.getPathForFile(file),
  pickFiles: () => ipcRenderer.invoke('pick-files'),
  pickFolder: () => ipcRenderer.invoke('pick-folder'),
  convert: (jobs, options) => ipcRenderer.invoke('convert', { jobs, options }),
  cancel: () => ipcRenderer.invoke('cancel'),
  reveal: (p) => ipcRenderer.invoke('reveal', p),
  openPath: (p) => ipcRenderer.invoke('open-path', p),
  openLibreOfficeSite: () => ipcRenderer.invoke('open-libreoffice-site'),
  onJobUpdate: (cb) => ipcRenderer.on('job:update', (_e, msg) => cb(msg)),
  onQueueDone: (cb) => ipcRenderer.on('queue:done', (_e, msg) => cb(msg)),
  onOpenFiles: (cb) => ipcRenderer.on('open-files', (_e, paths) => cb(paths)),
});
