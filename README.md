# Tinker SDK 全面调研报告与教程

> "Tinker SDK" 涵盖两个不同的项目，本仓库对两者都进行了全面调研。

本仓库包含对 **两个 Tinker SDK** 的全面调研报告、原理分析、使用教程和完整示例代码。

## 两个 Tinker SDK

| 项目 | 公司 | 领域 | 简介 |
|------|------|------|------|
| **Tencent Tinker** | 腾讯微信 | Android 热修复 | 开源的 Android 热补丁方案，支持代码/资源/So修复 |
| **Thinking Machines Tinker** | Thinking Machines Lab | LLM 分布式训练 | Mira Murati 团队的 LLM 微调训练 API |

## 目录

### Part 1: Tencent Tinker (Android 热修复)

- [调研报告](docs/research-report.md) — 架构原理、DexDiff 算法、与 Sophix/Robust/AndFix 对比
- [接入教程](docs/integration-guide.md) — 从零开始接入 Tinker 的完整步骤
- [API 参考](docs/api-reference.md) — Tinker 核心 API 详解
- [自定义扩展](docs/custom-extensions.md) — 高级自定义用法
- [示例项目](sample/) — 完整的 Android 示例项目代码

### Part 2: Thinking Machines Tinker (LLM 训练 API)

- [TM Tinker 调研报告](docs/thinking-machines-tinker.md) — 架构原理、核心 API、完整示例

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

### Tencent Tinker
- [Tinker GitHub](https://github.com/Tencent/tinker)
- [Tinker Wiki](https://github.com/Tencent/tinker/wiki)
- [TinkerPatch 补丁分发平台](http://www.tinkerpatch.com)

### Thinking Machines Tinker
- [官网](https://thinkingmachines.ai/tinker/)
- [文档](https://tinker-docs.thinkingmachines.ai/)
- [GitHub SDK](https://github.com/thinking-machines-lab/tinker)
- [Cookbook](https://github.com/thinking-machines-lab/tinker-cookbook)
