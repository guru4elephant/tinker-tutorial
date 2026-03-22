"""
Tinker SDK 多模态视觉语言模型 (VLM) RL 训练示例

训练 Qwen3-VL 通过强化学习来提升视觉推理能力。
示例场景：VLM 看图表/图形并回答数学相关问题，通过 RL 学习推理过程。

由于图像数据需要实际文件，本示例使用模拟的图像数据来展示 API 用法。
实际使用时请替换为真实图像。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python vlm_rl_training.py

参考:
    - Tinker Vision Blog: https://thinkingmachines.ai/blog/tinker-general-availability/
    - Tinker Rendering Docs: https://tinker-docs.thinkingmachines.ai/rendering
    - Cookbook VLM Classifier: tinker_cookbook/recipes/vlm_classifier/
"""

import tinker
from tinker.types import ImagePart, TextPart
import re
import random
import struct

# ============================================================
# 1. 配置
# ============================================================

# 视觉模型（MoE，活跃参数 3B，性价比高）
BASE_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
LORA_RANK = 32
NUM_STEPS = 100
LEARNING_RATE = 5e-5
TEMPERATURE = 0.8
GROUP_SIZE = 4  # GRPO 风格：每个 prompt 采样多条轨迹

SYSTEM_PROMPT = """You are a visual math and chart reasoning assistant.
Look at the provided image carefully and answer the question.
Think step by step, then provide your final answer as <answer>NUMBER</answer>.
Only output a number in the answer tag."""

# ============================================================
# 2. 模拟数据集（实际使用时替换为真实图像）
# ============================================================


def create_placeholder_image():
    """
    创建一个最小的合法 PNG 图像（1x1 像素，红色）。
    实际使用时应替换为真实的图表/图形截图。
    """
    # Minimal 1x1 red PNG
    import io
    import zlib

    def _create_png_bytes():
        signature = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT chunk (1x1 red pixel: filter byte 0, R=255, G=0, B=0)
        raw_data = zlib.compress(b"\x00\xff\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw_data) & 0xFFFFFFFF
        idat = struct.pack(">I", len(raw_data)) + b"IDAT" + raw_data + struct.pack(">I", idat_crc)

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return signature + ihdr + idat + iend

    return _create_png_bytes()


# 模拟数据集：(图像bytes, 问题, 期望答案)
# 实际场景中，图像应为真实的图表截图、数学题图片等
PLACEHOLDER_IMAGE = create_placeholder_image()

TRAIN_DATASET = [
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The bar chart shows sales for Q1=150, Q2=230, Q3=180, Q4=310. What is the total annual sales?",
        "answer": "870",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The pie chart shows: Product A=40%, Product B=25%, Product C=35%. If total revenue is $500K, how much is Product B's revenue in thousands?",
        "answer": "125",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The line graph shows temperature readings: Mon=22, Tue=25, Wed=19, Thu=28, Fri=24. What is the average temperature?",
        "answer": "23.6",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The scatter plot shows data points. The trend line equation is y = 2.5x + 10. What is y when x = 20?",
        "answer": "60",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The table shows: Item A costs $15 (qty 3), Item B costs $8 (qty 5), Item C costs $22 (qty 2). What is the total cost?",
        "answer": "129",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The histogram shows exam scores. Mean=75, Std=10. What percentage of students scored above 85 (assume normal distribution, 1 std = 68%)?",
        "answer": "16",
    },
]

EVAL_DATASET = [
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The bar chart shows monthly visitors: Jan=1200, Feb=1500, Mar=1800. What is the growth from Jan to Mar?",
        "answer": "600",
    },
    {
        "image": PLACEHOLDER_IMAGE,
        "question": "The pie chart shows budget allocation: Engineering=45%, Marketing=30%, Operations=25%. If budget is $200K, how much goes to Marketing in thousands?",
        "answer": "60",
    },
]


# ============================================================
# 3. 奖励函数
# ============================================================


def compute_reward(response, expected_answer):
    """
    计算奖励：
    - 正确答案: +1.0
    - 错误答案: -0.5
    - 无法解析答案: -0.3
    """
    match = re.search(r"<answer>([\d\.\-\+e]+)</answer>", response)
    if not match:
        return -0.3  # 没有给出格式化答案

    try:
        predicted = float(match.group(1))
        expected = float(expected_answer)

        if expected != 0:
            rel_error = abs(predicted - expected) / abs(expected)
            if rel_error < 0.05:  # 5% 容差
                return 1.0
        elif abs(predicted) < 0.01:
            return 1.0

        return -0.5
    except ValueError:
        return -0.3


# ============================================================
# 4. 构造多模态消息
# ============================================================


def build_messages(image_bytes, question, response=None):
    """构造包含图像的多模态消息"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                ImagePart(image_data=image_bytes, format="png"),
                TextPart(text=question),
            ],
        },
    ]
    if response is not None:
        messages.append({"role": "assistant", "content": response})
    return messages


# ============================================================
# 5. 主训练循环
# ============================================================


def main():
    print(f"Model: {BASE_MODEL}")
    print(f"LoRA rank: {LORA_RANK}, LR: {LEARNING_RATE}")
    print(f"Group size: {GROUP_SIZE} (GRPO-style)")
    print(f"Training samples: {len(TRAIN_DATASET)}, Eval samples: {len(EVAL_DATASET)}")
    print("=" * 60)

    service_client = tinker.ServiceClient()
    training_client = service_client.create_lora_training_client(
        base_model=BASE_MODEL,
        rank=LORA_RANK,
    )

    # ---- 训练 ----
    print(f"\nStarting VLM RL training: {NUM_STEPS} steps")
    print("-" * 60)

    total_correct = 0
    total_episodes = 0

    for step in range(NUM_STEPS):
        data = TRAIN_DATASET[step % len(TRAIN_DATASET)]

        # GRPO: 每个样本采样多条轨迹
        group_rewards = []
        group_responses = []

        sampler = training_client.save_weights_and_get_sampling_client(
            name=f"vlm_step_{step}"
        )

        for g in range(GROUP_SIZE):
            # VLM 看图 + 生成推理过程和答案
            prompt_messages = build_messages(data["image"], data["question"])
            response = sampler.sample(
                messages=prompt_messages,
                temperature=TEMPERATURE,
                max_tokens=512,
            )

            reward = compute_reward(response, data["answer"])
            group_rewards.append(reward)
            group_responses.append(response)
            total_episodes += 1
            if reward > 0:
                total_correct += 1

        # GRPO advantage 计算
        mean_reward = sum(group_rewards) / len(group_rewards)

        for response, reward in zip(group_responses, group_rewards):
            advantage = reward - mean_reward
            train_messages = build_messages(data["image"], data["question"], response)

            training_client.forward_backward(
                messages=train_messages,
                loss="policy_gradient",
                reward=advantage,
            )

        training_client.optim_step(
            learning_rate=LEARNING_RATE,
            beta1=0.9,
            beta2=0.95,
            eps=1e-8,
        )

        if (step + 1) % 10 == 0:
            avg_reward = sum(group_rewards) / len(group_rewards)
            accuracy = total_correct / total_episodes * 100
            print(
                f"Step {step + 1}/{NUM_STEPS}, "
                f"Group Avg Reward: {avg_reward:.2f}, "
                f"Running Accuracy: {accuracy:.1f}%"
            )

        if (step + 1) % 25 == 0:
            training_client.save_state(f"vlm_checkpoint_{step + 1}")

    # ---- 评估 ----
    print("\n" + "=" * 60)
    print("Evaluation")
    print("=" * 60)

    eval_sampler = training_client.save_weights_and_get_sampling_client(
        name="vlm_final"
    )

    eval_correct = 0
    for data in EVAL_DATASET:
        prompt_messages = build_messages(data["image"], data["question"])
        response = eval_sampler.sample(
            messages=prompt_messages,
            temperature=0.0,  # greedy for eval
            max_tokens=512,
        )

        reward = compute_reward(response, data["answer"])
        status = "PASS" if reward > 0 else "FAIL"
        eval_correct += int(reward > 0)

        print(f"[{status}] Q: {data['question'][:60]}...")
        print(f"  Expected: {data['answer']}, Response: {response[:100]}...")

    print(
        f"\nEval Accuracy: {eval_correct}/{len(EVAL_DATASET)} "
        f"({eval_correct / len(EVAL_DATASET) * 100:.0f}%)"
    )
    print("\nDone! Model saved as 'vlm_final'.")


if __name__ == "__main__":
    main()
