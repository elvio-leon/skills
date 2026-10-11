'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('engineBridge', {
  onTask: (cb) => ipcRenderer.on('engine:task', (_event, task) => cb(task)),
  reply: (msg) => ipcRenderer.send('engine:result', msg),
  ready: () => ipcRenderer.send('engine:ready'),
});
