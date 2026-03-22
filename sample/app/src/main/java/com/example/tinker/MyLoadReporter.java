package com.example.tinker;

import android.content.Context;
import android.util.Log;

import com.tencent.tinker.lib.reporter.DefaultLoadReporter;
import com.tencent.tinker.loader.shareutil.ShareConstants;

import java.io.File;

/**
 * 自定义补丁加载报告器
 *
 * 在每次应用启动加载补丁时回调
 * 可以在此处添加监控上报逻辑
 */
public class MyLoadReporter extends DefaultLoadReporter {

    private static final String TAG = "TinkerDemo";

    public MyLoadReporter(Context context) {
        super(context);
    }

    @Override
    public void onLoadResult(File patchDirectory, int loadCode, long cost) {
        super.onLoadResult(patchDirectory, loadCode, cost);

        switch (loadCode) {
            case ShareConstants.ERROR_LOAD_OK:
                Log.i(TAG, "Patch loaded successfully, cost: " + cost + "ms");
                break;
            default:
                Log.w(TAG, "Patch load failed, code: " + loadCode
                    + ", cost: " + cost + "ms");
                break;
        }
    }

    @Override
    public void onLoadException(Throwable e, int errorCode) {
        super.onLoadException(e, errorCode);
        Log.e(TAG, "Patch load exception, code: " + errorCode, e);
        // 上报异常到监控平台
    }

    @Override
    public void onLoadFileMd5Mismatch(File file, int fileType) {
        super.onLoadFileMd5Mismatch(file, fileType);
        Log.e(TAG, "MD5 mismatch: " + file.getPath()
            + ", type: " + fileType);
    }
}
