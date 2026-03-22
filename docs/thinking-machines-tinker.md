# Thinking Machines Tinker SDK 调研报告

> Mira Murati 团队推出的 LLM 分布式训练 API

## 1. 概述

### 1.1 什么是 Thinking Machines Tinker？

Thinking Machines Tinker 是一个 **LLM 分布式微调训练 API**，由 Mira Murati（前 OpenAI CTO）和 John Schulman（前 OpenAI 联合创始人）共同创办的 Thinking Machines Lab 于 **2025 年 10 月** 推出。

核心理念：在本地 CPU 机器上编写训练循环，Tinker 负责所有分布式 GPU 基础设施。Andrej Karpathy 评价其"保留约 90% 的算法控制权，同时消除约 90% 的基础设施痛点"。

### 1.2 项目信息

| 属性 | 值 |
|------|-----|
| 官网 | https://thinkingmachines.ai/tinker/ |
| 文档 | https://tinker-docs.thinkingmachines.ai/ |
| GitHub SDK | https://github.com/thinking-machines-lab/tinker |
| Cookbook | https://github.com/thinking-machines-lab/tinker-cookbook |
| 许可证 | Apache-2.0（Cookbook） |
| 发布日期 | 2025 年 10 月 1 日 |

---

## 2. 核心架构与原理

### 2.1 设计哲学

- **API-first**：所有训练在服务端执行，本地代码仅发送 API 调用
- **仅 LoRA 微调**：使用低秩自适应（Low-Rank Adaptation），团队认为 LoRA 在大多数实际场景中与全参数微调效果相当
- **四个核心原语**：API 表面极简，仅 `forward_backward`、`optim_step`、`save_state`、`sample`
- **异步流水线**：操作可以异步排队，`forward_backward` 和 `optim_step` 可以流水线化执行

### 2.2 架构图

```
┌──────────────────────────┐
│    你的本地机器 (CPU)      │
│                          │
│  ┌────────────────────┐  │
│  │  训练循环代码        │  │
│  │  (Python)           │  │
│  └────────┬───────────┘  │
│           │ API 调用      │
└───────────┼──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Thinking Machines Cloud  │
│                          │
│  ┌────────────────────┐  │
│  │  Tinker API Server  │  │
│  └────────┬───────────┘  │
│           │              │
│  ┌────────▼───────────┐  │
│  │  分布式 GPU 集群     │  │
│  │  (自动管理)          │  │
│  └────────────────────┘  │
│                          │
│  ┌────────────────────┐  │
│  │  模型权重存储        │  │
│  │  (检查点管理)        │  │
│  └────────────────────┘  │
└──────────────────────────┘
```

### 2.3 与传统训练方式对比

| 特性 | 传统分布式训练 | Tinker API |
|------|--------------|-----------|
| GPU 管理 | 手动配置 | 自动 |
| 并行策略 | 手动实现 (FSDP/DeepSpeed) | 自动 |
| 代码复杂度 | 高（数千行） | 低（数十行） |
| 调试难度 | 难（分布式调试） | 易（本地调试） |
| 算法控制 | 完全控制 | ~90% 控制 |
| 基础设施控制 | 完全控制 | 无（API 抽象） |

---

## 3. 安装与配置

### 3.1 安装

```bash
# 安装核心 SDK
pip install tinker

# 安装 Cookbook（可选，包含示例和工具）
pip install tinker-cookbook
```

### 3.2 认证配置

```python
import tinker

# 创建服务客户端（需要 API Key）
service_client = tinker.ServiceClient()
```

---

## 4. 核心 API 详解

### 4.1 四个核心原语

#### `forward_backward` — 前向传播 + 反向传播

计算梯度并累积。

```python
# 创建训练客户端
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.2-1B",
    rank=32,  # LoRA 秩
)

# 执行前向传播和反向传播
result = training_client.forward_backward(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
    ],
    loss="cross_entropy",  # 内置损失函数
)
```

#### `optim_step` — 优化器步进

使用累积的梯度更新模型权重。

```python
training_client.optim_step(
    learning_rate=1e-4,
    beta1=0.9,
    beta2=0.95,
    eps=1e-8,
)
```

#### `save_state` / `load_state` — 状态管理

保存和恢复训练状态（检查点）。

```python
# 保存检查点
training_client.save_state("checkpoint_epoch_1")

# 恢复检查点
training_client.load_state("checkpoint_epoch_1")
```

#### `sample` — 推理采样

使用训练好的模型进行推理。

```python
# 获取采样客户端
sampling_client = training_client.save_weights_and_get_sampling_client(
    name="my_fine_tuned_model"
)

# 生成响应
response = sampling_client.sample(
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
    max_tokens=256,
)
print(response)
```

### 4.2 自定义损失函数

当内置损失函数（`cross_entropy`、`policy_gradient`）不够用时：

```python
# forward_backward_custom 允许任意可微损失函数
# 代价是需要额外一次前向传播
result = training_client.forward_backward_custom(
    messages=messages,
    custom_loss_fn=my_custom_loss,
)
```

### 4.3 异步流水线模式

高效训练的关键 — 让 `forward_backward` 和 `optim_step` 流水线化执行：

```python
import asyncio

async def train_step(data, training_client, lr, num_substeps, loss_fn):
    """流水线化训练步骤，最大化 GPU 利用率"""
    batches = split_into_batches(data, num_substeps)

    # 发送第一个 batch 的前向/反向传播
    fb_future = training_client.forward_backward_async(
        batches[0], loss=loss_fn
    )

    for i in range(1, len(batches)):
        # 等待上一个 forward_backward 完成
        await fb_future

        # 同时发送 optim_step 和下一个 forward_backward
        # 这两个操作可以在 GPU 上并行执行
        os_future = training_client.optim_step_async(learning_rate=lr)
        fb_future = training_client.forward_backward_async(
            batches[i], loss=loss_fn
        )

        # 等待 optim_step 完成
        await os_future

    # 处理最后一个 batch
    await fb_future
    await training_client.optim_step_async(learning_rate=lr)
```

---

## 5. 支持的模型

| 类别 | 模型 |
|------|------|
| 紧凑模型 | Llama-3.2-1B, Llama-3.2-3B |
| 中型模型 | Llama-3.1-8B, Qwen 系列 |
| 大型模型 | Llama-3.1-70B |
| MoE 大模型 | Qwen3-235B-A22B, Qwen3.5-397B-A17B |
| 视觉语言模型 | Qwen3-VL |

切换模型只需修改一个字符串：

```python
# 从 1B 切换到 70B，只需改 base_model 参数
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.1-70B",  # 只改这里
    rank=32,
)
```

---

## 6. 完整示例

### 6.1 监督微调 (SFT)

```python
import tinker

# 初始化
service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.2-1B",
    rank=32,
)

# 准备训练数据
train_data = [
    [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a high-level programming language."},
    ],
    [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is a subset of AI."},
    ],
    # ... 更多数据
]

# 训练循环
num_epochs = 3
learning_rate = 1e-4

for epoch in range(num_epochs):
    total_loss = 0.0

    for messages in train_data:
        # 前向 + 反向传播
        result = training_client.forward_backward(
            messages=messages,
            loss="cross_entropy",
        )
        total_loss += result.loss

        # 更新权重
        training_client.optim_step(
            learning_rate=learning_rate,
            beta1=0.9,
            beta2=0.95,
            eps=1e-8,
        )

    avg_loss = total_loss / len(train_data)
    print(f"Epoch {epoch + 1}/{num_epochs}, Avg Loss: {avg_loss:.4f}")

    # 保存检查点
    training_client.save_state(f"checkpoint_epoch_{epoch + 1}")

# 导出模型用于推理
sampling_client = training_client.save_weights_and_get_sampling_client(
    name="my_sft_model"
)

# 测试
response = sampling_client.sample(
    messages=[{"role": "user", "content": "What is deep learning?"}],
    temperature=0.7,
)
print(response)
```

### 6.2 强化学习 (RL) 训练

```python
import tinker

service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.1-8B",
    rank=64,
)

def reward_function(question, answer):
    """自定义奖励函数 — 例如数学正确性检查"""
    expected = eval_math(question)  # 获取正确答案
    if expected in answer:
        return 1.0  # 正确
    return -0.5  # 错误

# RL 训练循环
questions = ["What is 15 * 23?", "What is 127 + 896?", ...]

for step in range(1000):
    question = questions[step % len(questions)]

    # 用当前模型生成回答
    sampling_client = training_client.save_weights_and_get_sampling_client(
        name=f"step_{step}"
    )
    response = sampling_client.sample(
        messages=[{"role": "user", "content": question}],
        temperature=0.8,
    )

    # 计算奖励
    reward = reward_function(question, response)

    # 使用 policy gradient 损失进行训练
    training_client.forward_backward(
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": response},
        ],
        loss="policy_gradient",
        reward=reward,
    )

    training_client.optim_step(learning_rate=5e-5)

    if step % 100 == 0:
        print(f"Step {step}, Reward: {reward}")
        training_client.save_state(f"rl_checkpoint_{step}")
```

---

## 7. Cookbook 示例项目

Tinker Cookbook 提供了多个生产级训练模板：

| 示例 | 描述 | 适用场景 |
|------|------|---------|
| **Chat SFT** | 对话式监督微调 | 聊天机器人定制 |
| **Math Reasoning** | 数学推理 RL 训练 | 提升数学能力 |
| **Preference Learning** | 三阶段 RLHF (SFT→RM→PPO) | 对齐训练 |
| **Tool Use** | 工具调用检索增强训练 | 智能体训练 |
| **Prompt Distillation** | 大模型行为蒸馏 | 模型压缩 |
| **Multi-Agent** | 多智能体优化 | 多模型协作 |

---

## 8. 知名用户与成果

| 团队 | 应用 | 成果 |
|------|------|------|
| Princeton Goedel | 形式化定理证明 | 用 LoRA 仅 20% 数据达到全参微调效果 (88.1% pass@32 on MiniF2F) |
| Stanford Rotskoff Lab | 化学推理 (LLaMA 70B) | IUPAC 转化学式准确率从 15% 提升到 50% |
| Berkeley | 早期采用者 | — |
| Redwood Research | 早期采用者 | — |

---

## 9. 数据隐私与定价

- **数据隐私**：用户数据仅用于训练用户自己的模型，Thinking Machines 不使用客户数据训练自有模型
- **定价**：按百万 token 计费（基于计算量）
- **推理兼容**：训练后的模型暴露 OpenAI 兼容 HTTP 端点，可使用任何 OpenAI SDK 调用

---

## 10. 总结

Thinking Machines Tinker 代表了 LLM 训练基础设施的新范式：

- **极简 API**：4 个核心原语覆盖所有训练需求
- **零基础设施管理**：不需要管理 GPU、NCCL、分布式策略
- **完整算法控制**：研究者保留对训练循环、损失函数、优化器的完全控制
- **适合研究者**：特别适合 RL 研究、对齐训练等需要精细控制的场景

与传统 MLOps 平台（如 AWS SageMaker、Modal）相比，Tinker 的定位更偏向"研究者工具"而非"工程师平台"。
