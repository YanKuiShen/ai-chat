const { app, BrowserWindow, dialog, screen } = require('electron');
const path = require('path');

let mainWindow;
let serverPort = 3456;
let _cleanupServer = null;  // v3.8.1：app 退出时清理所有 spawn 子进程（混元3D + PS bridge）

// 防止双开：第二个实例启动时直接聚焦到第一个窗口
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  return;
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

function createWindow() {
  // v1.8.5：约束窗口尺寸不超过屏幕可用区域（避免在小屏笔记本上窗口超出屏幕）
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
  const winW = Math.min(1200, sw);
  const winH = Math.min(800, sh);
  mainWindow = new BrowserWindow({
    width: winW,
    height: winH,
    minWidth: 900,
    minHeight: 600,
    maxWidth: sw,
    maxHeight: sh,
    center: true,                  // 居中显示
    useContentSize: true,          // width/height 指内容区域而非含标题栏
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: path.join(__dirname, 'public', 'app-icon.icns')
  });
  // 防止用户拖拽放大超出屏幕
  mainWindow.setMaximumSize(sw, sh);


  // 隐藏菜单栏
  mainWindow.setMenuBarVisibility(false);

  // 加载本地服务器地址（端口由服务实际监听到的为准）
  mainWindow.loadURL(`http://localhost:${serverPort}`);

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

app.on('ready', async () => {
  // 设置数据存储目录为用户数据目录，防止打包后无法写入
  const userDataPath = app.getPath('userData');
  process.env.DATA_DIR = path.join(userDataPath, 'data');

  try {
    // 在主进程中启动 Express 服务器，等服务真正监听后再创建窗口
    const { startServer, cleanupOnExit } = require('./server.js');
    _cleanupServer = cleanupOnExit;
    const result = await startServer(3456, 20);
    serverPort = result.port;
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      '启动失败',
      `无法启动本地服务：${err.message}\n\n请检查是否有其他程序占用了 3456-3475 端口，或者重启电脑后再试。`
    );
    app.quit();
  }
});

// v3.8.1：退出前清理所有 spawn 子进程（混元3D + PS bridge），根治孤儿残留
app.on('before-quit', function () {
  if (typeof _cleanupServer === 'function') {
    try { _cleanupServer(); } catch (e) {}
  }
});

app.on('window-all-closed', function () {
  // 所有平台关闭窗口都退出应用（避免 macOS 后台残留导致端口被占）
  app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) {
    createWindow();
  }
});
