# Tinker 自定义扩展

> 高级自定义用法，包括自定义监听器、报告器、结果处理等

## 1. 可扩展组件概览

Tinker 提供了多个可自定义的组件，通过在 `TinkerInstaller.install()` 时传入自定义实现：

| 组件 | 作用 | 默认实现 |
|------|------|---------|
| `LoadReporter` | 补丁加载结果回调 | `DefaultLoadReporter` |
| `PatchReporter` | 补丁合成过程回调 | `DefaultPatchReporter` |
| `PatchListener` | 补丁请求过滤/验证 | `DefaultPatchListener` |
| `ResultService` | 补丁合成结果处理 | `DefaultTinkerResultService` |
| `TinkerLoader` | 自定义加载器（不推荐修改） | `TinkerLoader` |

```java
// 使用自定义组件安装 Tinker
TinkerInstaller.install(
    applicationLike,
    new MyLoadReporter(context),
    new MyPatchReporter(context),
    new MyPatchListener(context),
    MyResultService.class,
    new UpgradePatch()
);
```

---

## 2. 自定义 LoadReporter

`LoadReporter` 在每次应用启动加载补丁时被回调，可以用于监控和上报。

```java
public class MyLoadReporter extends DefaultLoadReporter {

    public MyLoadReporter(Context context) {
        super(context);
    }

    /**
     * 所有加载完成后回调（无论成功失败）
     * 可在此处上报加载结果到监控平台
     */
    @Override
    public void onLoadResult(File patchDirectory, int loadCode, long cost) {
        super.onLoadResult(patchDirectory, loadCode, cost);

        // 上报加载结果
        if (loadCode == ShareConstants.ERROR_LOAD_OK) {
            // 加载成功
            Analytics.report("tinker_load_success", cost);
        } else {
            // 加载失败
            Analytics.report("tinker_load_fail", loadCode);
        }
    }

    /**
     * 补丁文件未找到
     */
    @Override
    public void onLoadFileNotFound(File file, int fileType, boolean isDirectory) {
        super.onLoadFileNotFound(file, fileType, isDirectory);
        Log.w("Tinker", "Patch file not found: " + file.getPath());
    }

    /**
     * 文件 MD5 校验不匹配
     */
    @Override
    public void onLoadFileMd5Mismatch(File file, int fileType) {
        super.onLoadFileMd5Mismatch(file, fileType);
        Log.e("Tinker", "MD5 mismatch: " + file.getPath());
        // 文件被篡改，考虑清除补丁
    }

    /**
     * 补丁包校验失败（签名、版本等）
     */
    @Override
    public void onLoadPackageCheckFail(File patchFile, int errorCode) {
        super.onLoadPackageCheckFail(patchFile, errorCode);
        Log.e("Tinker", "Package check failed, code: " + errorCode);
    }

    /**
     * dex 加载异常
     */
    @Override
    public void onLoadException(Throwable e, int errorCode) {
        super.onLoadException(e, errorCode);
        // 上报异常
        CrashReporter.report(e);
    }
}
```

---

## 3. 自定义 PatchReporter

`PatchReporter` 在补丁合成过程中被回调。

```java
public class MyPatchReporter extends DefaultPatchReporter {

    public MyPatchReporter(Context context) {
        super(context);
    }

    /**
     * 补丁合成结果回调
     */
    @Override
    public void onPatchResult(File patchFile, boolean success, long cost) {
        super.onPatchResult(patchFile, success, cost);

        Analytics.report("tinker_patch_result",
            "success", success,
            "cost", cost
        );
    }

    /**
     * 补丁合成服务启动
     */
    @Override
    public void onPatchServiceStart(Intent intent) {
        super.onPatchServiceStart(intent);
        Log.i("Tinker", "Patch service started");
    }

    /**
     * 补丁包校验失败
     */
    @Override
    public void onPatchPackageCheckFail(File patchFile, int errorCode) {
        super.onPatchPackageCheckFail(patchFile, errorCode);
        Log.e("Tinker", "Patch package check failed: " + errorCode);
    }

    /**
     * dex/so/资源 提取失败
     */
    @Override
    public void onPatchTypeExtractFail(File patchFile, File extractTo,
            String filename, int fileType) {
        super.onPatchTypeExtractFail(patchFile, extractTo, filename, fileType);
        Log.e("Tinker", "Extract failed: " + filename);
    }

    /**
     * dex 合成（DexDiff）异常
     */
    @Override
    public void onPatchDexOptFail(File patchFile, File dexFile, String optDir,
            Throwable t) {
        super.onPatchDexOptFail(patchFile, dexFile, optDir, t);
        CrashReporter.report(t);
    }
}
```

---

## 4. 自定义 PatchListener

`PatchListener` 在接收到补丁请求时被调用，可以在此过滤和验证补丁。

```java
public class MyPatchListener extends DefaultPatchListener {

    private final Context context;

    public MyPatchListener(Context context) {
        super(context);
        this.context = context;
    }

    /**
     * 补丁请求过滤
     * 返回 0 表示允许，返回负数表示拒绝
     */
    @Override
    public int patchCheck(String path, String patchMd5) {
        // 先执行默认检查（Tinker 是否启用、文件是否存在、是否正在合成等）
        int result = super.patchCheck(path, patchMd5);
        if (result != ShareConstants.ERROR_PATCH_OK) {
            return result;
        }

        // 自定义检查：ROM 空间是否充足
        if (!hasEnoughStorage()) {
            return MyErrorCode.ERROR_STORAGE_NOT_ENOUGH;
        }

        // 自定义检查：是否在主进程
        if (!ShareTinkerInternals.isInMainProcess(context)) {
            return MyErrorCode.ERROR_NOT_MAIN_PROCESS;
        }

        // 自定义检查：网络环境
        if (isOnMobileNetwork() && !allowPatchOnMobile()) {
            return MyErrorCode.ERROR_MOBILE_NETWORK;
        }

        // 自定义检查：温度是否过高（CPU 密集操作可能导致温度升高）
        if (isBatteryTooLow()) {
            return MyErrorCode.ERROR_BATTERY_LOW;
        }

        return ShareConstants.ERROR_PATCH_OK;
    }

    private boolean hasEnoughStorage() {
        // 检查存储空间
        StatFs stat = new StatFs(Environment.getDataDirectory().getPath());
        long available = stat.getAvailableBytes();
        return available > 50 * 1024 * 1024; // 至少 50MB
    }

    private boolean isBatteryTooLow() {
        IntentFilter filter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        Intent battery = context.registerReceiver(null, filter);
        int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        float percent = level * 100f / scale;
        return percent < 15f;
    }
}
```

---

## 5. 自定义 ResultService

`ResultService` 在补丁合成完成后被调用（运行在补丁进程中），用于处理合成结果。

```java
public class MyResultService extends DefaultTinkerResultService {

    /**
     * 补丁合成完成后的回调
     * 注意：此方法在 :patch 进程中执行
     */
    @Override
    public void onPatchResult(PatchResult result) {
        if (result == null) {
            Log.e("Tinker", "Result is null");
            return;
        }

        if (!result.isSuccess) {
            Log.e("Tinker", "Patch failed: " + result.rawPatchFilePath);
            // 合成失败，可以上报错误
            return;
        }

        Log.i("Tinker", "Patch success: " + result.rawPatchFilePath);

        // 策略一：立即杀掉进程，下次启动生效（用户体验较差）
        // killProcessAndRestart();

        // 策略二：等待应用切到后台时重启（推荐）
        // 通过 SharedPreferences 标记有新补丁
        markPatchReady();

        // 策略三：下次自然启动时生效（不做额外处理）
        // 什么都不做
    }

    private void killProcessAndRestart() {
        // 杀掉所有其他进程
        ShareTinkerInternals.killAllOtherProcess(getApplicationContext());
        // 杀掉当前进程（:patch 进程）
        android.os.Process.killProcess(android.os.Process.myPid());
    }

    private void markPatchReady() {
        SharedPreferences sp = getSharedPreferences("tinker_patch", MODE_PRIVATE);
        sp.edit().putBoolean("patch_ready", true).apply();
    }
}
```

**别忘了在 AndroidManifest.xml 中注册：**

```xml
<service
    android:name=".MyResultService"
    android:exported="false"
    android:process=":patch" />
```

---

## 6. 后台重启策略

最佳用户体验的补丁生效策略：当应用切到后台时重启。

```java
public class MyApplicationLike extends DefaultApplicationLike {

    @Override
    public void onCreate() {
        super.onCreate();

        // 注册应用前后台监听
        getApplication().registerActivityLifecycleCallbacks(
            new Application.ActivityLifecycleCallbacks() {
                private int activityCount = 0;

                @Override
                public void onActivityStarted(Activity activity) {
                    activityCount++;
                }

                @Override
                public void onActivityStopped(Activity activity) {
                    activityCount--;
                    if (activityCount == 0) {
                        // 应用切到后台
                        checkAndApplyPatch();
                    }
                }

                // ... 其他方法留空

                @Override
                public void onActivityCreated(Activity a, Bundle b) {}
                @Override
                public void onActivityResumed(Activity a) {}
                @Override
                public void onActivityPaused(Activity a) {}
                @Override
                public void onActivitySaveInstanceState(Activity a, Bundle b) {}
                @Override
                public void onActivityDestroyed(Activity a) {}
            }
        );
    }

    private void checkAndApplyPatch() {
        SharedPreferences sp = getApplication()
            .getSharedPreferences("tinker_patch", Context.MODE_PRIVATE);
        if (sp.getBoolean("patch_ready", false)) {
            sp.edit().putBoolean("patch_ready", false).apply();
            // 杀掉进程，下次启动时补丁生效
            ShareTinkerInternals.killAllOtherProcess(getApplication());
            android.os.Process.killProcess(android.os.Process.myPid());
        }
    }
}
```

---

## 7. 自定义 TinkerLoader

> ⚠️ **不推荐自定义 TinkerLoader**，除非有非常特殊的需求。

如果需要自定义，注意：

1. TinkerLoader 及其引用的所有类必须添加到 `dex.loader` 配置中
2. 这些类必须在主 dex 中
3. 这些类 **不能被热修复**

```java
public class MyTinkerLoader extends TinkerLoader {

    @Override
    public Intent tryLoad(TinkerApplication app) {
        // 自定义加载逻辑
        Intent result = super.tryLoad(app);

        // 可以在此添加自定义的加载前验证
        return result;
    }
}
```

在 `@DefaultLifeCycle` 注解中指定：

```java
@DefaultLifeCycle(
    application = "com.example.tinker.MyApplication",
    flags = ShareConstants.TINKER_ENABLE_ALL,
    loaderClass = "com.example.tinker.MyTinkerLoader"
)
```

---

## 8. 多进程处理

Tinker 在多进程场景下需要注意：

```java
@Override
public void onBaseContextAttached(Context base) {
    super.onBaseContextAttached(base);

    if (ShareTinkerInternals.isInMainProcess(base)) {
        // 主进程：完整安装 Tinker
        TinkerInstaller.install(this,
            new MyLoadReporter(getApplication()),
            new MyPatchReporter(getApplication()),
            new MyPatchListener(getApplication()),
            MyResultService.class,
            new UpgradePatch()
        );
    } else {
        // 非主进程：可以使用简化安装
        // 或者不安装（使用 TinkerApplicationHelper 获取信息）
        TinkerInstaller.install(this);
    }
}
```

---

## 9. Notification 配置

Tinker 的补丁合成 Service 是前台 Service（Android O+ 要求），默认会显示一个通知：

```java
// 自定义通知 ID
TinkerPatchService.setTinkerNotificationId(100);

// 或在 Service 中自定义通知样式
// 需要自定义 AbstractTinkerPatchService
```

---

## 10. 调试与排错

### 10.1 启用详细日志

```java
// 在安装 Tinker 之前设置
TinkerInstaller.setLogIml(new TinkerLog.LogImp() {
    // 实现所有日志方法，输出到 Logcat
    // 可以额外写入文件，方便排查线上问题
});
```

### 10.2 验证补丁是否生效

```java
public void checkPatchStatus() {
    Tinker tinker = Tinker.with(context);

    Log.d("Tinker", "Installed: " + tinker.isTinkerInstalled());
    Log.d("Tinker", "Loaded: " + tinker.isTinkerLoaded());

    TinkerLoadResult result = tinker.getTinkerLoadResultIfPresent();
    if (result != null) {
        Log.d("Tinker", "Old TinkerId: " + result.getTinkerID());
        Log.d("Tinker", "New TinkerId: " + result.getNewTinkerID());
        Log.d("Tinker", "Patch message: " +
            result.getPackageConfigByName("patchMessage"));
    }
}
```

### 10.3 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 补丁不生效 | 未重启应用 | 杀掉进程后重启 |
| TinkerId 不匹配 | 基线包版本不对 | 确认 oldApk 指向正确的基线包 |
| MD5 校验失败 | 补丁文件损坏 | 重新下载/推送补丁 |
| 签名校验失败 | 签名不一致 | 确保补丁和基线包使用相同签名 |
| ClassNotFound | 类在 loader 列表中 | 检查 dex.loader 配置 |
| ProGuard 不一致 | 未使用基线包的 mapping | 配置 applyMapping |
