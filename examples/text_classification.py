"""
Tinker SDK 文本分类示例 — 情感分析

将传统的分类任务转化为 LLM 生成式 prompt 格式，
通过 SFT 微调实现高质量的文本分类。

用法:
    pip install tinker
    export TINKER_API_KEY="your-api-key"
    python text_classification.py
"""

import tinker
import random

# ============================================================
# 1. 配置
# ============================================================

BASE_MODEL = "meta-llama/Llama-3.2-1B"  # 分类任务用小模型即可
LORA_RANK = 16          # 分类任务复杂度低，小秩即可
NUM_EPOCHS = 5
LEARNING_RATE = 2e-4    # 分类任务可用稍大学习率
LABELS = ["positive", "negative", "neutral"]

SYSTEM_PROMPT = (
    "You are a sentiment classifier. "
    "Classify the given text into exactly one category.\n"
    "Respond with ONLY the label, nothing else.\n"
    f"Labels: {', '.join(LABELS)}"
)

# ============================================================
# 2. 训练数据（将分类标签转化为 chat 格式）
# ============================================================

train_data = [
    # Positive
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "This movie was absolutely fantastic! Best film I've seen all year."},
        {"role": "assistant", "content": "positive"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "I love this restaurant! The food is amazing and the service is excellent."},
        {"role": "assistant", "content": "positive"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "What a wonderful experience! Highly recommend to everyone."},
        {"role": "assistant", "content": "positive"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "The new update is incredible, everything runs so much smoother now."},
        {"role": "assistant", "content": "positive"},
    ],
    # Negative
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Terrible waste of time. The plot made no sense and the acting was awful."},
        {"role": "assistant", "content": "negative"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Worst customer service ever. Never buying from them again."},
        {"role": "assistant", "content": "negative"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Completely broken on arrival. Total waste of money."},
        {"role": "assistant", "content": "negative"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "I regret this purchase. The quality is unacceptably poor."},
        {"role": "assistant", "content": "negative"},
    ],
    # Neutral
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "The product arrived on time and works as described."},
        {"role": "assistant", "content": "neutral"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "The meeting has been rescheduled to 3pm tomorrow."},
        {"role": "assistant", "content": "neutral"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "The package weighs about 2 kilograms and measures 30cm by 20cm."},
        {"role": "assistant", "content": "neutral"},
    ],
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "The store is located on the corner of 5th Avenue and Main Street."},
        {"role": "assistant", "content": "neutral"},
    ],
]

# 测试数据
test_data = [
    {"text": "This is the best purchase I've ever made!", "label": "positive"},
    {"text": "Completely disappointed with the quality.", "label": "negative"},
    {"text": "The package weighs about 2 kilograms.", "label": "neutral"},
    {"text": "Outstanding performance and great value for money!", "label": "positive"},
    {"text": "Do not buy this. It broke after one day.", "label": "negative"},
    {"text": "The office is on the second floor.", "label": "neutral"},
]


def main():
    # ============================================================
    # 3. 初始化 Tinker
    # ============================================================
    print(f"Initializing Tinker with {BASE_MODEL}...")
    service_client = tinker.ServiceClient()
    training_client = service_client.create_lora_training_client(
        base_model=BASE_MODEL,
        rank=LORA_RANK,
    )

    # ============================================================
    # 4. 训练
    # ============================================================
    print(f"\nStarting training: {NUM_EPOCHS} epochs, lr={LEARNING_RATE}")
    print(f"Training samples: {len(train_data)}, Test samples: {len(test_data)}")
    print("-" * 60)

    for epoch in range(NUM_EPOCHS):
        random.shuffle(train_data)
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

        training_client.save_state(f"sentiment_epoch_{epoch + 1}")

    # ============================================================
    # 5. 评估
    # ============================================================
    print("\n" + "=" * 60)
    print("Evaluation")
    print("=" * 60)

    sampling_client = training_client.save_weights_and_get_sampling_client(
        name="sentiment_classifier"
    )

    correct = 0
    for item in test_data:
        response = sampling_client.sample(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": item["text"]},
            ],
            temperature=0.0,
            max_tokens=8,
        )

        predicted = response.strip().lower()
        expected = item["label"]
        is_correct = predicted == expected
        correct += int(is_correct)

        status = "PASS" if is_correct else "FAIL"
        print(f"[{status}] \"{item['text'][:50]}...\"")
        print(f"       Expected: {expected}, Predicted: {predicted}")

    accuracy = correct / len(test_data) * 100
    print(f"\nAccuracy: {accuracy:.1f}% ({correct}/{len(test_data)})")


if __name__ == "__main__":
    main()
