# Tinker SDK 全面调研报告与教程

> Tencent Tinker — 微信官方 Android 热修复解决方案

本仓库包含对 Tinker SDK 的全面调研报告、原理分析、使用教程和完整示例代码。

## 目录

- [调研报告](docs/research-report.md) — Tinker SDK 全面调研，包括架构原理、与竞品对比
- [接入教程](docs/integration-guide.md) — 从零开始接入 Tinker 的完整步骤
- [API 参考](docs/api-reference.md) — Tinker 核心 API 详解
- [自定义扩展](docs/custom-extensions.md) — 高级自定义用法
- [示例项目](sample/) — 完整的示例项目代码

## 快速开始

```gradle
// 项目根 build.gradle
buildscript {
    dependencies {
        classpath 'com.tencent.tinker:tinker-patch-gradle-plugin:1.9.15.2'
    }
}

// app/build.gradle
dependencies {
    annotationProcessor 'com.tencent.tinker:tinker-android-anno:1.9.15.2'
    implementation 'com.tencent.tinker:tinker-android-lib:1.9.15.2'
}
apply plugin: 'com.tencent.tinker.patch'
```

## 参考资源

- [Tinker GitHub](https://github.com/Tencent/tinker)
- [Tinker Wiki](https://github.com/Tencent/tinker/wiki)
- [TinkerPatch 补丁分发平台](http://www.tinkerpatch.com)
