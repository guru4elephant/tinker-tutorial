# Tinker SDK 全面调研报告

## 1. 概述

### 1.1 什么是 Tinker？

Tinker 是 **腾讯微信团队** 开源的 Android 热修复（Hot-Fix）框架，支持在不重新安装 APK 的情况下，动态更新应用的：

- **Dex 代码**（Java/Kotlin 类）
- **Native 库**（.so 文件）
- **应用资源**（layout、drawable、values 等）

Tinker 已在 **微信** 数十亿设备上稳定运行，是目前 Android 平台最成熟、功能最全面的开源热修复方案之一。

### 1.2 项目信息

| 属性 | 值 |
|------|-----|
| GitHub 地址 | https://github.com/Tencent/tinker |
| Stars | 17.8k+ |
| 开源协议 | BSD 3-Clause |
| 最新版本 | v1.9.15.2 (2025年7月) |
| 语言构成 | Java (92.8%)、Groovy (6.5%) |
| 支持平台 | Android 2.X ~ 14+ |

### 1.3 核心优势

1. **全面修复能力**：同时支持代码、资源、So 库修复
2. **补丁包小**：采用 DexDiff 算法，差量补丁体积极小
3. **开发透明**：对业务代码无侵入，开发调试流程不受影响
4. **Gradle 深度集成**：自动完成补丁构建、签名、ProGuard 适配
5. **稳定可靠**：经过微信数十亿用户验证，兼容性极强
6. **完全开源**：基础功能完全免费

---

## 2. 核心架构与原理

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                  Tinker 架构                      │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  Patch 生成   │  │  Patch 分发   │              │
│  │  (编译时)     │  │  (服务端)     │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                      │
│         ▼                  ▼                      │
│  ┌──────────────────────────────────┐            │
│  │         Patch 验证与合成          │            │
│  │    (PatchListener + PatchService) │            │
│  └──────────────┬───────────────────┘            │
│                  │                                │
│         ┌───────┼───────┐                        │
│         ▼       ▼       ▼                        │
│  ┌─────────┐ ┌─────┐ ┌──────┐                   │
│  │ DexDiff │ │ BSP │ │ Res  │                    │
│  │ 合成    │ │iff  │ │ 合成 │                    │
│  │         │ │ So  │ │      │                    │
│  └────┬────┘ └──┬──┘ └──┬───┘                   │
│       │         │       │                        │
│       ▼         ▼       ▼                        │
│  ┌──────────────────────────────────┐            │
│  │       TinkerLoader (加载)         │            │
│  │  ClassLoader Hook + Resource Hook │            │
│  └──────────────────────────────────┘            │
│                                                   │
└─────────────────────────────────────────────────┘
```

### 2.2 Dex 修复原理

Tinker 采用 **类加载方案 (ClassLoader)**，而非底层替换方案：

#### 2.2.1 补丁生成（编译时）

1. 使用自研 **DexDiff** 算法对比新旧 APK 的 dex 文件
2. 生成差量补丁（远小于完整 dex）
3. DexDiff 基于 dex 文件格式进行字节级别的差量计算

```
旧 APK (old.apk)  ─┐
                     ├─ DexDiff ─→ patch.dex (差量补丁)
新 APK (new.apk)  ─┘
```

**DexDiff 内部实现：** `DexPatchGenerator` 是入口类，它为 DEX 文件的每个 Section 初始化独立的 Diff 算法：

| Section Diff 算法 | 处理的 DEX Section |
|---|---|
| `StringDataSectionDiffAlgorithm` | 字符串常量池 |
| `TypeIdSectionDiffAlgorithm` | 类型 ID 表 |
| `ProtoIdSectionDiffAlgorithm` | 方法原型表 |
| `FieldIdSectionDiffAlgorithm` | 字段 ID 表 |
| `MethodIdSectionDiffAlgorithm` | 方法 ID 表 |
| `ClassDefSectionDiffAlgorithm` | 类定义表 |
| `TypeListSectionDiffAlgorithm` | 类型列表 |
| `AnnotationSetSectionDiffAlgorithm` | 注解集 |
| `ClassDataSectionDiffAlgorithm` | 类数据（字段/方法列表） |
| `CodeSectionDiffAlgorithm` | 字节码指令 |
| `DebugInfoItemSectionDiffAlgorithm` | 调试信息 |

生成的补丁文件包含：MAGIC 头、版本号、各 Section 的操作列表（删除、新增、替换），每个操作记录目标索引和数据。

```java
// DexDiff 使用示意
DexPatchGenerator generator = new DexPatchGenerator(oldDexFile, newDexFile);
generator.executeAndSaveTo(patchFile);
```

#### 2.2.2 补丁加载（运行时）

补丁加载分为两个阶段：**合成阶段**（后台进程）和**加载阶段**（主进程重启后）。

**合成阶段：**
1. `TinkerInstaller.onReceiveUpgradePatch()` 触发补丁请求
2. 请求经过 `PatchListener` 验证（签名、空间、版本等）
3. 在独立的 `:patch` 进程中，`TinkerPatchService` 执行 DexPatch 合成
4. 合成后的完整 dex 写入应用数据目录
5. `ResultService` 回调通知合成结果

**加载阶段（下次冷启动）：**
1. `TinkerApplication.onCreate()` 最先执行
2. `TinkerLoader.tryLoad()` 检查是否有已合成的补丁
3. 使用 ClassLoader 注入机制加载合成后的 dex

**Tinker 提供两种 ClassLoader 注入方式：**

| 方式 | 类名 | 原理 | 适用场景 |
|------|------|------|---------|
| **方式 A（默认）** | `NewClassLoaderInjector` | 创建新的 `TinkerClassLoader`，通过反射替换 `LoadedApk.mClassLoader` | 新版本推荐 |
| **方式 B（Legacy）** | `SystemClassLoaderAdder` | 反射修改现有 `PathClassLoader` 的 `dexElements` 数组 | 旧版本兼容 |

```java
// 方式 A 原理简化示意
// 创建包含合成 dex 的新 ClassLoader
TinkerClassLoader newLoader = new TinkerClassLoader(mergedDexPath, parent);
// 反射替换 LoadedApk 的 mClassLoader
LoadedApk loadedApk = getLoadedApk();
Field classLoaderField = loadedApk.getClass().getDeclaredField("mClassLoader");
classLoaderField.set(loadedApk, newLoader);
```

> **注意**：Tinker 的类加载方案需要 **冷启动（重启应用）** 后才能生效，不支持即时生效。

#### 2.2.3 崩溃保护机制

Tinker 内置了崩溃保护，防止坏补丁导致应用无限崩溃：

1. 每次加载补丁后启动，Tinker 在 SharedPreferences 中递增崩溃计数器
2. 如果应用在启动后 **10 秒内** 连续崩溃超过 **3 次**，判定为补丁导致的崩溃
3. 自动 **回滚补丁**（`cleanPatch`），恢复到基线版本
4. 成功运行超过阈值时间后，重置崩溃计数器

#### 2.2.4 为什么选择类加载方案？

| 特性 | 底层替换 (AndFix) | 类加载 (Tinker) |
|------|-------------------|-----------------|
| 即时生效 | ✅ | ❌ (需冷启动) |
| 兼容性 | 差（依赖 ART 内部结构） | 好 |
| 修复范围 | 仅方法替换 | 类级别替换 |
| 稳定性 | 低 | 高 |
| 新增类 | ❌ | ✅ |

### 2.3 资源修复原理

Tinker 采用 **全量替换** 策略修复资源：

1. 编译时对比新旧 APK 的资源文件，生成资源补丁
2. 运行时通过反射替换 `AssetManager`，加载新的资源包
3. 大文件使用 **BSDiff** 算法生成差量补丁，减小补丁体积（默认阈值 100KB）

```
资源修复流程：
1. 对比 resources.arsc → 生成差量
2. 对比其他资源文件 → 新增/修改的资源打入补丁
3. 运行时合成完整资源包
4. 反射替换 AssetManager 指向新资源包
```

### 2.4 So 库修复原理

Native 库修复采用 **替换加载** 策略：

1. 编译时使用 **BSDiff** 对比新旧 so 文件生成差量补丁
2. 运行时合成新的 so 文件
3. 通过两种方式加载：
   - **反射注入方式**：将补丁 so 路径注入到 `nativeLibraryDirectories`
   - **手动加载方式**：显式使用 `TinkerLoadLibrary.loadLibraryFromTinker()` 加载

### 2.5 补丁文件结构

```
patch_signed.apk
├── META-INF/          # 签名信息
├── assets/
│   ├── dex_meta.txt   # dex 补丁元数据
│   ├── so_meta.txt    # so 补丁元数据
│   ├── res_meta.txt   # 资源补丁元数据
│   └── package_meta.txt # 补丁包元数据 (tinkerId 等)
├── classes.dex        # dex 差量补丁
├── lib/               # so 差量补丁
│   └── armeabi-v7a/
│       └── libxxx.so
└── res/               # 资源补丁
    └── resources.apk
```

---

## 3. 与其他热修复方案对比

### 3.1 对比表

| 特性 | Tinker | Sophix | Robust | AndFix |
|------|--------|--------|--------|--------|
| **开发团队** | 腾讯微信 | 阿里云 | 美团 | 阿里支付宝 |
| **代码修复** | ✅ | ✅ | ✅ | ✅ |
| **资源修复** | ✅ | ✅ | ❌ | ❌ |
| **So 修复** | ✅ | ✅ | ❌ | ❌ |
| **即时生效** | ❌ | ✅ (小修改) | ✅ | ✅ |
| **修复粒度** | 类级别 | 方法/类级别 | 方法级别 | 方法级别 |
| **侵入性** | 低 (依赖侵入) | 无 | 高 (插桩) | 无 |
| **兼容性** | 优 | 优 | 优 | 差 |
| **开源** | ✅ | ❌ | ✅ | ✅ (已停更) |
| **费用** | 免费 | 商业收费 | 免费 | 免费 |
| **维护状态** | 活跃 | 活跃 | 活跃 | 已停更 (2016) |
| **补丁大小** | 小 | 小 | 较大 | 小 |
| **平台支持** | 2.X~14+ | 4.0~14+ | 4.0~14+ | 2.3~7.0 |

### 3.2 选型建议

| 场景 | 推荐方案 |
|------|---------|
| 需要全面修复能力 + 免费 | **Tinker** |
| 需要即时生效 + 简单集成 | **Sophix** (付费) |
| 只修复代码 + 追求稳定 | **Robust** |
| 不推荐 | AndFix (已停更) |

### 3.3 各方案原理对比

```
┌─ 底层替换方案 ──────────────────────────────────┐
│ AndFix: Native 层指针替换 ArtMethod             │
│ Sophix: 整体替换 ArtMethod (改进版)              │
│ 优点: 即时生效  缺点: 兼容性差, 修复范围受限      │
└────────────────────────────────────────────────┘

┌─ 类加载方案 ───────────────────────────────────┐
│ Tinker: DexDiff + ClassLoader Hook              │
│ QZone: 插桩 + ClassLoader Hook                  │
│ 优点: 兼容性好, 修复范围广  缺点: 需要冷启动     │
└────────────────────────────────────────────────┘

┌─ Instant Run 方案 ─────────────────────────────┐
│ Robust: 编译时插桩代理                           │
│ 优点: 即时生效, 兼容性好  缺点: 包体积增大        │
└────────────────────────────────────────────────┘

┌─ 混合方案 ─────────────────────────────────────┐
│ Sophix: 底层替换 + 类加载 自动选择               │
│ 优点: 综合优势  缺点: 闭源, 商业收费              │
└────────────────────────────────────────────────┘
```

---

## 4. Tinker 组件模块

### 4.1 核心模块

| 模块 | 说明 |
|------|------|
| `tinker-android-lib` | 核心 SDK，包含补丁加载和合成逻辑 |
| `tinker-android-loader` | 补丁加载器，在应用启动最早期执行 |
| `tinker-android-anno` | 注解处理器，自动生成 Application 类 |
| `tinker-patch-gradle-plugin` | Gradle 插件，自动化补丁构建 |
| `tinker-patch-cli` | 命令行工具，用于非 Gradle 环境 |
| `tinker-commons` | 公共工具类 |
| `aosp-dexutils` | AOSP dex 处理工具 |
| `bsdiff-util` | BSDiff 差量算法工具 |

### 4.2 关键算法

#### DexDiff 算法

Tinker 自研的 dex 差量算法，针对 dex 文件格式优化：

- 基于 dex 文件内部结构（StringId、TypeId、MethodId、ClassDef 等 Section）逐段对比
- 相比通用 BSDiff，针对 dex 格式优化后差量更小
- 在微信实测中，补丁大小仅为 BSDiff 的 **1/5 到 1/10**

#### BSDiff 算法

用于 So 文件和大资源文件的差量计算：

- 通用的二进制差量算法
- 适合处理编译产物（so 文件等）的差量

---

## 5. 已知限制

### 5.1 功能限制

1. **不能修改 AndroidManifest.xml**：不能新增四大组件（Activity、Service、BroadcastReceiver、ContentProvider）
   - 1.9.0+ 支持新增 **非导出（non-exported）Activity**
2. **不支持即时生效**：需要冷启动后补丁才能生效
3. **不支持修改 RemoteView 相关资源**：桌面小部件、通知栏图标等
4. **Android N 轻微启动影响**：混合编译模式下有轻微的启动时间增加

### 5.2 平台限制

1. **Google Play 限制**：Google Play 开发者政策不推荐热修复
2. **部分三星 Android 5.0 设备不兼容**
3. **不支持 Instant Run**：开发时需关闭 Instant Run

### 5.3 开发限制

1. Application 类需要特殊处理（使用 ApplicationLike 代理）
2. 多进程场景需要额外处理
3. ProGuard 混淆需要保持 mapping 一致性

---

## 6. 生态系统

### 6.1 TinkerPatch 补丁分发平台

[TinkerPatch](http://www.tinkerpatch.com) 是第三方提供的补丁分发管理平台：

- 补丁 CDN 分发
- 灰度发布
- 补丁监控和统计
- 条件下发（版本、渠道、设备等）

### 6.2 社区与维护

- GitHub Issues 活跃维护
- Wiki 文档完善
- 示例项目 `tinker-sample-android` 持续更新

---

## 7. 总结

Tinker 是目前 Android 开源热修复领域功能最全面、稳定性最高的方案。虽然需要冷启动才能生效，但其全面的修复能力（代码+资源+So）、出色的兼容性和极小的补丁体积，使其成为大多数 Android 应用热修复的首选。

对于有预算的团队，可以考虑阿里的 Sophix 作为替代方案，它在即时生效和易用性方面更有优势，但需要商业付费。

对于只需要修复代码层面 bug 且要求即时生效的场景，美团的 Robust 是不错的选择。
