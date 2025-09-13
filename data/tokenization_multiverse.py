from typing import Dict
from datasets import load_dataset, Dataset, concatenate_datasets
from transformers import AutoTokenizer
from functools import partial

QUERY_TEMPLATE_NOANSWER = """{Question}""".strip()

def process_cot_example(
    example: Dict,
    tokenizer,
):
    source = example.get("source_dataset")

    if source == "d1":
        thinking_trajectory = example["deepseek_thinking_trajectory_parallel"].strip()
        question = example["question"] + " Think step by step and in parallel before answering."

    elif source == "d2":
        thinking_trajectory = "<Think>\n" + example["deepseek_thinking_trajectory"].strip() + "\n</Think>"
        question = example["question"] + " Think step by step before answering."
    else:
        # Fallback for examples without a source_dataset identifier or with an unrecognized one.
        # This situation likely indicates an issue upstream in data preparation.
        print(f"Warning: Example is missing 'source_dataset' or has an unrecognized one. Source: {source}. Question: {example.get('question', 'N/A')}")
        # Defaulting to empty string for thinking_trajectory in such cases.
        # Consider if original logic based on 'distance' should be a fallback if 'distance' is reliably present.
        thinking_trajectory = ""

    answer = example["deepseek_attempt"] 
    prompt = QUERY_TEMPLATE_NOANSWER.format(Question=question)
    answer = "Answer: " + answer if "Answer:" not in answer else answer
    text = tokenizer.apply_chat_template([
        {"role": "user", "content": prompt},
        {
            "role": "assistant", 
            "content": thinking_trajectory.strip() + "\n\n" + answer.strip()
        }
    ], tokenize=False)
    return dict(
            text=text,
        )

def reorder_dataset(
    metadata_dataset: Dataset,
    target_dataset: Dataset,
    key: str = "metadata",
) -> Dataset:
    """
    Reorder target_dataset to match the order of metadata_dataset based on a key field.
    """
    target_lookup = {example[key]: example for example in target_dataset}

    reordered_examples = []
    missing_keys = []
    for k in metadata_dataset[key]:
        if k in target_lookup:
            reordered_examples.append(target_lookup[k])
        else:
            missing_keys.append(k)

    if missing_keys:
        print(f"⚠️ Warning: {len(missing_keys)} missing keys not found in target dataset. (Examples: {missing_keys[:5]})")

    return Dataset.from_list(reordered_examples)

def mathcot_sft(upload_data_path: str, num_proc: int,
                download_data_path1: str = None,
                download_data_path2: str = "simplescaling/s1K-1.1"):
    # Load dataset1
    dataset1 = load_dataset(download_data_path1, download_mode='force_redownload')
    if 'train' in dataset1:
        dataset1 = dataset1['train']
    # Add source identifier to dataset1
    dataset1 = dataset1.map(lambda ex: {**ex, "source_dataset": "d1"})

    # Load dataset2
    dataset2 = load_dataset(download_data_path2, download_mode='force_redownload')
    if 'train' in dataset2:
        dataset2 = dataset2['train']
    # Add source identifier to dataset2
    dataset2 = dataset2.map(lambda ex: {**ex, "source_dataset": "d2"})

    dataset1 = dataset1.shuffle(seed=42)
    dataset2 = dataset2.shuffle(seed=42)

    d1_len = len(dataset1)
    d1_first_half_end_idx = d1_len // 2
    d1_first_half = dataset1.select(range(d1_first_half_end_idx))
    d1_second_half = dataset1.select(range(d1_first_half_end_idx, d1_len))

    d1_one_of_ten_idx = d1_len // 10
    d1_one_of_ten = dataset1.select(range(d1_one_of_ten_idx))
    d1_rest = dataset1.select(range(d1_one_of_ten_idx, d1_len))

    d2_len = len(dataset2)
    d2_first_half_end_idx = d2_len // 2
    d2_first_half = dataset2.select(range(d2_first_half_end_idx))
    d2_second_half = dataset2.select(range(d2_first_half_end_idx, d2_len))

    d2_one_of_ten_idx = d2_len // 10
    d2_one_of_ten = dataset2.select(range(d2_one_of_ten_idx))
    d2_rest = dataset2.select(range(d2_one_of_ten_idx, d2_len))

    mixed_first_halves = concatenate_datasets([d1_first_half, d2_first_half]).shuffle(seed=42)
    mixed_second_halves = concatenate_datasets([d1_second_half, d2_second_half]).shuffle(seed=42)

    mixed_d1 = concatenate_datasets([d1_rest, d2_one_of_ten]).shuffle(seed=42)
    mixed_d2 = concatenate_datasets([d1_one_of_ten, d2_rest]).shuffle(seed=42)

    dataset = concatenate_datasets([
        dataset2,
        dataset2,
        mixed_d2,
        mixed_first_halves,
        mixed_second_halves,
        mixed_d1,
        dataset1,
        dataset1
    ])
    
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-32B-Instruct")
    process_example_map = partial(process_cot_example, tokenizer=tokenizer)
    dataset = dataset.map(
        process_example_map,
        num_proc=num_proc,
        desc="Tokenizing SFT data",
    )
    
    dataset.push_to_hub(upload_data_path)
    print(f"✅ Uploaded unsorted tokenized dataset to {upload_data_path}")


if __name__ == "__main__":
    mathcot_sft(download_data_path1="Multiverse4FM/Multiverse-1K",
                download_data_path2="simplescaling/s1K-1.1",
                upload_data_path="Multiverse4FM/Autoregressive-1K-mixed", 
                num_proc=1)
