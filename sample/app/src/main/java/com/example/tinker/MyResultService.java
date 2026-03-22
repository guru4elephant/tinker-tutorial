package com.example.tinker;

import android.content.SharedPreferences;
import android.util.Log;

import com.tencent.tinker.lib.service.DefaultTinkerResultService;
import com.tencent.tinker.lib.service.PatchResult;
import com.tencent.tinker.loader.shareutil.ShareTinkerInternals;

/**
 * 自定义补丁合成结果处理 Service
 *
 * 在补丁合成完成后被调用（运行在 :patch 进程中）
 *
 * 补丁生效策略：
 * - 策略一：立即杀掉进程重启（用户体验差，但最快）
 * - 策略二：标记已就绪，等应用切到后台时重启（推荐）
 * - 策略三：什么都不做，等用户自然重启应用
 */
public class MyResultService extends DefaultTinkerResultService {

    private static final String TAG = "TinkerDemo";

    @Override
    public void onPatchResult(PatchResult result) {
        if (result == null) {
            Log.e(TAG, "PatchResult is null!");
            return;
        }

        Log.i(TAG, "Patch result - success: " + result.isSuccess);
        Log.i(TAG, "Patch result - path: " + result.rawPatchFilePath);
        Log.i(TAG, "Patch result - cost: " + result.costTime + "ms");

        if (!result.isSuccess) {
            Log.e(TAG, "Patch merge failed!");
            return;
        }

        // 补丁合成成功！

        // === 策略二（推荐）：标记补丁已就绪 ===
        SharedPreferences sp = getSharedPreferences("tinker_patch",
            MODE_PRIVATE);
        sp.edit()
            .putBoolean("patch_ready", true)
            .putLong("patch_time", System.currentTimeMillis())
            .apply();

        Log.i(TAG, "Patch merged successfully, waiting for app restart");

        // === 策略一（可选）：立即杀掉进程 ===
        // 取消注释以下代码启用立即重启
        // ShareTinkerInternals.killAllOtherProcess(getApplicationContext());
        // android.os.Process.killProcess(android.os.Process.myPid());
    }
}
