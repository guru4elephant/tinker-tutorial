"""
Tinker SDK 强化学习 (RL) 训练示例

使用 policy gradient 和自定义奖励函数训练数学推理能力。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python rl_training.py
"""

import tinker
import re

# ============================================================
# 配置
# ============================================================

BASE_MODEL = "meta-llama/Llama-3.1-8B"
LORA_RANK = 64
NUM_STEPS = 200
LEARNING_RATE = 5e-5

# ============================================================
# 训练数据 & 奖励函数
# ============================================================

# 简单数学题（带标准答案）
math_problems = [
    {"question": "What is 15 * 23?", "answer": "345"},
    {"question": "What is 127 + 896?", "answer": "1023"},
    {"question": "What is 1000 - 457?", "answer": "543"},
    {"question": "What is 144 / 12?", "answer": "12"},
    {"question": "What is 25 * 25?", "answer": "625"},
    {"question": "What is 999 + 1?", "answer": "1000"},
    {"question": "What is 81 / 9?", "answer": "9"},
    {"question": "What is 37 * 11?", "answer": "407"},
]


def extract_number(text):
    """从模型回答中提取数字"""
    numbers = re.findall(r'\b\d+\b', text)
    return numbers[-1] if numbers else None


def reward_function(expected_answer, model_response):
    """奖励函数：正确 +1.0，错误 -0.5"""
    extracted = extract_number(model_response)
    if extracted == expected_answer:
        return 1.0
    return -0.5


def main():
    print(f"Initializing Tinker with {BASE_MODEL}...")
    service_client = tinker.ServiceClient()
    training_client = service_client.create_lora_training_client(
        base_model=BASE_MODEL,
        rank=LORA_RANK,
    )

    print(f"Starting RL training: {NUM_STEPS} steps")
    print("-" * 60)

    total_reward = 0.0
    correct_count = 0

    for step in range(NUM_STEPS):
        problem = math_problems[step % len(math_problems)]

        # 用当前模型生成回答
        sampling_client = training_client.save_weights_and_get_sampling_client(
            name=f"rl_step_{step}"
        )
        response = sampling_client.sample(
            messages=[{"role": "user", "content": problem["question"]}],
            temperature=0.8,
            max_tokens=64,
        )

        # 计算奖励
        reward = reward_function(problem["answer"], response)
        total_reward += reward
        if reward > 0:
            correct_count += 1

        # 使用 policy gradient 训练
        training_client.forward_backward(
            messages=[
                {"role": "user", "content": problem["question"]},
                {"role": "assistant", "content": response},
            ],
            loss="policy_gradient",
            reward=reward,
        )

        training_client.optim_step(learning_rate=LEARNING_RATE)

        # 定期打印进度
        if (step + 1) % 20 == 0:
            avg_reward = total_reward / (step + 1)
            acc = correct_count / (step + 1) * 100
            print(f"Step {step + 1}/{NUM_STEPS}, "
                  f"Avg Reward: {avg_reward:.3f}, "
                  f"Accuracy: {acc:.1f}%")

        # 定期保存检查点
        if (step + 1) % 50 == 0:
            training_client.save_state(f"rl_checkpoint_{step + 1}")

    print("\nRL training complete!")
    print(f"Final Accuracy: {correct_count / NUM_STEPS * 100:.1f}%")


if __name__ == "__main__":
    main()
