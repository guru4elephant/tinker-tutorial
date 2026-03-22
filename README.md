# Thinking Machines Tinker SDK 调研与教程

> Mira Murati 团队推出的 LLM 分布式微调训练 API — 全面调研、原理分析与实战示例

## 什么是 Tinker？

Thinking Machines Tinker 是由 Thinking Machines Lab（Mira Murati & John Schulman 联合创办）推出的 **LLM 分布式微调训练 API**。

核心理念：在本地 CPU 机器上编写训练循环，Tinker 负责所有分布式 GPU 基础设施。

| 属性 | 值 |
|------|-----|
| 官网 | https://thinkingmachines.ai/tinker/ |
| 文档 | https://tinker-docs.thinkingmachines.ai/ |
| GitHub SDK | https://github.com/thinking-machines-lab/tinker |
| Cookbook | https://github.com/thinking-machines-lab/tinker-cookbook |

## 目录

### 调研报告

- [全面调研报告](docs/research-report.md) — 架构原理、核心 API、与其他平台对比、完整使用教程
- [On-Policy Distillation 调研](docs/on-policy-distillation.md) — 在策略蒸馏原理、逆向 KL 散度、Cookbook 实战
- [Agentic RL 多轮工具调用](docs/agentic-rl-tool-use.md) — Env 接口、多轮训练、GRPO、Cookbook 实战案例
- [多模态 VLM RL 训练](docs/vlm-rl-training.md) — Qwen3-VL 视觉模型微调、ImageChunk API、模型列表说明

### 示例代码

- [文本分类 (情感分析)](examples/text_classification.py) — 用 LLM + SFT 实现文本分类
- [监督微调 (SFT)](examples/sft_training.py) — 基础 SFT 训练循环
- [强化学习 (RL)](examples/rl_training.py) — Policy Gradient + 自定义奖励函数
- [On-Policy Distillation](examples/on_policy_distillation.py) — 大模型蒸馏到小模型（逆向 KL 散度）
- [Agentic RL 工具调用](examples/agentic_rl_tool_use.py) — 多轮 RL 训练 agent 使用工具（GRPO 风格）
- [VLM RL 训练](examples/vlm_rl_training.py) — 视觉语言模型 RL 微调（图表推理 + GRPO）

## 快速开始

```bash
pip install tinker
export TINKER_API_KEY="your-api-key"
```

```python
import tinker

service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.2-1B",
    rank=32,
)

# 训练
result = training_client.forward_backward(
    messages=[
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI is artificial intelligence."},
    ],
    loss="cross_entropy",
)
training_client.optim_step(learning_rate=1e-4)

# 推理
sampling_client = training_client.save_weights_and_get_sampling_client(name="my_model")
response = sampling_client.sample(
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
)
print(response)
```

## 支持的模型

| 类别 | 模型 |
|------|------|
| 紧凑模型 | Llama-3.2-1B, Llama-3.2-3B |
| 中型模型 | Llama-3.1-8B, Qwen 系列 |
| 大型模型 | Llama-3.1-70B |
| MoE 大模型 | Qwen3-235B-A22B, Qwen3.5-397B-A17B |
| 视觉语言模型 | Qwen3-VL |

## 核心 API（4 个原语）

| API | 功能 | 说明 |
|-----|------|------|
| `forward_backward()` | 前向 + 反向传播 | 计算梯度并累积 |
| `optim_step()` | 优化器步进 | 使用累积梯度更新权重 |
| `save_state()` / `load_state()` | 检查点管理 | 保存/恢复训练状态 |
| `sample()` | 推理采样 | 使用训练后的模型生成文本 |

## 适用场景

| 场景 | 示例 |
|------|------|
| 对话机器人定制 | SFT 微调 + 领域数据 |
| 文本分类 | 情感分析、主题分类、意图识别 |
| 数学推理增强 | RL 训练 + 正确性奖励 |
| 对齐训练 | RLHF (SFT → RM → PPO) |
| Agentic RL 工具调用 | 多轮 RL 训练 agent 使用检索/计算/终端工具 |
| 模型蒸馏 | 大模型行为蒸馏到小模型 |
| On-Policy Distillation | 学生 on-policy 采样 + 教师 KL 监督（FLOPs 降低 9-30x） |
| 多模态视觉 RL | VLM 图表推理、GUI Agent、视觉数学（Qwen3-VL） |

> **注意**：Tinker 只支持[预定义的模型列表](https://tinker-docs.thinkingmachines.ai/model-lineup)，不支持上传自定义模型。训练好的 LoRA 权重可下载导出。

## 参考资源

- [Tinker 官网](https://thinkingmachines.ai/tinker/)
- [Tinker 文档](https://tinker-docs.thinkingmachines.ai/)
- [Tinker SDK GitHub](https://github.com/thinking-machines-lab/tinker)
- [Tinker Cookbook GitHub](https://github.com/thinking-machines-lab/tinker-cookbook)
- [On-Policy Distillation Blog](https://thinkingmachines.ai/blog/on-policy-distillation/)
- [Tinker GA + Vision Input Blog](https://thinkingmachines.ai/blog/tinker-general-availability/)
