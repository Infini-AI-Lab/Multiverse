import datasets
from datasets import load_dataset
import random
import json
import re

dataset_path = 'simplescaling/s1K-1.1'
collect_path = '1.1k.jsonl'
dataset = load_dataset(dataset_path, split='train')

collect_data = []
for i in range(len(dataset)):
    data = dataset[i]
    d = dict()
    d['uuid'] = 'simple-scaling-1.1k-' + str(i)
    d['problem'] = data['question']
    d['solution'] = data['solution']
    d['correctness'] = data['deepseek_grade']
    cot_type = data['cot_type']
    d['thinking'] = data['deepseek_thinking_trajectory']
    d['output'] = data['deepseek_attempt']
    d['gemini_thinking'] = data['gemini_thinking_trajectory']
    d['gemini_output'] = data['gemini_attempt']
    collect_data.append(d)

with open(collect_path, 'w') as f:
    for d in collect_data:
        f.write(json.dumps(d) + '\n')
        
print(f"Collected {len(collect_data)} data")
