"""
Tinker SDK Agentic RL 多轮工具调用训练示例

训练 LLM 在多轮交互中学会使用计算器和常量查询工具来解决数学问题。
模型通过 RL（策略梯度）学习何时调用工具、如何解析结果、何时给出最终答案。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python agentic_rl_tool_use.py

参考:
    - Tinker RL 文档: https://tinker-docs.thinkingmachines.ai/rl
    - Cookbook Tool Use: https://github.com/thinking-machines-lab/tinker-cookbook
"""

import tinker
import re
import random

# ============================================================
# 1. 工具定义
# ============================================================

CONSTANTS = {
    "pi": "3.14159265",
    "e": "2.71828183",
    "sqrt2": "1.41421356",
    "sqrt3": "1.73205081",
    "phi": "1.61803399",  # 黄金比例
}


def execute_tool(tool_name, argument):
    """安全地执行工具调用"""
    if tool_name == "calculator":
        try:
            # 仅允许安全的数学运算
            allowed = {
                "__builtins__": {},
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "pow": pow,
            }
            result = eval(argument, allowed, {})
            return f"{result}"
        except Exception as e:
            return f"Error: invalid expression — {e}"

    elif tool_name == "lookup_constant":
        name = argument.strip().lower().strip("'\"")
        value = CONSTANTS.get(name)
        if value:
            return value
        return f"Error: unknown constant '{name}'. Available: {', '.join(CONSTANTS)}"

    return f"Error: unknown tool '{tool_name}'"


# ============================================================
# 2. 环境定义
# ============================================================

SYSTEM_PROMPT = """You are a math assistant with access to tools.

Available tools:
- calculator(expression): Perform arithmetic. Example: <tool>calculator(15 * 23)</tool>
- lookup_constant(name): Look up constants (pi, e, sqrt2, sqrt3, phi). Example: <tool>lookup_constant(pi)</tool>

Instructions:
1. Think about what you need to calculate.
2. Use tools by writing <tool>tool_name(argument)</tool>.
3. After receiving tool results, continue reasoning or use more tools.
4. When ready, give your final answer as <answer>NUMBER</answer>.

Always use tools for calculations. Do not guess."""


class MathToolEnv:
    """
    多轮数学工具调用环境。

    模型在环境中进行多步交互：
    1. 接收数学问题
    2. 选择调用工具（calculator / lookup_constant）
    3. 获取工具结果
    4. 继续推理或给出最终答案
    5. 根据答案正确性获得奖励
    """

    def __init__(self, question, expected_answer, max_turns=5):
        self.question = question
        self.expected_answer = float(expected_answer)
        self.max_turns = max_turns
        self.turn = 0
        self.tool_calls = 0

    def initial_observation(self):
        """初始观测：system prompt + 用户问题"""
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self.question},
        ]

    def step(self, model_response):
        """
        处理模型回复，返回 (observation, reward, done)

        - 包含 <tool>: 执行工具，返回结果
        - 包含 <answer>: 检查答案，返回奖励
        - 其他: 提示模型使用工具或给答案
        """
        self.turn += 1

        # 检查工具调用
        tool_match = re.search(r"<tool>(\w+)\((.+?)\)</tool>", model_response)
        if tool_match:
            tool_name = tool_match.group(1)
            argument = tool_match.group(2).strip("'\"")
            result = execute_tool(tool_name, argument)
            self.tool_calls += 1

            observation = {
                "role": "user",
                "content": f"Tool result: {result}\n\nContinue reasoning or provide your final answer with <answer>NUMBER</answer>.",
            }
            done = self.turn >= self.max_turns
            reward = 0.0  # 中间步骤无奖励
            if done:
                reward = -0.3  # 用完所有轮次但没给答案
            return observation, reward, done

        # 检查最终答案
        answer_match = re.search(r"<answer>([\d\.\-\+e]+)</answer>", model_response)
        if answer_match:
            try:
                predicted = float(answer_match.group(1))
                # 相对误差 < 1% 视为正确
                if self.expected_answer != 0:
                    rel_error = abs(predicted - self.expected_answer) / abs(
                        self.expected_answer
                    )
                    is_correct = rel_error < 0.01
                else:
                    is_correct = abs(predicted) < 0.01

                reward = 1.0 if is_correct else -0.5
                return None, reward, True
            except ValueError:
                return None, -0.5, True

        # 既无工具调用也无答案
        done = self.turn >= self.max_turns
        observation = {
            "role": "user",
            "content": "Please use a tool with <tool>tool_name(argument)</tool> or provide your answer with <answer>NUMBER</answer>.",
        }
        reward = -0.3 if done else -0.05  # 轻微惩罚无效回复
        return observation, reward, done


# ============================================================
# 3. 训练任务
# ============================================================

TRAIN_TASKS = [
    {"question": "What is 127 * 389?", "answer": "49403"},
    {"question": "What is pi * 100?", "answer": "314.159265"},
    {"question": "What is 2^10 + 3^5?", "answer": "1267"},
    {"question": "What is (pi + e) * 10?", "answer": "58.5987448"},
    {"question": "What is sqrt2 * sqrt3?", "answer": "2.44948975"},
    {"question": "What is 999 * 999?", "answer": "998001"},
    {"question": "What is phi^2 - phi?", "answer": "1.0"},
    {"question": "What is 12345 + 67890?", "answer": "80235"},
    {"question": "What is 1024 / 16?", "answer": "64"},
    {"question": "What is pi * e?", "answer": "8.53973422"},
]

EVAL_TASKS = [
    {"question": "What is 256 * 512?", "answer": "131072"},
    {"question": "What is pi * sqrt2?", "answer": "4.44288294"},
    {"question": "What is 7^4 + 3^6?", "answer": "3130"},
]

# ============================================================
# 4. 配置
# ============================================================

BASE_MODEL = "meta-llama/Llama-3.1-8B"
LORA_RANK = 64
NUM_STEPS = 200
LEARNING_RATE = 4e-5
TEMPERATURE = 0.8
MAX_TURNS = 5
GROUP_SIZE = 4  # 每个 prompt 采样 4 条轨迹（GRPO 风格）


def run_episode(sampler, env):
    """运行一个完整的 episode，返回 (完整对话, 总奖励, 工具调用次数)"""
    messages = env.initial_observation()
    trajectory = list(messages)
    total_reward = 0.0

    done = False
    while not done:
        response = sampler.sample(
            messages=trajectory,
            temperature=TEMPERATURE,
            max_tokens=512,
        )

        observation, reward, done = env.step(response)
        total_reward += reward

        trajectory.append({"role": "assistant", "content": response})
        if observation:
            trajectory.append(observation)

    return trajectory, total_reward, env.tool_calls


def main():
    print(f"Model: {BASE_MODEL}")
    print(f"LoRA rank: {LORA_RANK}, LR: {LEARNING_RATE}")
    print(f"Max turns per episode: {MAX_TURNS}, Group size: {GROUP_SIZE}")
    print("=" * 60)

    service_client = tinker.ServiceClient()
    training_client = service_client.create_lora_training_client(
        base_model=BASE_MODEL,
        rank=LORA_RANK,
    )

    # ============================================================
    # 训练循环
    # ============================================================
    print(f"\nStarting agentic RL training: {NUM_STEPS} steps")
    print("-" * 60)

    total_correct = 0
    total_episodes = 0

    for step in range(NUM_STEPS):
        task = TRAIN_TASKS[step % len(TRAIN_TASKS)]

        # GRPO: 每个 prompt 采样多条轨迹
        group_rewards = []
        group_trajectories = []

        sampler = training_client.save_weights_and_get_sampling_client(
            name=f"step_{step}"
        )

        for g in range(GROUP_SIZE):
            env = MathToolEnv(task["question"], task["answer"], max_turns=MAX_TURNS)
            trajectory, reward, tool_calls = run_episode(sampler, env)
            group_rewards.append(reward)
            group_trajectories.append(trajectory)
            total_episodes += 1
            if reward > 0:
                total_correct += 1

        # GRPO 风格：计算组内 advantage
        mean_reward = sum(group_rewards) / len(group_rewards)

        # 对每条轨迹用 advantage 进行训练
        for trajectory, reward in zip(group_trajectories, group_rewards):
            advantage = reward - mean_reward

            training_client.forward_backward(
                messages=trajectory,
                loss="policy_gradient",
                reward=advantage,
            )

        training_client.optim_step(
            learning_rate=LEARNING_RATE,
            beta1=0.9,
            beta2=0.95,
            eps=1e-8,
        )

        # 定期打印进度
        if (step + 1) % 10 == 0:
            avg_reward = sum(group_rewards) / len(group_rewards)
            accuracy = total_correct / total_episodes * 100
            print(
                f"Step {step + 1}/{NUM_STEPS}, "
                f"Group Avg Reward: {avg_reward:.2f}, "
                f"Running Accuracy: {accuracy:.1f}%"
            )

        # 定期保存检查点
        if (step + 1) % 50 == 0:
            training_client.save_state(f"agent_checkpoint_{step + 1}")

    # ============================================================
    # 评估
    # ============================================================
    print("\n" + "=" * 60)
    print("Evaluation")
    print("=" * 60)

    eval_sampler = training_client.save_weights_and_get_sampling_client(
        name="agent_final"
    )

    eval_correct = 0
    for task in EVAL_TASKS:
        env = MathToolEnv(task["question"], task["answer"], max_turns=MAX_TURNS)
        trajectory, reward, tool_calls = run_episode(eval_sampler, env)

        status = "PASS" if reward > 0 else "FAIL"
        print(f"[{status}] {task['question']}")
        print(f"  Expected: {task['answer']}, Reward: {reward:.2f}, Tool calls: {tool_calls}")

        # 打印模型的推理过程
        for msg in trajectory:
            if msg["role"] == "assistant":
                print(f"  Model: {msg['content'][:100]}...")
                break

        if reward > 0:
            eval_correct += 1

    print(f"\nEval Accuracy: {eval_correct}/{len(EVAL_TASKS)} ({eval_correct / len(EVAL_TASKS) * 100:.0f}%)")


if __name__ == "__main__":
    main()
