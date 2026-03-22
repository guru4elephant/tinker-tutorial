# On-Policy Distillation 调研与教程

> 基于 Thinking Machines Tinker SDK 的 On-Policy 蒸馏技术

## 1. 什么是 On-Policy Distillation？

On-Policy Distillation（在策略蒸馏）是一种 LLM 知识蒸馏训练范式：

- **学生模型**（小模型）在自己的策略下生成轨迹（即"on-policy"采样）
- **教师模型**（大模型）对学生生成的轨迹提供 token 级别的概率分布监督
- 学生通过最小化与教师的 **逆向 KL 散度（Reverse KL Divergence）** 来更新参数

### 与传统 Off-Policy 蒸馏的区别

```
Off-Policy Distillation（传统 SFT 蒸馏）:
  教师模型生成数据 → 学生模型在教师数据上做 SFT
  问题：学生学习的是教师常走的路径，不是自己常走的路径 → 复合误差

On-Policy Distillation:
  学生模型自己生成数据 → 教师模型对学生轨迹评分 → 学生最小化 KL 散度
  优势：学生在自己会遇到的状态上学习 → 避免复合误差
```

| 特性 | Off-Policy (SFT) | On-Policy Distillation |
|------|-------------------|----------------------|
| **数据来源** | 教师模型生成 | 学生模型生成 |
| **训练方式** | 标准交叉熵 SFT | 逆向 KL 散度优化 |
| **复合误差** | 严重（分布偏移） | 轻微（on-policy 采样） |
| **教师推理成本** | 需要生成完整文本 | 仅需一次前向传播（log-prob） |
| **计算效率** | 较低 | FLOPs 降低 9-30x |
| **效果** | 基线 | 通常显著更优 |

---

## 2. 核心原理

### 2.1 灵感来源：DAGGER 算法

On-Policy Distillation 的灵感来自模仿学习中的 **DAGGER（Dataset Aggregation）** 算法：

1. 学生在自己的策略下生成轨迹
2. 教师对学生访问的状态提供反馈
3. 学生根据反馈更新策略
4. 迭代执行

Thinking Machines Lab 在 DAGGER 的基础上，结合了 Agarwal et al.、Gu et al. 和 Qwen3 团队的先前工作。

### 2.2 逆向 KL 散度（Reverse KL）

On-Policy Distillation 使用 **per-token 逆向 KL 散度** 作为损失函数：

```
Loss = KL(π_student ‖ π_teacher) = Σ_t π_student(a_t|s_t) * log(π_student(a_t|s_t) / π_teacher(a_t|s_t))
```

其中：
- `π_student(a_t|s_t)` 是学生模型在状态 s_t 下生成 token a_t 的概率
- `π_teacher(a_t|s_t)` 是教师模型在相同状态下的概率
- 当学生行为与教师完全一致时，KL = 0

#### 为什么用逆向 KL 而不是正向 KL？

| 特性 | 正向 KL `KL(teacher‖student)` | 逆向 KL `KL(student‖teacher)` |
|------|------------------------------|-------------------------------|
| **行为** | Mean-seeking（均值追踪） | Mode-seeking（模式追踪） |
| **效果** | 学生尝试覆盖教师的所有模式 | 学生集中学习教师的主要行为模式 |
| **鲁棒性** | 容易被"hack" | 不可被"hack"（低 KL 一定对应正确行为） |
| **与 RL 的兼容性** | 弱 | 强（天然兼容策略梯度框架） |

逆向 KL 的关键优势：
- **不可被 hack**：低 KL 一定意味着学生真正学到了教师的行为
- **Mode-seeking**：学生学习教师的核心行为，而非分散注意力
- **与 RL 天然兼容**：可以作为 RL 训练中 KL 正则化项的直接替换

### 2.3 与 RL 的关系：一行代码的改动

On-Policy Distillation 的实现可以看作 **RL + KL 正则化** 的特殊情况：

```
标准 RL with KL：
  reward = task_reward - β * KL(π_student ‖ π_reference)

On-Policy Distillation：
  reward = 0 - β * KL(π_student ‖ π_teacher)
  ↕  仅将 reference model 替换为 teacher model，去掉 task reward
```

因此，Thinking Machines 团队指出：**在已有的 RL 实现上，on-policy distillation 可能只是一行代码的改动** — 将正则化模型从 reference model 替换为 teacher model。

---

## 3. Tinker SDK 中的实现

### 3.1 核心训练流程

```python
import tinker
import asyncio

async def on_policy_distillation_step(
    training_client,
    teacher_client,
    prompts,
    temperature=1.0,
    kl_penalty_coef=1.0,
):
    """单步 on-policy distillation"""

    for prompt in prompts:
        # 1. 学生模型生成轨迹（on-policy 采样）
        student_sampling = training_client.save_weights_and_get_sampling_client(
            name="student_current"
        )
        student_response = student_sampling.sample(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )

        # 2. 构造完整对话
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": student_response},
        ]

        # 3. 使用 KL 散度损失进行训练
        #    Tinker 内部会计算学生和教师的 log-prob，然后优化逆向 KL
        result = await training_client.forward_backward_async(
            data=messages,
            loss_fn="importance_sampling",  # 用于 on-policy distillation
        )

    # 4. 更新学生模型权重
    await training_client.optim_step_async(learning_rate=1e-4)
```

### 3.2 使用 Cookbook 的完整实现

Tinker Cookbook 提供了生产级的 on-policy distillation 实现：

```bash
# 安装
pip install tinker tinker-cookbook

# 运行 on-policy distillation（以 DeepMath 数据集为例）
python -m tinker_cookbook.recipes.distillation.on_policy_distillation \
    model_name=Qwen/Qwen3-8B-Base \
    teacher_model=Qwen/Qwen3-32B \
    dataset=deepmath \
    learning_rate=1e-4 \
    groups_per_batch=512 \
    lora_rank=128 \
    kl_penalty_coef=1.0 \
    temperature=1.0 \
    max_tokens=4096 \
    wandb_project=my_distillation
```

#### Cookbook 关键参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model_name` | `Qwen/Qwen3-8B-Base` | 学生模型 |
| `teacher_model` | `Qwen/Qwen3-8B` | 教师模型 |
| `lora_rank` | 128 | LoRA 秩（推荐 8/32/128） |
| `learning_rate` | 1e-4 | 学习率 |
| `groups_per_batch` | 1024 | 每批次的 prompt 组数 |
| `group_size` | 4 | 每个 prompt 的采样数量 |
| `kl_penalty_coef` | 1.0 | KL 惩罚系数 β |
| `kl_discount_factor` | 0.0 | KL 折扣因子（一般不需要调） |
| `temperature` | 1.0 | 采样温度 |
| `max_tokens` | 4096 | 最大生成长度 |
| `loss_fn` | `importance_sampling` | 损失函数类型 |
| `dataset` | `deepmath` | 数据集（`deepmath` 或 `tulu3`） |
| `eval_every` | 20 | 每 N 步评估一次 |
| `save_every` | 20 | 每 N 步保存检查点 |

### 3.3 Cookbook 代码结构

```
tinker_cookbook/recipes/distillation/
├── on_policy_distillation.py           # 主入口：单数据集 on-policy 蒸馏
├── on_policy_multi_teacher.py          # 多教师模型蒸馏
├── on_policy_distillation_harbor_multi_turn.py  # 多轮工具调用场景的蒸馏
├── off_policy_reasoning.py             # 对照：off-policy SFT 基线
├── harbor_multiturn.py                 # 多轮对话环境定义
└── harbor_multiturn_test.py            # 测试
```

### 3.4 多教师蒸馏

Tinker Cookbook 支持从多个教师模型同时蒸馏：

```python
# 配置多个数据集，每个数据集有独立的教师模型
dataset_configs = [
    DistillationDatasetConfig(
        dataset_builder=math_dataset_builder,
        teacher_config=TeacherConfig(base_model="Qwen/Qwen3-32B"),
        groups_per_batch=512,
    ),
    DistillationDatasetConfig(
        dataset_builder=chat_dataset_builder,
        teacher_config=TeacherConfig(base_model="Qwen/Qwen3-8B"),
        groups_per_batch=64,
    ),
]
```

### 3.5 多轮工具调用场景的蒸馏

对于需要工具调用（tool-use）的场景，Cookbook 提供了 Harbor 环境的蒸馏实现：

```bash
python -m tinker_cookbook.recipes.distillation.on_policy_distillation_harbor_multi_turn \
    model_name=Qwen/Qwen3-8B-Base \
    teacher_model=Qwen/Qwen3-32B \
    learning_rate=1e-4 \
    lora_rank=8 \
    max_turns=10 \
    max_tokens=2048 \
    kl_penalty_coef=1.0
```

关键特点：
- 环境提供的 token（system prompt、工具返回结果）在训练时被 **mask 掉**
- 只有学生生成的 token 参与损失计算
- 唯一的监督信号来自最小化与教师模型的 KL 散度

---

## 4. 实战效果

### 4.1 基准测试结果

Thinking Machines 使用 Tinker 复现了 Qwen3 的 on-policy distillation 结果：

| 设置 | AIME'24 得分 | 说明 |
|------|-------------|------|
| Off-Policy SFT（基线） | ~45% | 标准教师数据 SFT |
| On-Policy Distillation (rank-8) | ~55% | 低秩 LoRA |
| On-Policy Distillation (rank-32) | ~60% | 中等 LoRA |
| On-Policy Distillation (rank-128) | **~65%** | 仅 100 步训练 |

### 4.2 计算效率

与 off-policy SFT 相比，on-policy distillation 实现了显著的计算效率提升：

- **FLOPs 降低 9-30x**：因为教师模型只需要计算 log-prob（一次前向传播），不需要生成完整文本
- 学生模型（较小）生成轨迹，教师模型（较大）仅做评分
- 部分/截断轨迹也可以使用，不需要等待完整轨迹生成

### 4.3 已知限制

- **仅支持同架构蒸馏**：Tinker 目前只支持同一模型家族内的蒸馏（如 Qwen → Qwen），不支持跨架构（如 DeepSeek → Qwen）
- **需要教师模型在线**：教师模型需要在 Tinker 平台上可用
- `kl_discount_factor` 增大（优化折扣未来 KL）一般不会提升效果

---

## 5. 从零开始的简化示例

> 完整代码见 [examples/on_policy_distillation.py](../examples/on_policy_distillation.py)

以下是一个简化的 on-policy distillation 训练脚本，展示核心思路：

```python
"""
简化的 On-Policy Distillation 示例

学生模型：Qwen3-8B-Base
教师模型：Qwen3-32B
数据：数学推理 prompt
"""
import tinker
import asyncio

async def main():
    service_client = tinker.ServiceClient()

    # 创建学生训练客户端
    student = service_client.create_lora_training_client(
        base_model="Qwen/Qwen3-8B-Base",
        rank=128,
    )

    # 教师模型（用于计算 log-prob）
    teacher = service_client.create_lora_training_client(
        base_model="Qwen/Qwen3-32B",
        rank=0,  # 教师不训练，rank=0
    )

    # 训练 prompt
    prompts = [
        "Solve: What is the sum of all prime numbers less than 20?",
        "Prove that the square root of 2 is irrational.",
        "Find the derivative of f(x) = x^3 * sin(x).",
        # ... 更多数学 prompt
    ]

    num_steps = 100
    learning_rate = 1e-4
    kl_coef = 1.0

    for step in range(num_steps):
        prompt = prompts[step % len(prompts)]

        # 1. 学生模型 on-policy 采样
        student_sampler = student.save_weights_and_get_sampling_client(
            name=f"student_step_{step}"
        )
        student_response = student_sampler.sample(
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=4096,
        )

        # 2. 用学生的轨迹构造训练数据
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": student_response},
        ]

        # 3. forward_backward 计算梯度
        #    内部计算学生和教师的 token-level KL 散度
        result = student.forward_backward(
            messages=messages,
            loss="cross_entropy",  # 简化版用 cross_entropy
            # 生产版本使用 importance_sampling + KL penalty
        )

        # 4. 更新学生权重
        student.optim_step(
            learning_rate=learning_rate,
            beta1=0.9,
            beta2=0.95,
        )

        if (step + 1) % 20 == 0:
            print(f"Step {step + 1}/{num_steps}, Loss: {result.loss:.4f}")
            student.save_state(f"distill_checkpoint_{step + 1}")

    print("On-policy distillation complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. 最佳实践

### 6.1 超参数推荐

| 场景 | 学生模型 | 教师模型 | LoRA Rank | LR | Batch Size |
|------|---------|---------|-----------|-----|-----------|
| 数学推理 | Qwen3-8B-Base | Qwen3-32B | 128 | 1e-4 | 512 |
| 通用对话 | Qwen3-8B-Base | Qwen3-8B | 128 | 1e-4 | 64 |
| 工具调用 | Qwen3-8B-Base | Qwen3-32B | 8 | 1e-4 | 64 |

### 6.2 常见问题

**Q: 什么时候用 on-policy 而不是 off-policy？**
- 当你需要最佳效果且计算预算充足时，用 on-policy
- 当你需要快速实验且不追求极致效果时，off-policy SFT 也可以

**Q: 教师模型和学生模型必须是同一架构吗？**
- 是的，Tinker 目前仅支持同一模型家族内的蒸馏（如 Qwen → Qwen）

**Q: LoRA rank 选多大？**
- rank=128 效果最好，但 rank=8 也能达到不错的效果
- 推荐从 rank=32 开始实验

**Q: kl_discount_factor 需要调吗？**
- 一般不需要，默认值 0.0 即可
- Thinking Machines 团队未观察到增大此值有明显提升

---

## 参考资源

- [Thinking Machines Blog: On-Policy Distillation](https://thinkingmachines.ai/blog/on-policy-distillation/)
- [Tinker Cookbook: Distillation Recipes](https://github.com/thinking-machines-lab/tinker-cookbook/tree/main/tinker_cookbook/recipes/distillation)
- [Tinker API 文档](https://tinker-docs.thinkingmachines.ai/)
- [Qwen3 On-Policy Distillation 论文](https://arxiv.org/abs/2306.13649)
- [DAGGER 算法原始论文](https://arxiv.org/abs/1011.0686)
