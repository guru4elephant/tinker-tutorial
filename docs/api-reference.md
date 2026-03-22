# Tinker API 参考

> Tinker 核心 API 类和方法的完整参考

## 1. 核心类概览

| 类名 | 作用 |
|------|------|
| `TinkerInstaller` | 入口类，封装常用操作（安装、加载补丁、加载 so） |
| `Tinker` | 管理类，存储所有状态和信息（单例模式） |
| `TinkerLoadResult` | 补丁加载结果，包含加载信息 |
| `TinkerApplicationHelper` | 无需构造 Tinker 即可调用的辅助方法 |
| `TinkerLoadLibrary` | So 库加载工具类 |

---

## 2. TinkerInstaller

### 2.1 安装 Tinker

```java
/**
 * 安装 Tinker，必须在使用其他 API 之前调用
 * 通常在 ApplicationLike.onBaseContextAttached() 中调用
 */
public static void install(ApplicationLike applicationLike)
```

**带自定义组件的安装：**

```java
/**
 * 安装 Tinker 并指定自定义组件
 *
 * @param applicationLike   ApplicationLike 实例
 * @param loadReporter      自定义加载报告器
 * @param patchReporter     自定义补丁报告器
 * @param patchListener     自定义补丁监听器
 * @param resultServiceClass 自定义结果服务类
 * @param upgradePatchProcessor 自定义补丁处理器
 */
public static void install(
    ApplicationLike applicationLike,
    LoadReporter loadReporter,
    PatchReporter patchReporter,
    AbstractPatchListener patchListener,
    Class<? extends AbstractResultService> resultServiceClass,
    UpgradePatch upgradePatchProcessor
)
```

**完整示例：**

```java
@Override
public void onBaseContextAttached(Context base) {
    super.onBaseContextAttached(base);

    // 方式一：使用默认组件
    TinkerInstaller.install(this);

    // 方式二：使用自定义组件
    TinkerInstaller.install(
        this,
        new MyLoadReporter(getApplication()),
        new MyPatchReporter(getApplication()),
        new MyPatchListener(getApplication()),
        MyResultService.class,
        new UpgradePatch()
    );
}
```

### 2.2 加载补丁

```java
/**
 * 发起补丁升级请求
 * 请求会经过 PatchListener 验证后在后台 Service 中执行
 *
 * @param context       上下文
 * @param patchLocation 补丁文件路径
 */
public static void onReceiveUpgradePatch(Context context, String patchLocation)
```

**使用示例：**

```java
// 从 SD 卡加载补丁
String patchPath = "/sdcard/patch_signed_7zip.apk";
TinkerInstaller.onReceiveUpgradePatch(context, patchPath);

// 从应用私有目录加载（更安全）
String patchPath = getFilesDir() + "/tinker_patch.apk";
TinkerInstaller.onReceiveUpgradePatch(context, patchPath);

// 从网络下载后加载
downloadPatch(url, localPath, () -> {
    TinkerInstaller.onReceiveUpgradePatch(context, localPath);
});
```

### 2.3 加载 So 库

**方式一：手动指定加载（推荐）**

```java
// 从 Tinker 补丁目录加载 so
TinkerLoadLibrary.loadLibraryFromTinker(
    getApplicationContext(),
    "lib/armeabi-v7a",  // so 所在目录
    "libexample"         // so 名称（不含 lib 前缀和 .so 后缀）
);

// 针对特定架构的快捷方法
TinkerLoadLibrary.loadArmLibrary(context, "libexample");
TinkerLoadLibrary.loadArmV7Library(context, "libexample");
```

**方式二：反射注入方式（Hack 方式）**

```java
// 将 Tinker 补丁的 so 目录注入到系统 library path
// 之后可以直接使用 System.loadLibrary()
TinkerLoadLibrary.installNavitveLibraryABI(context, "armeabi-v7a");

// 注入后，正常的 System.loadLibrary 会自动找到补丁中的 so
System.loadLibrary("example");
```

### 2.4 日志配置

```java
// 设置自定义日志实现
TinkerInstaller.setLogIml(new TinkerLog.LogImp() {
    @Override
    public void v(String tag, String msg, Object... obj) {
        Log.v(tag, String.format(msg, obj));
    }

    @Override
    public void i(String tag, String msg, Object... obj) {
        Log.i(tag, String.format(msg, obj));
    }

    @Override
    public void w(String tag, String msg, Object... obj) {
        Log.w(tag, String.format(msg, obj));
    }

    @Override
    public void d(String tag, String msg, Object... obj) {
        Log.d(tag, String.format(msg, obj));
    }

    @Override
    public void e(String tag, String msg, Object... obj) {
        Log.e(tag, String.format(msg, obj));
    }

    @Override
    public void printErrStackTrace(String tag, Throwable e, String msg, Object... obj) {
        Log.e(tag, String.format(msg, obj), e);
    }
});
```

---

## 3. Tinker（管理类）

### 3.1 获取实例

```java
// 获取 Tinker 单例（必须已调用 TinkerInstaller.install()）
Tinker tinker = Tinker.with(context);
```

### 3.2 状态查询

```java
Tinker tinker = Tinker.with(context);

// 检查 Tinker 是否已安装
boolean installed = tinker.isTinkerInstalled();

// 检查是否有补丁已加载
boolean loaded = tinker.isTinkerLoaded();

// 检查是否正在进行补丁合成
boolean patching = tinker.isPatchProcess();

// 获取补丁加载结果
TinkerLoadResult result = tinker.getTinkerLoadResultIfPresent();

// 获取补丁目录
File patchDir = tinker.getPatchDirectory();

// 获取当前补丁版本的目录
File currentPatchDir = SharePatchFileUtil.getPatchDirectory(context);
```

### 3.3 补丁管理

```java
Tinker tinker = Tinker.with(context);

// 清除所有补丁
// ⚠️ 清除已加载的补丁可能导致崩溃，建议在清除后重启
tinker.cleanPatch();

// 清除指定版本的补丁
tinker.cleanPatchByVersion(versionFile);
```

**安全清除补丁的方式：**

```java
public void safeCleanPatch(Context context) {
    Tinker tinker = Tinker.with(context);
    tinker.cleanPatch();
    // 清除后立即杀掉进程
    ShareTinkerInternals.killAllOtherProcess(context);
    android.os.Process.killProcess(android.os.Process.myPid());
}
```

---

## 4. TinkerLoadResult

### 4.1 获取补丁信息

```java
TinkerLoadResult result = Tinker.with(context).getTinkerLoadResultIfPresent();
if (result != null) {
    // 获取自定义配置字段（在 tinkerPatch.packageConfig 中配置）
    String patchMessage = result.getPackageConfigByName("patchMessage");
    String platform = result.getPackageConfigByName("platform");
    String patchVersion = result.getPackageConfigByName("patchVersion");

    // 获取基线包的 TinkerId
    String oldTinkerId = result.getTinkerID();

    // 获取补丁包的 TinkerId
    String newTinkerId = result.getNewTinkerID();

    // 加载的 dex 信息
    boolean dexLoaded = result.dexes != null;

    // 加载的 so 信息
    boolean libLoaded = result.libs != null;

    // 加载的资源信息
    boolean resLoaded = result.resource;
}
```

### 4.2 验证 Dex 完整性

```java
// 使用 MD5 验证 dex 文件完整性
// 注意：dex 可能被重打包为 jar 格式
boolean valid = SharePatchFileUtil.verifyDexFileMd5(
    dexFile,
    expectedMd5
);
```

---

## 5. TinkerApplicationHelper

在 `TinkerInstaller.install()` 之前或某些进程中不需要初始化 Tinker 时，可以使用此类获取信息：

```java
// 获取当前补丁版本目录
String currentVersion = TinkerApplicationHelper.getCurrentVersion(context);

// 检查是否在补丁进程中
boolean isPatchProcess = TinkerApplicationHelper.isPatchProcess(context);

// 检查 Tinker 是否启用
boolean enabled = TinkerApplicationHelper.isTinkerEnabled(context);

// 获取已加载的补丁信息
TinkerLoadResult result = TinkerApplicationHelper.getTinkerLoadResult(context);

// 加载 so（不需要先 install Tinker）
TinkerApplicationHelper.loadArmLibrary(context, "libexample");
TinkerApplicationHelper.loadArmV7Library(context, "libexample");
```

---

## 6. ShareConstants（常量）

### 6.1 Tinker Flags

控制 Tinker 支持的修复类型：

```java
// 支持所有类型（dex + so + 资源）
ShareConstants.TINKER_ENABLE_ALL

// 仅支持 dex 修复
ShareConstants.TINKER_DEX_MASK

// 仅支持 so 修复
ShareConstants.TINKER_NATIVE_LIBRARY_MASK

// 仅支持资源修复
ShareConstants.TINKER_RESOURCE_MASK

// 同时支持 dex 和 so
ShareConstants.TINKER_DEX_AND_LIBRARY

// 禁用 Tinker
ShareConstants.TINKER_DISABLE
```

### 6.2 错误码

**补丁加载错误码：**

| 错误码 | 含义 |
|--------|------|
| 0 | 成功 |
| -1 | 未启用 |
| -2 | 补丁信息文件不存在 |
| -3 | 补丁版本文件不存在 |
| -4 | 补丁包签名校验失败 |
| -5 | 补丁包 TinkerId 不匹配 |
| -6 | 补丁包完整性校验失败 |
| -7 | 补丁包已被禁用 |
| -8 | dex 文件校验失败 |
| -9 | so 文件校验失败 |

**补丁请求错误码：**

| 错误码 | 含义 |
|--------|------|
| -1 | 补丁功能已禁用 |
| -2 | 补丁文件不存在 |
| -3 | 补丁中... 正在合成 |
| -4 | 超出重试次数 |
| -5 | 服务进程异常 |
| -6 | JIT 崩溃（部分 CPU 上） |
| -7 | ROM 空间不足 |

---

## 7. 实用工具

### 7.1 ShareTinkerInternals

```java
// 杀掉所有其他进程（补丁加载完成后重启用）
ShareTinkerInternals.killAllOtherProcess(context);

// 检查当前是否是主进程
boolean isMainProcess = ShareTinkerInternals.isInMainProcess(context);

// 获取当前进程名
String processName = ShareTinkerInternals.getCurrentProcessName(context);
```

### 7.2 SharePatchFileUtil

```java
// 验证文件 MD5
boolean valid = SharePatchFileUtil.verifyFileMd5(file, md5);

// 验证 dex 文件 MD5
boolean valid = SharePatchFileUtil.verifyDexFileMd5(file, md5);

// 获取文件 MD5
String md5 = SharePatchFileUtil.getMD5(file);
```
