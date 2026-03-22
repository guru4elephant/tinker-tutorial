"""
Tinker SDK 监督微调 (SFT) 示例

基础 SFT 训练循环，适合对话机器人定制、知识注入等场景。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python sft_training.py
"""

import tinker

# ============================================================
# 配置
# ============================================================

BASE_MODEL = "meta-llama/Llama-3.2-1B"
LORA_RANK = 32
NUM_EPOCHS = 3
LEARNING_RATE = 1e-4

# ============================================================
# 训练数据
# ============================================================

train_data = [
    [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a high-level, interpreted programming language known for its simple syntax and versatility. It's widely used in web development, data science, AI, and automation."},
    ],
    [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is a subset of artificial intelligence where systems learn patterns from data to make predictions or decisions, without being explicitly programmed for each task."},
    ],
    [
        {"role": "user", "content": "Explain the difference between a list and a tuple in Python."},
        {"role": "assistant", "content": "Lists are mutable (can be changed after creation) and use square brackets []. Tuples are immutable (cannot be changed) and use parentheses (). Tuples are slightly faster and can be used as dictionary keys."},
    ],
    [
        {"role": "user", "content": "What is a neural network?"},
        {"role": "assistant", "content": "A neural network is a computational model inspired by the human brain. It consists of layers of interconnected nodes (neurons) that process data by learning weighted connections through training."},
    ],
]


def main():
    print(f"Initializing Tinker with {BASE_MODEL}...")
    service_client = tinker.ServiceClient()
    training_client = service_client.create_lora_training_client(
        base_model=BASE_MODEL,
        rank=LORA_RANK,
    )

    # 训练循环
    for epoch in range(NUM_EPOCHS):
        total_loss = 0.0

        for messages in train_data:
            result = training_client.forward_backward(
                messages=messages,
                loss="cross_entropy",
            )
            total_loss += result.loss

            training_client.optim_step(
                learning_rate=LEARNING_RATE,
                beta1=0.9,
                beta2=0.95,
                eps=1e-8,
            )

        avg_loss = total_loss / len(train_data)
        print(f"Epoch {epoch + 1}/{NUM_EPOCHS}, Avg Loss: {avg_loss:.4f}")

        training_client.save_state(f"sft_checkpoint_epoch_{epoch + 1}")

    # 测试推理
    print("\nTraining complete! Testing inference...")
    sampling_client = training_client.save_weights_and_get_sampling_client(
        name="my_sft_model"
    )

    test_questions = [
        "What is deep learning?",
        "How do you read a file in Python?",
    ]

    for question in test_questions:
        response = sampling_client.sample(
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )
        print(f"\nQ: {question}")
        print(f"A: {response}")


if __name__ == "__main__":
    main()
