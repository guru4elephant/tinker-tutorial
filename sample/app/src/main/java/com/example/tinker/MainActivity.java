package com.example.tinker;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.tencent.tinker.lib.tinker.Tinker;
import com.tencent.tinker.lib.tinker.TinkerInstaller;
import com.tencent.tinker.loader.shareutil.ShareTinkerInternals;

import java.io.File;

/**
 * Tinker 热修复 Demo 主界面
 *
 * 功能：
 * 1. 显示当前 Tinker 状态（是否已安装、是否已加载补丁）
 * 2. 加载本地补丁文件
 * 3. 清除已加载的补丁
 * 4. 杀掉进程使补丁生效
 * 5. 展示一个可以被"修复"的 Bug 方法
 */
public class MainActivity extends AppCompatActivity {

    private static final String TAG = "TinkerDemo";
    private static final int REQUEST_PERMISSION = 100;

    private TextView tvStatus;
    private TextView tvBugDemo;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        requestPermissions();
        updateStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }

    private void initViews() {
        tvStatus = findViewById(R.id.tv_status);
        tvBugDemo = findViewById(R.id.tv_bug_demo);

        // 加载补丁按钮
        Button btnLoadPatch = findViewById(R.id.btn_load_patch);
        btnLoadPatch.setOnClickListener(v -> loadPatch());

        // 清除补丁按钮
        Button btnCleanPatch = findViewById(R.id.btn_clean_patch);
        btnCleanPatch.setOnClickListener(v -> cleanPatch());

        // 杀掉进程按钮
        Button btnKillProcess = findViewById(R.id.btn_kill_process);
        btnKillProcess.setOnClickListener(v -> killProcess());

        // 展示 Bug 方法
        Button btnShowBug = findViewById(R.id.btn_show_bug);
        btnShowBug.setOnClickListener(v -> showBugResult());
    }

    /**
     * 加载本地补丁
     * 实际项目中补丁通常从服务器下载到本地，然后调用此方法
     */
    private void loadPatch() {
        // 补丁文件路径（实际使用时从服务器下载到此路径）
        String patchPath = Environment.getExternalStorageDirectory()
            .getAbsolutePath() + "/patch_signed_7zip.apk";

        File patchFile = new File(patchPath);
        if (!patchFile.exists()) {
            Toast.makeText(this, "补丁文件不存在: " + patchPath, Toast.LENGTH_LONG).show();
            Log.e(TAG, "Patch file not found: " + patchPath);
            return;
        }

        Log.i(TAG, "Loading patch from: " + patchPath);
        Toast.makeText(this, "开始加载补丁...", Toast.LENGTH_SHORT).show();

        // 发起补丁请求，Tinker 会在后台 Service 中合成补丁
        TinkerInstaller.onReceiveUpgradePatch(getApplicationContext(), patchPath);
    }

    /**
     * 清除所有已加载的补丁
     */
    private void cleanPatch() {
        Tinker tinker = Tinker.with(getApplicationContext());
        tinker.cleanPatch();
        Toast.makeText(this, "补丁已清除，需要重启生效", Toast.LENGTH_SHORT).show();
        updateStatus();
    }

    /**
     * 杀掉进程使补丁生效
     */
    private void killProcess() {
        ShareTinkerInternals.killAllOtherProcess(getApplicationContext());
        android.os.Process.killProcess(android.os.Process.myPid());
    }

    /**
     * 这是一个包含 "Bug" 的方法
     * 通过热修复可以修改这个方法的返回值
     *
     * 修复前：返回 "这里有一个 Bug! 1 + 1 = 3"
     * 修复后：返回 "Bug 已修复! 1 + 1 = 2"
     */
    private String getBuggyResult() {
        // ===== 修复前的代码 =====
        int result = 1 + 1 + 1;  // Bug: 多加了一个 1
        return "这里有一个 Bug! 1 + 1 = " + result;

        // ===== 修复后应改为 =====
        // int result = 1 + 1;
        // return "Bug 已修复! 1 + 1 = " + result;
    }

    private void showBugResult() {
        String result = getBuggyResult();
        tvBugDemo.setText(result);
        Log.i(TAG, result);
    }

    /**
     * 更新界面上的 Tinker 状态信息
     */
    private void updateStatus() {
        StringBuilder sb = new StringBuilder();

        Tinker tinker = Tinker.with(getApplicationContext());
        sb.append("Tinker 已安装: ").append(tinker.isTinkerInstalled()).append("\n");
        sb.append("补丁已加载: ").append(tinker.isTinkerLoaded()).append("\n");

        if (tinker.isTinkerLoaded()) {
            var loadResult = tinker.getTinkerLoadResultIfPresent();
            if (loadResult != null) {
                sb.append("基线 TinkerId: ").append(loadResult.getTinkerID()).append("\n");
                sb.append("补丁 TinkerId: ").append(loadResult.getNewTinkerID()).append("\n");

                String msg = loadResult.getPackageConfigByName("patchMessage");
                if (msg != null && !msg.isEmpty()) {
                    sb.append("补丁说明: ").append(msg).append("\n");
                }

                String ver = loadResult.getPackageConfigByName("patchVersion");
                if (ver != null && !ver.isEmpty()) {
                    sb.append("补丁版本: ").append(ver).append("\n");
                }
            }
        } else {
            sb.append("当前无补丁加载\n");
        }

        tvStatus.setText(sb.toString());
    }

    private void requestPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (ContextCompat.checkSelfPermission(this,
                    Manifest.permission.READ_EXTERNAL_STORAGE)
                    != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.READ_EXTERNAL_STORAGE},
                    REQUEST_PERMISSION);
            }
        }
    }
}
