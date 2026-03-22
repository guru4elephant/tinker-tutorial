# 多模态 VLM 模型 RL 训练调研与教程

> 基于 Thinking Machines Tinker SDK 对视觉语言模型进行 SFT/RL 微调

## 1. 概述

### 1.1 Tinker 的多模态支持

2025 年 12 月，Tinker 在 GA（正式发布）时新增了视觉语言模型（VLM）支持。用户可以输入图片（截图、照片、图表等），对 VLM 进行 **SFT 和 RL 微调**。

### 1.2 支持的视觉模型

| 模型 | 参数量 | 活跃参数 | 架构 | 说明 |
|------|--------|----------|------|------|
| Qwen3-VL-30B-A3B-Instruct | 30B | 3B | MoE | 轻量级 VLM，性价比高 |
| Qwen3-VL-235B-A22B-Instruct | 235B | 22B | MoE | 大型 VLM，能力最强 |

> **注意**：Tinker 只支持预定义的模型列表，不支持上传自定义模型。完整列表见 [Model Lineup](https://tinker-docs.thinkingmachines.ai/model-lineup)。

### 1.3 为什么用 VLM 做视觉任务？

传统视觉模型（如 DINOv2、ResNet）需要大量标注数据。VLM 的优势：

| 特性 | 传统视觉模型 | VLM (Qwen3-VL) |
|------|-------------|----------------|
| **少样本能力** | 弱 | 强（自带语言知识） |
| **零样本能力** | 无 | 有（知道 "golden retriever" 是什么） |
| **任务格式** | 需要分类头 | 直接生成文本标签 |
| **灵活性** | 固定类别 | 开放类别，prompt 可调 |
| **多任务** | 每个任务一个模型 | 一个模型多个任务 |

Thinking Machines 的基准测试显示：在少样本场景下（每类仅 1 个样本），**Qwen3-VL-235B 超过 DINOv2-base**。

---

## 2. 图像输入 API

### 2.1 低级 API：ImageChunk

Tinker 的底层 API 通过 `ImageChunk` 和 `EncodedTextChunk` 交错排列来输入多模态数据：

```python
import tinker

# 读取图像为 bytes
with open("image.png", "rb") as f:
    image_bytes = f.read()

# 构造多模态输入
model_input = tinker.ModelInput(chunks=[
    tinker.types.ImageChunk(data=image_bytes, format="png"),
    tinker.types.EncodedTextChunk(tokens=tokenizer.encode("What is in this image?")),
])
```

### 2.2 高级 API：消息格式

更常用的高级接口，消息的 `content` 可以是字符串或包含 `ImagePart` / `TextPart` 的列表：

```python
from tinker.types import ImagePart, TextPart

messages = [
    {
        "role": "user",
        "content": [
            ImagePart(image_data=image_bytes, format="png"),
            TextPart(text="Classify this image into one category: cat, dog, bird, other."),
        ],
    },
    {
        "role": "assistant",
        "content": "dog",
    },
]
```

### 2.3 Qwen3VLRenderer

Qwen3-VL 使用特殊 token（`<|vision_start|>`, `<|vision_end|>`）来标记视觉区域。Cookbook 提供了 `Qwen3VLRenderer`，自动处理这些 token：

```python
from tinker_cookbook.renderers import Qwen3VLRenderer

renderer = Qwen3VLRenderer(
    model_name="Qwen/Qwen3-VL-235B-A22B-Instruct"
)

# renderer 自动在图像前后插入 <|vision_start|> 和 <|vision_end|>
tokens = renderer.render(messages)
```

---

## 3. VLM SFT 微调

### 3.1 图像分类（SFT）

将分类问题转化为文本生成——给定图像，模型直接输出类别名称：

```python
import tinker

service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="Qwen/Qwen3-VL-235B-A22B-Instruct",
    rank=32,
)

# 训练数据：图像 + 分类标签
for image_bytes, label in train_dataset:
    messages = [
        {
            "role": "user",
            "content": [
                ImagePart(image_data=image_bytes, format="png"),
                TextPart(text="Classify this image. Respond with only the class name."),
            ],
        },
        {"role": "assistant", "content": label},
    ]

    result = training_client.forward_backward(
        messages=messages,
        loss="cross_entropy",
    )
    training_client.optim_step(learning_rate=1e-4)
```

### 3.2 官方 VLM Classifier Recipe

Cookbook 提供了生产级的 VLM 分类 recipe：

```bash
# 位于 tinker_cookbook/recipes/vlm_classifier/
python -m tinker_cookbook.recipes.vlm_classifier.train \
    model_name=Qwen/Qwen3-VL-235B-A22B-Instruct \
    dataset=caltech101 \
    learning_rate=1e-4 \
    lora_rank=32
```

支持的数据集：Caltech 101、Stanford Cars、Oxford Flowers、Oxford Pets。

---

## 4. VLM RL 微调

### 4.1 为什么需要 VLM RL？

SFT 需要标注的 (图像, 标签) 对。RL 允许模型通过与环境交互来学习，适用于：

| 场景 | SFT | RL |
|------|-----|-----|
| 标注数据充足 | 适合 | 可用 |
| 标注数据稀缺 | 困难 | **适合（用奖励函数替代标注）** |
| 需要推理链 | 需要标注推理过程 | **自动学习推理链** |
| 多步视觉推理 | 困难 | **适合（多轮交互）** |
| GUI Agent | 需要大量轨迹标注 | **适合（环境奖励）** |

### 4.2 VLM RL 典型场景

| 场景 | 输入 | 工具/环境 | 奖励 |
|------|------|-----------|------|
| **图表问答** | 图表截图 + 问题 | 无 | 答案正确性 |
| **GUI Agent** | 屏幕截图 | 点击/输入操作 | 任务完成度 |
| **视觉数学** | 数学题图片 | 计算器 | 答案正确性 |
| **文档理解** | PDF/文档截图 | 无 | 提取信息准确性 |
| **视觉推理** | 场景图片 | 无 | 推理正确性 |
| **机器人控制** | 摄像头画面 | 动作指令 | 任务完成度 |

### 4.3 VLM RL 训练流程

```
1. 环境提供图像观测（截图、图表等）
   ↓
2. VLM 接收图像 + 文本 prompt → 生成动作/回答
   ↓
3. 环境执行动作 / 验证答案 → 返回奖励
   ↓
4. 使用 policy gradient 更新 VLM 的 LoRA 权重
   ↓
5. 重复 1-4
```

---

## 5. 完整示例：视觉数学推理 RL

> 完整代码见 [examples/vlm_rl_training.py](../examples/vlm_rl_training.py)

训练 VLM 看数学题图片并给出正确答案，通过 RL 学习推理过程：

```python
import tinker
from tinker.types import ImagePart, TextPart

service_client = tinker.ServiceClient()
training_client = service_client.create_lora_training_client(
    base_model="Qwen/Qwen3-VL-30B-A3B-Instruct",  # 视觉模型
    rank=32,
)

SYSTEM_PROMPT = """You are a visual math solver. Look at the image carefully.
Think step by step, then provide your answer as <answer>NUMBER</answer>."""

for step in range(num_steps):
    image_bytes, question, expected_answer = dataset[step]

    # 1. VLM 看图 + 生成推理和答案
    sampler = training_client.save_weights_and_get_sampling_client(
        name=f"vlm_step_{step}"
    )
    response = sampler.sample(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    ImagePart(image_data=image_bytes, format="png"),
                    TextPart(text=question),
                ],
            },
        ],
        temperature=0.8,
        max_tokens=512,
    )

    # 2. 计算奖励
    reward = compute_reward(response, expected_answer)

    # 3. Policy gradient 更新
    training_client.forward_backward(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    ImagePart(image_data=image_bytes, format="png"),
                    TextPart(text=question),
                ],
            },
            {"role": "assistant", "content": response},
        ],
        loss="policy_gradient",
        reward=reward,
    )
    training_client.optim_step(learning_rate=5e-5)
```

---

## 6. 完整示例：多轮视觉 Agent（GUI 操作）

多轮场景下，VLM 反复观察屏幕截图并执行操作：

```python
# 伪代码：GUI Agent RL 训练
for step in range(num_steps):
    env = GUIEnvironment(task="Open the calculator app and compute 123*456")
    messages = [{"role": "system", "content": GUI_SYSTEM_PROMPT}]
    total_reward = 0.0

    done = False
    while not done:
        # 获取当前屏幕截图
        screenshot_bytes = env.get_screenshot()

        # 添加截图到对话
        messages.append({
            "role": "user",
            "content": [
                ImagePart(image_data=screenshot_bytes, format="png"),
                TextPart(text="What action should you take next?"),
            ],
        })

        # VLM 生成动作
        response = sampler.sample(messages=messages, temperature=0.8)
        messages.append({"role": "assistant", "content": response})

        # 执行动作，获取奖励
        action = parse_action(response)
        reward, done = env.step(action)
        total_reward += reward

    # 用完整轨迹训练
    training_client.forward_backward(
        messages=messages,
        loss="policy_gradient",
        reward=total_reward,
    )
    training_client.optim_step(learning_rate=5e-5)
```

---

## 7. 最佳实践

### 7.1 模型选择

| 场景 | 推荐模型 | 说明 |
|------|---------|------|
| 快速实验 | Qwen3-VL-30B-A3B | MoE，活跃参数仅 3B，成本低 |
| 最佳效果 | Qwen3-VL-235B-A22B | 大型 VLM，少样本能力强 |

### 7.2 超参数推荐

| 参数 | SFT | RL |
|------|-----|-----|
| `lora_rank` | 16-32 | 32-128 |
| `learning_rate` | 1e-4 ~ 2e-4 | 1e-5 ~ 5e-5 |
| `temperature` | — | 0.8-1.0 |
| `max_tokens` | 16（分类）| 512-2048 |

### 7.3 图像处理建议

- 图像格式支持 PNG 和 JPEG，推荐 PNG（无损）
- 图像会被 Qwen3-VL 内部的 image processor 自动调整大小
- 大图像会增加 token 数量（影响成本），建议预处理到合理分辨率
- 多图输入：可以在一条消息中包含多个 `ImagePart`

### 7.4 注意事项

- VLM 的 LoRA 只微调语言模型部分，**不微调视觉编码器**
- 推理时用 `temperature=0.0` 确保确定性输出（分类任务）
- RL 训练时用 `temperature=0.8-1.0` 鼓励探索
- Qwen3-VL 的 Instruct 版本已经有很好的零样本视觉理解能力，通常只需少量微调

---

## 8. 支持的模型说明

### 8.1 Tinker 的模型策略

**Tinker 只支持预定义的开源模型列表，不支持上传自定义模型。**

原因：Tinker 为每个基础模型维护一个热 GPU 池（warm pool），所有用户共享相同的基础模型权重，仅 LoRA 适配器不同。这种设计使得 GPU 利用率极高——任何持有相同基础模型的 worker 都能处理任何用户的请求。

### 8.2 当前完整模型列表

| 类别 | 模型 | 架构 | 特点 |
|------|------|------|------|
| **紧凑 Dense** | Llama-3.2-1B, 3B | Dense | Base / Instruct |
| **中型 Dense** | Llama-3.1-8B | Dense | Base / Instruct |
| **大型 Dense** | Llama-3.1-70B | Dense | Base / Instruct |
| **MoE** | Qwen3-8B, Qwen3-14B, Qwen3-32B | MoE | Base / Instruct / Hybrid |
| **大型 MoE** | Qwen3-235B-A22B | MoE | Base / Instruct / Hybrid |
| **超大 MoE** | Qwen3.5-397B-A17B | MoE | Instruct |
| **Vision** | Qwen3-VL-30B-A3B, Qwen3-VL-235B-A22B | MoE + Vision | Instruct |
| **Reasoning** | Kimi K2 Thinking | MoE | Thinking mode |

### 8.3 模型权重可导出

虽然不能上传自定义模型，但训练好的 LoRA 权重可以**下载**出来，在其他平台使用：

```python
# 下载训练好的 LoRA 权重
training_client.download_weights("my_checkpoint", output_dir="./weights")
# 然后在 vLLM、llama.cpp 等推理框架中使用
```

### 8.4 替代方案

如果需要使用 Tinker 不支持的模型：

| 需求 | 替代方案 |
|------|---------|
| 自定义架构 | SkyRL（兼容 Tinker API，可在自有 GPU 上运行） |
| 其他开源模型 | 等待 Tinker 扩展模型列表 |
| 闭源模型微调 | OpenAI fine-tuning API / Google Vertex AI |

---

## 参考资源

- [Tinker GA + Vision Input Blog](https://thinkingmachines.ai/blog/tinker-general-availability/)
- [Tinker Model Lineup](https://tinker-docs.thinkingmachines.ai/model-lineup)
- [Tinker Rendering Docs](https://tinker-docs.thinkingmachines.ai/rendering)
- [Tinker Training & Sampling](https://tinker-docs.thinkingmachines.ai/training-sampling)
- [Tinker Cookbook: VLM Classifier Recipe](https://github.com/thinking-machines-lab/tinker-cookbook)
- [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
