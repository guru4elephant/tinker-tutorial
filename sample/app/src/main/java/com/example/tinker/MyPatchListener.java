package com.example.tinker;

import android.content.Context;
import android.os.StatFs;
import android.os.Environment;
import android.util.Log;

import com.tencent.tinker.lib.listener.DefaultPatchListener;
import com.tencent.tinker.loader.shareutil.ShareConstants;
import com.tencent.tinker.loader.shareutil.ShareTinkerInternals;

/**
 * 自定义补丁请求监听器
 *
 * 在接收到补丁请求时被调用
 * 可以在此处添加自定义的前置检查逻辑
 */
public class MyPatchListener extends DefaultPatchListener {

    private static final String TAG = "TinkerDemo";
    private static final long MIN_STORAGE_BYTES = 50 * 1024 * 1024; // 50MB

    private final Context context;

    public MyPatchListener(Context context) {
        super(context);
        this.context = context;
    }

    /**
     * 补丁请求过滤
     *
     * @return 0 = 允许加载; 负数 = 拒绝加载
     */
    @Override
    public int patchCheck(String path, String patchMd5) {
        // 执行默认检查
        int result = super.patchCheck(path, patchMd5);
        if (result != ShareConstants.ERROR_PATCH_OK) {
            Log.w(TAG, "Default patch check failed: " + result);
            return result;
        }

        // 自定义检查 1：存储空间
        if (!hasEnoughStorage()) {
            Log.w(TAG, "Not enough storage space");
            return -100; // 自定义错误码
        }

        // 自定义检查 2：仅主进程允许加载补丁
        if (!ShareTinkerInternals.isInMainProcess(context)) {
            Log.w(TAG, "Not in main process, skip patch");
            return -101;
        }

        Log.i(TAG, "Patch check passed, allow patching");
        return ShareConstants.ERROR_PATCH_OK;
    }

    private boolean hasEnoughStorage() {
        try {
            StatFs stat = new StatFs(
                Environment.getDataDirectory().getPath());
            long available = stat.getAvailableBytes();
            return available > MIN_STORAGE_BYTES;
        } catch (Exception e) {
            return true; // 检查失败时默认允许
        }
    }
}
