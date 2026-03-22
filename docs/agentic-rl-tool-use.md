# Agentic RL：多轮工具调用训练调研与教程

> 基于 Thinking Machines Tinker SDK 的多轮 Agent RL 训练

## 1. 概述

### 1.1 什么是 Agentic RL？

Agentic RL（智能体强化学习）是一种训练 LLM 在多轮交互中学会使用工具的方法。与单轮 SFT/RL 不同，Agentic RL 让模型在一个 **环境** 中进行多步交互：

```
传统单轮训练:
  用户 → 模型 → 回复（一次性完成）

Agentic RL 多轮训练:
  用户提问 → 模型思考 → 调用工具A → 获取结果 → 调用工具B → 获取结果 → 最终回答
  ↑ 每一步都有 token 级别的梯度，整个轨迹获得一个奖励信号
```

### 1.2 典型应用场景

| 场景 | 工具 | 奖励信号 |
|------|------|---------|
| **检索增强问答** | 搜索 API、知识库查询 | 答案正确性 |
| **代码调试** | 终端执行、测试运行 | 测试通过率 |
| **数学推理** | 计算器、符号计算 | 答案正确性 |
| **数据分析** | SQL 查询、Python 执行 | 结果准确性 |
| **多智能体博弈** | 对手模型 | 胜负结果 |

### 1.3 Tinker 的优势

Tinker 的 API 原生支持多轮 RL 训练，核心优势：

- **Env 抽象**：类似 OpenAI Gym 但专为 LLM 设计，操作 token 级别
- **异步流水线**：长轨迹、异构长度的 rollout 天然适合异步处理
- **GRPO 风格训练**：组内优势归一化，每个 prompt 采样多条轨迹
- **多智能体支持**：`EnvGroupBuilder` 支持同时构建多个环境实例

---

## 2. 核心架构

### 2.1 Env 接口

Tinker Cookbook 的 RL 环境基于 `Env` 接口，需要实现两个方法：

```python
class Env:
    """
    有状态的 RL 环境，单个 agent 与之交互。
    每个 episode 使用一个实例，用完即弃（无 reset）。
    """

    async def initial_observation(self) -> tuple[Observation, StopCondition]:
        """
        返回初始观测和停止条件。
        Observation: token 序列（环境给模型看的内容）
        StopCondition: 何时停止生成（如遇到特定 token）
        """
        ...

    async def step(self, action: Action) -> StepResult:
        """
        接收模型的动作（生成的 token 序列），返回：
        - 下一个观测（工具返回结果等）
        - 奖励
        - 是否结束
        - 停止条件
        """
        ...
```

> **关键设计**：`Env` 在 token 级别操作，而非字符串或消息级别。因为训练代码需要知道模型采样的确切 token 及其 log-prob。

### 2.2 支撑类

```python
class EnvGroupBuilder:
    """
    构建一组环境实例。
    用途：
    - 多智能体训练（多个 agent 在不同环境中交互）
    - 对比多个采样结果（GRPO 风格）
    """
    def build(self) -> list[Env]:
        ...

class RLDataset:
    """
    提供 EnvGroupBuilder 的批次。
    将数据集与环境解耦，比 OpenAI Gym 更模块化。
    """
    def get_batch(self) -> list[EnvGroupBuilder]:
        ...
```

### 2.3 Completer（策略执行器）

| 类型 | 用途 | 说明 |
|------|------|------|
| `TokenCompleter` | RL 训练 | 跟踪采样的 token 和 log-prob，用于策略梯度更新 |
| `MessageCompleter` | 采样/评估 | 返回结构化消息，用于 judge 模型或多智能体交互 |

### 2.4 Rollout 流程

```
1. env.initial_observation()           → 获取初始观测（如用户问题）
   ↓
2. policy(observation, stop_condition) → 模型生成动作（工具调用）
   ↓
3. env.step(action)                    → 环境执行工具，返回结果 + 奖励
   ↓
4. 重复 2-3 直到 done=True
   ↓
5. 收集整条 Trajectory → 计算 advantage → 更新策略
```

### 2.5 训练策略：GRPO 风格

Tinker Cookbook 使用 GRPO（Group Relative Policy Optimization）风格的训练：

1. 每个 prompt/任务复制 `group_size` 次，生成多条轨迹
2. 每批次收集 `group_size × batch_size` 条轨迹
3. 轨迹内所有奖励求和得到轨迹总奖励
4. 按组归一化：`advantage = reward - group_mean_reward`
5. 同一轨迹内所有 token 共享同一个 advantage
6. 使用 importance sampling 或 PPO 损失进行策略更新

---

## 3. 多轮训练的计算效率

### 3.1 Extension Property（扩展性质）

多轮对话中，每个新观测 **包含所有之前的观测作为前缀**，上下文单调增长：

```
Turn 1: [system + user_question]
Turn 2: [system + user_question + model_response_1 + tool_result_1]
Turn 3: [system + user_question + model_response_1 + tool_result_1 + model_response_2 + tool_result_2]
```

当此性质成立时，多个 timestep 可以合并为单个训练数据，计算复杂度从 O(T²) 降为 O(T)。

### 3.2 异步 RL

对于长轨迹和异构长度的 rollout（如多轮工具调用），异步 RL 特别合适：

```python
# 异步 rollout — 不同轨迹长度不同，无需等待最慢的
async def collect_rollouts(envs, policy, num_envs):
    tasks = [rollout_one_episode(env, policy) for env in envs]
    trajectories = await asyncio.gather(*tasks)
    return trajectories
```

---

## 4. Cookbook 示例项目

### 4.1 Tool Use（检索增强 RL）

训练 LLM 学会使用检索工具来回答问题：

```
tinker_cookbook/recipes/tool_use/
├── README.md
├── env.py              # 检索工具环境定义
├── train.py            # 训练入口
└── eval.py             # 评估脚本
```

运行方式：

```bash
python -m tinker_cookbook.recipes.tool_use.train \
    model_name=meta-llama/Llama-3.1-8B \
    learning_rate=4e-5 \
    max_tokens=2048
```

### 4.2 Twenty Questions（多智能体博弈）

一个多步 RL 环境，训练一个"提问者"agent 通过提问来猜测隐藏的单词：

- **提问者**（被训练的模型）：提出 yes/no 问题
- **回答者**（固定模型 Llama-3.1-8B-Instruct）：根据隐藏单词回答
- **奖励**：正确猜出单词 +1，否则 0

```
tinker_cookbook/recipes/multiplayer_rl/twenty_questions/
├── env.py              # 多智能体环境
├── train.py            # 训练入口
└── play.py             # 交互式调试（人类扮演策略）
```

运行方式：

```bash
# 训练
python -m tinker_cookbook.recipes.multiplayer_rl.twenty_questions.train

# 交互式调试环境
python -m tinker_cookbook.recipes.multiplayer_rl.twenty_questions.play
```

### 4.3 Harbor（终端 RL）

在沙箱终端中训练 agent 执行命令：

```
tinker_cookbook/recipes/distillation/
├── harbor_multiturn.py                         # Harbor 多轮环境
├── on_policy_distillation_harbor_multi_turn.py # Harbor + 蒸馏
└── harbor_multiturn_test.py                    # 测试
```

Harbor 环境特点：
- `HarborBashTool` 封装沙箱终端，agent 可以执行 bash 命令
- `HarborEnvGroupBuilder` 管理多个沙箱环境实例
- 支持与 on-policy distillation 结合（用教师模型监督 agent 行为）

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

### 4.4 Math Reasoning（数学推理 RL）

训练模型通过链式思考（CoT）来解决数学问题：

```bash
python -m tinker_cookbook.recipes.rl_basic \
    model_name=meta-llama/Llama-3.1-8B \
    learning_rate=4e-5 \
    max_tokens=256
```

使用 GSM8K 数据集，奖励函数验证最终答案的正确性。

### 4.5 KernelBench（GPU Kernel 生成）

社区项目：训练 LLM 生成高效的 GPU kernel 代码。

```
KernelBenchEnv 继承 Tinker 的 Env 基类，
输入: kernel 规格描述
输出: CUDA kernel 代码
奖励: 编译成功 + 性能基准测试结果
```

---

## 5. 实战：构建自定义工具调用环境

> 完整代码见 [examples/agentic_rl_tool_use.py](../examples/agentic_rl_tool_use.py)

以下是一个简化的工具调用 RL 训练示例，展示如何训练 LLM 学会调用计算器工具来解决数学问题：

### 5.1 定义工具

```python
import re
import json

# 可用工具定义
TOOLS = {
    "calculator": {
        "description": "Perform arithmetic calculations",
        "usage": 'calculator(expression) — e.g., calculator("15 * 23")',
    },
    "lookup_constant": {
        "description": "Look up mathematical constants",
        "usage": 'lookup_constant(name) — e.g., lookup_constant("pi")',
    },
}

CONSTANTS = {"pi": "3.14159265", "e": "2.71828183", "sqrt2": "1.41421356"}


def execute_tool(tool_name, argument):
    """执行工具调用并返回结果"""
    if tool_name == "calculator":
        try:
            # 安全的数学表达式求值
            result = eval(argument, {"__builtins__": {}}, {})
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"
    elif tool_name == "lookup_constant":
        value = CONSTANTS.get(argument.strip().lower())
        return f"Value: {value}" if value else f"Error: Unknown constant '{argument}'"
    return f"Error: Unknown tool '{tool_name}'"
```

### 5.2 定义环境

```python
SYSTEM_PROMPT = """You are a math assistant with access to tools.

Available tools:
- calculator(expression): Perform arithmetic calculations
- lookup_constant(name): Look up mathematical constants (pi, e, sqrt2)

To use a tool, write: <tool>tool_name(argument)</tool>
After receiving the tool result, provide your final answer as: <answer>NUMBER</answer>

Think step by step, use tools when needed, then give your final answer."""


class MathToolEnv:
    """简化的多轮数学工具环境"""

    def __init__(self, question, expected_answer, max_turns=5):
        self.question = question
        self.expected_answer = expected_answer
        self.max_turns = max_turns
        self.turn = 0
        self.history = []

    def initial_observation(self):
        """返回初始 prompt"""
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self.question},
        ]

    def step(self, model_response):
        """
        处理模型的回复：
        - 如果包含 <tool>...</tool>，执行工具并返回结果
        - 如果包含 <answer>...</answer>，提取答案并计算奖励
        - 否则继续对话
        """
        self.turn += 1
        self.history.append({"role": "assistant", "content": model_response})

        # 检查是否有工具调用
        tool_match = re.search(r'<tool>(\w+)\((.+?)\)</tool>', model_response)
        if tool_match:
            tool_name = tool_match.group(1)
            argument = tool_match.group(2).strip('"\'')
            tool_result = execute_tool(tool_name, argument)

            observation = {"role": "user", "content": f"Tool result: {tool_result}"}
            self.history.append(observation)

            done = self.turn >= self.max_turns
            reward = 0.0  # 中间步骤无奖励
            return observation, reward, done

        # 检查是否有最终答案
        answer_match = re.search(r'<answer>(.*?)</answer>', model_response)
        if answer_match:
            predicted = answer_match.group(1).strip()
            is_correct = abs(float(predicted) - float(self.expected_answer)) < 0.01
            reward = 1.0 if is_correct else -0.5
            return None, reward, True  # episode 结束

        # 既没有工具调用也没有答案 → 继续，轻微惩罚
        observation = {
            "role": "user",
            "content": "Please use a tool or provide your final answer with <answer>NUMBER</answer>.",
        }
        self.history.append(observation)
        done = self.turn >= self.max_turns
        reward = -0.1 if done else 0.0  # 超时惩罚
        return observation, reward, done
```

### 5.3 训练循环

```python
import tinker

service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="meta-llama/Llama-3.1-8B",
    rank=64,
)

# 训练任务
tasks = [
    {"question": "What is 127 * 389?", "answer": "49403"},
    {"question": "What is pi * 100?", "answer": "314.159265"},
    {"question": "What is (sqrt2 + e) * 10?", "answer": "41.3249539"},
    {"question": "What is 2^10 + 3^5?", "answer": "1267"},
    # ... 更多任务
]

num_steps = 200
learning_rate = 4e-5

for step in range(num_steps):
    task = tasks[step % len(tasks)]
    env = MathToolEnv(task["question"], task["answer"], max_turns=5)

    # 获取初始观测
    messages = env.initial_observation()
    total_reward = 0.0
    trajectory_messages = list(messages)  # 累积完整对话

    # 多轮交互循环
    done = False
    while not done:
        # 模型生成回复
        sampler = training_client.save_weights_and_get_sampling_client(
            name=f"step_{step}_turn_{env.turn}"
        )
        response = sampler.sample(
            messages=trajectory_messages,
            temperature=0.8,
            max_tokens=512,
        )

        # 环境处理回复
        observation, reward, done = env.step(response)
        total_reward += reward

        # 更新对话历史
        trajectory_messages.append({"role": "assistant", "content": response})
        if observation:
            trajectory_messages.append(observation)

    # 用完整轨迹训练
    training_client.forward_backward(
        messages=trajectory_messages,
        loss="policy_gradient",
        reward=total_reward,
    )

    training_client.optim_step(learning_rate=learning_rate)

    if (step + 1) % 20 == 0:
        print(f"Step {step + 1}/{num_steps}, Reward: {total_reward:.2f}")
        training_client.save_state(f"agent_checkpoint_{step + 1}")
```

---

## 6. 真实案例

### 6.1 Berkeley SkyRL — 多智能体多工具 RL

- **场景**：异步 off-policy RL，多 agent 多轮工具调用
- **工具**：Tinker API 的灵活性使异步 RL 训练可行
- **成果**：SkyRL-SQL-7B 仅用 653 个样本，在 Text-to-SQL 上超过 GPT-4o 和 o4-mini
- **集成**：2026 年 2 月，SkyRL 正式集成 Harbor，支持训练终端使用 agent

### 6.2 Redwood Research — 长上下文 AI 控制

- **场景**：RL 训练 Qwen3-32B 执行长上下文 AI 控制任务
- **挑战**：多节点训练扩展一直是障碍
- **方案**：Tinker 抽象了分布式训练复杂性

### 6.3 KernelBench — GPU Kernel 生成

- **场景**：训练 LLM 生成高效 CUDA kernel
- **环境**：`KernelBenchEnv` 继承 Tinker 的 `Env` 基类
- **奖励**：编译成功 + 性能基准测试

---

## 7. 与其他框架对比

| 特性 | Tinker Cookbook | veRL | OpenRL | TRL |
|------|---------------|------|--------|-----|
| **多轮 RL** | 原生支持 | 支持 | 有限 | 有限 |
| **工具调用训练** | 内置 recipe | 需自建 | 需自建 | 不支持 |
| **多智能体** | 内置 | 有限 | 支持 | 不支持 |
| **异步 RL** | 支持 | 支持 | 有限 | 不支持 |
| **基础设施管理** | 零（API） | 需自建 | 需自建 | 需自建 |
| **Token 级别 Env** | 是 | 否 | 否 | 否 |
| **Extension Property 优化** | 是（O(T)） | 否 | 否 | 否 |

---

## 8. 最佳实践

### 8.1 环境设计

1. **明确工具协议**：在 system prompt 中定义清晰的工具调用格式（如 `<tool>...</tool>`）
2. **限制最大轮次**：防止无限循环，设置 `max_turns`（推荐 5-10）
3. **中间步骤奖励**：仅在 episode 结束时给予最终奖励，中间步骤奖励为 0
4. **超时惩罚**：轻微惩罚未在规定轮次内完成的轨迹

### 8.2 训练配置

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `group_size` | 4-16 | 每个 prompt 的采样数量（GRPO） |
| `max_tokens` | 2048-4096 | 多轮交互需要更长的上下文 |
| `temperature` | 0.8-1.0 | 鼓励探索 |
| `learning_rate` | 1e-5 ~ 5e-5 | 多轮 RL 用较小的学习率 |
| `lora_rank` | 32-128 | 工具调用比分类需要更大的 rank |

### 8.3 调试技巧

- 使用 `play.py` 风格的脚本，人工扮演策略与环境交互，检查奖励函数是否合理
- 先用小模型（1B/3B）快速验证环境逻辑，再切换到大模型
- 监控每轮的平均工具调用次数和成功率

---

## 参考资源

- [Tinker RL 文档](https://tinker-docs.thinkingmachines.ai/rl)
- [Tinker RL Environments 文档](https://tinker-docs.thinkingmachines.ai/rl/rl-envs)
- [Tinker Cookbook GitHub](https://github.com/thinking-machines-lab/tinker-cookbook)
- [Tinker Cookbook: Tool Use Recipe](https://github.com/thinking-machines-lab/tinker-cookbook/tree/main/tinker_cookbook/recipes/tool_use)
- [Tinker Cookbook: Twenty Questions](https://github.com/thinking-machines-lab/tinker-cookbook/tree/main/tinker_cookbook/recipes/multiplayer_rl/twenty_questions)
- [SkyRL GitHub](https://github.com/NovaSky-AI/SkyRL)
- [KernelBench-Tinker](https://github.com/ScalingIntelligence/kernelbench-tinker)
