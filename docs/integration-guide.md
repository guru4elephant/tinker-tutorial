# Tinker 接入教程

> 从零开始接入 Tinker 热修复框架的完整步骤指南

## 1. 环境要求

- Android Studio 3.0+
- Gradle 4.1+
- minSdkVersion >= 14（推荐 >= 19）
- **关闭 Instant Run**（必须）

---

## 2. 添加依赖

### 2.1 项目根 build.gradle

```gradle
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:7.4.2'
        // 添加 Tinker Gradle 插件
        classpath 'com.tencent.tinker:tinker-patch-gradle-plugin:1.9.15.2'
    }
}
```

### 2.2 app/build.gradle

```gradle
apply plugin: 'com.android.application'

// 必须在 apply plugin: 'com.android.application' 之后
// 在文件最后添加
apply plugin: 'com.tencent.tinker.patch'

android {
    compileSdkVersion 33
    defaultConfig {
        applicationId "com.example.tinker"
        minSdkVersion 19
        targetSdkVersion 33
        versionCode 1
        versionName "1.0.0"

        // 推荐：开启 multiDex
        multiDexEnabled true
    }

    // 签名配置（补丁包需要与基线包使用相同签名）
    signingConfigs {
        release {
            storeFile file('keystore/release.jks')
            storePassword 'your_password'
            keyAlias 'your_alias'
            keyPassword 'your_password'
        }
    }

    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
            signingConfig signingConfigs.release
        }
        debug {
            signingConfig signingConfigs.release  // 调试时也建议用相同签名
        }
    }

    // 必须：关闭 Instant Run 相关设置
    dexOptions {
        jumboMode = true
    }
}

dependencies {
    // Tinker 核心库
    implementation 'com.tencent.tinker:tinker-android-lib:1.9.15.2'
    // Tinker 注解处理器（推荐方式）
    annotationProcessor 'com.tencent.tinker:tinker-android-anno:1.9.15.2'
    // MultiDex 支持
    implementation 'androidx.multidex:multidex:2.0.1'
}
```

---

## 3. 配置 tinkerPatch

在 `app/build.gradle` 中添加 tinkerPatch 配置块：

```gradle
def bakPath = file("${buildDir}/bakApk/")

// tinkerPatch 全局配置
tinkerPatch {
    // 基线包路径（构建补丁时需要指定）
    oldApk = "${bakPath}/app-release-0322-14-30-00.apk"

    // 是否忽略警告，建议 false
    ignoreWarning = false

    // 是否使用签名，建议 true
    useSign = true

    // ========== 编译相关配置 ==========
    buildConfig {
        // ProGuard mapping 文件路径（保证混淆一致性）
        applyMapping = "${bakPath}/app-release-0322-14-30-00-mapping.txt"

        // R.txt 文件路径（保证资源 ID 一致性）
        applyResourceMapping = "${bakPath}/app-release-0322-14-30-00-R.txt"

        // Tinker ID，用于匹配基线包和补丁包
        // 建议使用 git 版本号或构建编号
        tinkerId = "patch-1.0.0-base"

        // 是否保持 dex 分包方式不变
        keepDexApply = false

        // 是否支持加固（360加固等）
        isProtectedApp = false

        // 是否支持新增非导出 Activity（1.9.0+）
        supportHotplugComponent = false
    }

    // ========== Dex 相关配置 ==========
    dex {
        // dex 模式：raw 或 jar
        // raw：保持原始 dex 格式（推荐）
        // jar：将 dex 打包为 jar（minSdkVersion < 14 时使用）
        dexMode = "jar"

        // 需要处理的 dex 文件路径模式
        pattern = ["classes*.dex", "assets/secondary-dex-?.jar"]

        // 在补丁加载过程中使用的类（这些类不能被修复）
        // 必须包含以下类：
        loader = [
            "com.example.tinker.MyApplication",
            // 以下是 Tinker 内部类，必须包含
            // Tinker 会自动添加
        ]
    }

    // ========== So 库相关配置 ==========
    lib {
        // 需要处理的 so 文件路径模式
        pattern = ["lib/*/*.so"]
    }

    // ========== 资源相关配置 ==========
    res {
        // 需要处理的资源文件路径模式
        pattern = ["res/*", "assets/*", "resources.arsc", "AndroidManifest.xml"]

        // 忽略变更的资源（不会生成补丁）
        ignoreChange = ["assets/sample_meta.txt"]

        // 大文件使用 bsdiff 的阈值（KB）
        largeModSize = 100
    }

    // ========== 补丁包额外信息 ==========
    packageConfig {
        // 自定义字段，可在运行时通过 API 读取
        configField("patchMessage", "fix crash on launch")
        configField("platform", "all")
        configField("patchVersion", "1.0.1")
    }

    // ========== 7zip 压缩配置 ==========
    sevenZip {
        // 7zip 路径，用于压缩补丁包
        zipArtifact = "com.tencent.mm:SevenZip:1.1.10"
    }
}

// ========== 备份基线包任务 ==========
// 每次构建 Release 包时自动备份
android.applicationVariants.all { variant ->
    def taskName = variant.name

    tasks.all {
        if ("assemble${taskName.capitalize()}".equalsIgnoreCase(it.name)) {
            it.doLast {
                copy {
                    def date = new Date().format("MMdd-HH-mm-ss")
                    from "${buildDir}/outputs/apk/${taskName}"
                    into bakPath
                    rename { String fileName ->
                        fileName.replace("${project.name}-${taskName}",
                            "${project.name}-${taskName}-${date}")
                    }
                }
                // 同时备份 mapping 和 R.txt
                copy {
                    def date = new Date().format("MMdd-HH-mm-ss")
                    from "${buildDir}/outputs/mapping/${taskName}/mapping.txt"
                    into bakPath
                    rename { "app-${taskName}-${date}-mapping.txt" }
                }
                copy {
                    def date = new Date().format("MMdd-HH-mm-ss")
                    from "${buildDir}/intermediates/symbols/${taskName}/R.txt"
                    into bakPath
                    rename { "app-${taskName}-${date}-R.txt" }
                }
            }
        }
    }
}
```

---

## 4. 改造 Application

Tinker 需要对 Application 进行特殊处理，因为 Application 类在补丁加载之前就已经加载，所以 **Application 本身不能被热修复**。

### 4.1 方式一：注解方式（推荐）

使用 `@DefaultLifeCycle` 注解自动生成 Application 类。

**第一步：创建 ApplicationLike 类**

```java
package com.example.tinker;

import android.app.Application;
import android.content.Context;
import android.content.Intent;

import com.tencent.tinker.anno.DefaultLifeCycle;
import com.tencent.tinker.loader.app.DefaultApplicationLike;
import com.tencent.tinker.lib.tinker.TinkerInstaller;
import com.tencent.tinker.loader.shareutil.ShareConstants;

@DefaultLifeCycle(
    application = "com.example.tinker.MyApplication",  // 生成的 Application 类名
    flags = ShareConstants.TINKER_ENABLE_ALL,           // 支持所有类型修复
    loaderClass = "com.tencent.tinker.loader.TinkerLoader"
)
public class MyApplicationLike extends DefaultApplicationLike {

    public MyApplicationLike(Application application, int tinkerFlags,
            boolean tinkerLoadVerifyFlag, long applicationStartElapsedTime,
            long applicationStartMillisTime, Intent tinkerResultIntent) {
        super(application, tinkerFlags, tinkerLoadVerifyFlag,
              applicationStartElapsedTime, applicationStartMillisTime,
              tinkerResultIntent);
    }

    /**
     * 相当于 Application.attachBaseContext()
     * 在这里进行 MultiDex 和 Tinker 的初始化
     */
    @Override
    public void onBaseContextAttached(Context base) {
        super.onBaseContextAttached(base);

        // MultiDex 初始化（如果使用了 MultiDex）
        // MultiDex.install(base);

        // 安装 Tinker
        TinkerInstaller.install(this);
    }

    /**
     * 相当于 Application.onCreate()
     */
    @Override
    public void onCreate() {
        super.onCreate();

        // 在这里进行你的初始化操作
        // 注意：使用 getApplication() 代替 this
        // 例如：SomeSDK.init(getApplication());
    }
}
```

**第二步：在 AndroidManifest.xml 中声明**

```xml
<application
    android:name="com.example.tinker.MyApplication"
    android:allowBackup="true"
    android:icon="@mipmap/ic_launcher"
    android:label="@string/app_name"
    android:theme="@style/AppTheme">

    <!-- 你的 Activity 声明 -->

</application>
```

> 注意：`MyApplication` 是注解自动生成的类，不需要手动创建。

### 4.2 方式二：手动方式

如果不想使用注解，可以手动创建 Application 类。

```java
package com.example.tinker;

import com.tencent.tinker.loader.app.TinkerApplication;
import com.tencent.tinker.loader.shareutil.ShareConstants;

public class MyApplication extends TinkerApplication {

    public MyApplication() {
        super(
            ShareConstants.TINKER_ENABLE_ALL,            // tinkerFlags
            "com.example.tinker.MyApplicationLike",      // delegateClassName（必须用字符串）
            "com.tencent.tinker.loader.TinkerLoader",    // loaderClassName
            false                                        // tinkerLoadVerifyFlag
        );
    }
}
```

### 4.3 Application 改造注意事项

1. **不要在 Application 中直接引用 ApplicationLike 的类**，必须使用字符串形式的类名
2. 将所有原 Application 中的逻辑迁移到 **ApplicationLike**
3. 使用 `getApplication()` 代替 `this` 获取 Application 实例
4. `attachBaseContext` 逻辑迁移到 `onBaseContextAttached`
5. Application 类会被注解处理器自动生成，不要手动修改

---

## 5. 配置 ProGuard

如果开启了代码混淆，需要添加 Tinker 的 ProGuard 规则：

```proguard
# tinker-proguard-rules.pro

# Tinker 核心类
-keepattributes *Annotation*
-dontwarn com.tencent.tinker.loader.**
-keep public class * extends com.tencent.tinker.loader.app.TinkerApplication

# 保留 ApplicationLike 的子类
-keep public class * extends com.tencent.tinker.loader.app.DefaultApplicationLike

# Tinker 注解
-keep @com.tencent.tinker.anno.DefaultLifeCycle public class *
```

> Tinker Gradle 插件会自动添加大部分混淆规则，以上为补充规则。

---

## 6. 构建基线包

```bash
# 构建 Debug 基线包
./gradlew assembleDebug

# 构建 Release 基线包
./gradlew assembleRelease
```

构建完成后，基线包会自动备份到 `app/build/bakApk/` 目录：

```
app/build/bakApk/
├── app-release-0322-14-30-00.apk      # 基线 APK
├── app-release-0322-14-30-00-mapping.txt   # ProGuard 映射
└── app-release-0322-14-30-00-R.txt         # 资源 ID 映射
```

---

## 7. 修复 Bug 并构建补丁

### 7.1 修改代码

修复你需要修复的 Bug 或添加需要的功能。

### 7.2 配置基线包路径

在 `app/build.gradle` 中更新：

```gradle
tinkerPatch {
    oldApk = "${bakPath}/app-release-0322-14-30-00.apk"

    buildConfig {
        applyMapping = "${bakPath}/app-release-0322-14-30-00-mapping.txt"
        applyResourceMapping = "${bakPath}/app-release-0322-14-30-00-R.txt"
        tinkerId = "patch-1.0.0-patch1"
    }
}
```

### 7.3 构建补丁包

```bash
# 构建 Debug 补丁
./gradlew tinkerPatchDebug

# 构建 Release 补丁
./gradlew tinkerPatchRelease
```

### 7.4 补丁输出

补丁文件生成在 `app/build/outputs/tinkerPatch/` 目录：

```
app/build/outputs/tinkerPatch/release/
├── patch_unsigned.apk        # 未签名补丁
├── patch_signed.apk          # 已签名补丁
├── patch_signed_7zip.apk     # 7zip 压缩后的补丁（用于分发）
├── log.txt                   # 构建日志
├── dex_log.txt               # dex 差量日志
├── so_log.txt                # so 差量日志
└── tempPatchedDexes/          # 合成后的完整 dex（用于验证）
```

---

## 8. 加载补丁

### 8.1 本地测试

```bash
# 将补丁推送到设备
adb push app/build/outputs/tinkerPatch/debug/patch_signed_7zip.apk /sdcard/

# 启动应用并触发补丁加载
```

### 8.2 在代码中加载补丁

```java
// 在 Activity 中触发补丁加载
public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 加载本地补丁文件
        findViewById(R.id.btn_load_patch).setOnClickListener(v -> {
            String patchPath = Environment.getExternalStorageDirectory()
                .getAbsolutePath() + "/patch_signed_7zip.apk";
            TinkerInstaller.onReceiveUpgradePatch(getApplicationContext(), patchPath);
        });

        // 清除所有补丁
        findViewById(R.id.btn_clean_patch).setOnClickListener(v -> {
            Tinker.with(getApplicationContext()).cleanPatch();
        });
    }
}
```

### 8.3 补丁生效

调用 `onReceiveUpgradePatch` 后，Tinker 会：
1. 在后台 Service 中验证和合成补丁
2. 合成完成后，通过 `ResultService` 回调通知
3. **下次冷启动时**补丁生效

> 可以在 `ResultService` 中杀死进程以强制冷启动。

---

## 9. 多渠道/多 Flavor 构建

### 9.1 配置多 Flavor 基线包路径

```gradle
ext {
    // 指定包含所有 flavor 基线包的目录
    tinkerBuildFlavorDirectory = "${bakPath}/app-0322-14-30-00"
}
```

### 9.2 构建所有 Flavor 的补丁

```bash
# 构建所有 Flavor 的 Debug 补丁
./gradlew tinkerPatchAllFlavorDebug

# 构建所有 Flavor 的 Release 补丁
./gradlew tinkerPatchAllFlavorRelease
```

---

## 10. 命令行方式（不使用 Gradle 插件）

如果不使用 Gradle（如 Eclipse 或其他构建工具），可以使用命令行工具：

```bash
java -jar tinker-patch-cli.jar \
    -old old.apk \
    -new new.apk \
    -config tinker_config.xml \
    -out output_path
```

需要手动处理：
1. 在 AndroidManifest.xml 中插入 `TINKER_ID`
2. 配置 ProGuard 规则
3. 指定 Main Dex 类列表

---

## 11. 完整的工作流程

```
第一次发版：
1. 开发完成 → assembleRelease → 发布 APK
2. 备份 APK + mapping.txt + R.txt

发现 Bug，需要热修复：
3. 修复代码
4. 配置 tinkerPatch 指向基线包
5. tinkerPatchRelease → 生成补丁
6. 分发补丁（TinkerPatch 平台 / 自建后台 / 本地测试）
7. 客户端加载补丁
8. 用户冷启动后 Bug 修复生效
```

---

## 下一步

- [API 参考](api-reference.md) — 了解 Tinker 的所有 API
- [自定义扩展](custom-extensions.md) — 自定义补丁监听、结果处理等
- [示例项目](../sample/) — 查看完整的示例代码
