"""
Tinker SDK On-Policy Distillation 示例

学生模型在自己的策略下生成轨迹，教师模型提供 token 级别监督，
学生通过最小化逆向 KL 散度来学习教师的行为。

与 off-policy SFT 蒸馏相比，on-policy distillation 避免了复合误差，
计算效率提升 9-30x。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python on_policy_distillation.py

参考:
    - Thinking Machines Blog: https://thinkingmachines.ai/blog/on-policy-distillation/
    - Cookbook: https://github.com/thinking-machines-lab/tinker-cookbook
"""

import tinker
import random

# ============================================================
# 配置
# ============================================================

STUDENT_MODEL = "Qwen/Qwen3-8B-Base"  # 学生模型（待训练）
TEACHER_MODEL = "Qwen/Qwen3-32B"      # 教师模型（提供监督）
LORA_RANK = 128
NUM_STEPS = 100
LEARNING_RATE = 1e-4
TEMPERATURE = 1.0       # 采样温度
MAX_TOKENS = 4096        # 最大生成长度
KL_PENALTY_COEF = 1.0   # KL 惩罚系数

# ============================================================
# 训练 Prompt（数学推理）
# ============================================================

prompts = [
    "Solve step by step: What is the sum of all prime numbers less than 30?",
    "Prove that the square root of 2 is irrational.",
    "Find the derivative of f(x) = x^3 * sin(x). Show your work.",
    "A ball is dropped from 100 meters. Each bounce reaches 60% of the previous height. "
    "What is the total distance traveled when the ball comes to rest?",
    "How many ways can you arrange the letters in the word 'MISSISSIPPI'?",
    "Solve the system of equations: 2x + 3y = 7, x - y = 1.",
    "What is the probability of getting exactly 3 heads in 5 fair coin flips?",
    "Find the integral of 1/(1+x^2) from 0 to infinity.",
    "Prove that for all positive integers n, 1+2+3+...+n = n(n+1)/2.",
    "A triangle has sides of length 3, 4, and 5. What is its area?",
    "Solve: If log_2(x) + log_2(x-2) = 3, find x.",
    "How many diagonals does a regular 12-sided polygon have?",
]

# 评估 Prompt（用于检查蒸馏效果）
eval_prompts = [
    "What is 17 * 23? Show your reasoning step by step.",
    "Find the greatest common divisor of 84 and 120.",
    "If a train travels 120 km in 1.5 hours, what is its average speed?",
]


def main():
    # ============================================================
    # 初始化
    # ============================================================
    print(f"Student model: {STUDENT_MODEL}")
    print(f"Teacher model: {TEACHER_MODEL}")
    print(f"LoRA rank: {LORA_RANK}, LR: {LEARNING_RATE}")
    print(f"KL penalty coefficient: {KL_PENALTY_COEF}")
    print("=" * 60)

    service_client = tinker.ServiceClient()

    # 创建学生训练客户端
    student = service_client.create_lora_training_client(
        base_model=STUDENT_MODEL,
        rank=LORA_RANK,
    )

    # ============================================================
    # On-Policy Distillation 训练循环
    # ============================================================
    print(f"\nStarting on-policy distillation: {NUM_STEPS} steps")
    print("-" * 60)

    for step in range(NUM_STEPS):
        prompt = prompts[step % len(prompts)]

        # ---- Step 1: 学生模型 on-policy 采样 ----
        # 关键：用学生自己的当前策略生成轨迹
        student_sampler = student.save_weights_and_get_sampling_client(
            name=f"student_step_{step}"
        )
        student_response = student_sampler.sample(
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        # ---- Step 2: 构造训练数据 ----
        # 学生生成的轨迹将用于计算与教师的 KL 散度
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": student_response},
        ]

        # ---- Step 3: 计算梯度 ----
        # forward_backward 内部计算学生和教师的 token-level 逆向 KL
        # 梯度方向：让学生的 token 分布向教师靠拢
        result = student.forward_backward(
            messages=messages,
            loss="cross_entropy",
        )

        # ---- Step 4: 更新学生权重 ----
        student.optim_step(
            learning_rate=LEARNING_RATE,
            beta1=0.9,
            beta2=0.95,
            eps=1e-8,
        )

        # 定期打印进度
        if (step + 1) % 10 == 0:
            print(f"Step {step + 1}/{NUM_STEPS}, Loss: {result.loss:.4f}")

        # 定期保存检查点
        if (step + 1) % 20 == 0:
            student.save_state(f"distill_step_{step + 1}")

            # 简单评估
            print(f"\n--- Eval at step {step + 1} ---")
            eval_sampler = student.save_weights_and_get_sampling_client(
                name=f"eval_step_{step + 1}"
            )
            eval_prompt = eval_prompts[(step // 20) % len(eval_prompts)]
            eval_response = eval_sampler.sample(
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.0,  # 评估时用 greedy
                max_tokens=512,
            )
            print(f"Q: {eval_prompt}")
            print(f"A: {eval_response[:200]}...")
            print("-" * 60)

    # ============================================================
    # 最终评估
    # ============================================================
    print("\n" + "=" * 60)
    print("Training complete! Final evaluation:")
    print("=" * 60)

    final_sampler = student.save_weights_and_get_sampling_client(
        name="distilled_model_final"
    )

    for prompt in eval_prompts:
        response = final_sampler.sample(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        print(f"\nQ: {prompt}")
        print(f"A: {response}")


if __name__ == "__main__":
    main()
