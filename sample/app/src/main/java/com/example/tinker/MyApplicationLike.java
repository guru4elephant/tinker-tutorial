package com.example.tinker;

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import com.tencent.tinker.anno.DefaultLifeCycle;
import com.tencent.tinker.lib.tinker.Tinker;
import com.tencent.tinker.lib.tinker.TinkerInstaller;
import com.tencent.tinker.loader.app.DefaultApplicationLike;
import com.tencent.tinker.loader.shareutil.ShareConstants;

/**
 * Tinker ApplicationLike 示例
 *
 * 使用 @DefaultLifeCycle 注解自动生成 MyApplication 类
 * MyApplication 继承自 TinkerApplication，由注解处理器生成
 *
 * flags 参数说明：
 *   TINKER_ENABLE_ALL   - 支持 dex + so + 资源修复
 *   TINKER_DEX_MASK     - 仅支持 dex 修复
 *   TINKER_NATIVE_LIBRARY_MASK - 仅支持 so 修复
 *   TINKER_RESOURCE_MASK - 仅支持资源修复
 */
@DefaultLifeCycle(
    application = "com.example.tinker.MyApplication",
    flags = ShareConstants.TINKER_ENABLE_ALL,
    loaderClass = "com.tencent.tinker.loader.TinkerLoader"
)
public class MyApplicationLike extends DefaultApplicationLike {

    private static final String TAG = "TinkerDemo";

    public MyApplicationLike(Application application, int tinkerFlags,
            boolean tinkerLoadVerifyFlag, long applicationStartElapsedTime,
            long applicationStartMillisTime, Intent tinkerResultIntent) {
        super(application, tinkerFlags, tinkerLoadVerifyFlag,
              applicationStartElapsedTime, applicationStartMillisTime,
              tinkerResultIntent);
    }

    /**
     * 等价于 Application.attachBaseContext()
     * 在这里初始化 Tinker
     */
    @Override
    public void onBaseContextAttached(Context base) {
        super.onBaseContextAttached(base);

        // 安装 Tinker（使用默认组件）
        // 生产环境建议使用自定义组件：
        // TinkerInstaller.install(this,
        //     new MyLoadReporter(getApplication()),
        //     new MyPatchReporter(getApplication()),
        //     new MyPatchListener(getApplication()),
        //     MyResultService.class,
        //     new UpgradePatch()
        // );
        TinkerInstaller.install(this);

        Log.i(TAG, "Tinker installed successfully");
    }

    /**
     * 等价于 Application.onCreate()
     * 在这里进行业务初始化
     */
    @Override
    public void onCreate() {
        super.onCreate();

        // 使用 getApplication() 而不是 this
        Log.i(TAG, "Application created");

        // 打印当前 Tinker 状态
        printTinkerStatus();
    }

    /**
     * 打印 Tinker 当前状态，用于调试
     */
    private void printTinkerStatus() {
        Tinker tinker = Tinker.with(getApplication());
        Log.i(TAG, "Tinker installed: " + tinker.isTinkerInstalled());
        Log.i(TAG, "Tinker loaded: " + tinker.isTinkerLoaded());

        if (tinker.isTinkerLoaded()) {
            var result = tinker.getTinkerLoadResultIfPresent();
            if (result != null) {
                Log.i(TAG, "Old TinkerId: " + result.getTinkerID());
                Log.i(TAG, "New TinkerId: " + result.getNewTinkerID());
                Log.i(TAG, "Patch message: " +
                    result.getPackageConfigByName("patchMessage"));
            }
        }
    }
}
