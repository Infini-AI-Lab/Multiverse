import asyncio
import os
from google import genai
import argparse
import json
import logging
from tqdm import tqdm
from typing import List
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
     raise ValueError("API key is missing. Use an environment variable or replace the placeholder.")


async def run_chat(client, prompt:List[str], thinking:str, model:str):
    chat = client.aio.chats.create(
        model=model,
    )
    
    prompt_list = []
    response_list = []

    for i, p in enumerate(prompt):
        if i == 3:
            all_case_response = []
            all_case_prompt = []
            recent_response = response_list[-1]
            # fine all the P{i} with i is an integer in the recent_response
            all_case = re.findall(r'P(\d+)', recent_response)
            all_case = list(set(all_case))
            all_case.sort()
            for case in all_case:
                p_case = p.format(i=case)
                response = await chat.send_message(p_case)
                all_case_response.append(response.text)
                all_case_prompt.append(p_case)
            response_list.append(all_case_response)
            prompt_list.append(all_case_prompt)
            continue
            
        elif i == 0:
            p = thinking + '\n\n' + p
        response = await chat.send_message(p)
        response_list.append(response.text)
        prompt_list.append(p)
    return response_list, prompt_list

async def run_chat_step1(client, prompt:List[str], thinking:str, model:str):
    chat = client.aio.chats.create(
        model=model,
    )
    
    prompt_list = []
    response_list = []
    
    for i, p in enumerate(prompt):
        if i == 0 or i == 5:
            original_text = "Original Reasoning Chain: \n" + "```markdown\n" + thinking + "\n```"
            p = original_text + "\n\n" + p
        response = await chat.send_message(p)
        response_list.append(response.text)
        prompt_list.append(p)
    return response_list, prompt_list

async def run_chat_step2(client, prompt:List[str], thinking:str, model:str, structure:str):
    chat = client.aio.chats.create(
        model=model,
    )
    
    prompt_list = []
    response_list = []
    
    basic_info = "** Original Reasoning Chain **: \n" + "```markdown\n" + thinking + "\n```"
    basic_info = basic_info + "\n\n" + "**Outline**: \n" + structure
    for i, p in enumerate(prompt):
        if i == 0:
            p = basic_info + "\n\n" + p
        response = await chat.send_message(p)
        response_list.append(response.text)
        prompt_list.append(p)
    return response_list, prompt_list

def main():
    parser = argparse.ArgumentParser(description='Run Gemini reasoning.')
    parser.add_argument('--prompt', type=str, help='The prompt file to use.')
    parser.add_argument('--input', type=str, help='The input file to use.')
    parser.add_argument('--output', type=str, help='The output file to store.')
    parser.add_argument('--structure', type=str, help='The structure file to use.', default=None)
    parser.add_argument('--chat', type=str, help='The chat file to store.')
    parser.add_argument('--start_idx', type=int, help='The start index of the input file.')
    parser.add_argument('--end_idx', type=int, help='The end index of the input file.')
    parser.add_argument('--gemini_model', type=str, help='The model to use.', default='gemini-2.5-pro-preview-03-25')
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    if not os.path.exists(args.chat):
        os.makedirs(args.chat)
    logger.info(f"args: {args}")
    r1_dataset = []
    with open(args.input, 'r') as f:
        for line in f:
            r1_dataset.append(json.loads(line))
    logger.info(f"Loaded {len(r1_dataset)} examples from {args.input}")
    if args.start_idx is not None:
        start_idx = args.start_idx if args.start_idx >= 0 else 0
    else:
        start_idx = 0
    if args.end_idx is not None:
        end_idx = args.end_idx if args.end_idx < len(r1_dataset) else len(r1_dataset)
    else:
        end_idx = len(r1_dataset)
    
    r1_dataset = r1_dataset[start_idx:end_idx]
    logger.info(f"Loaded {len(r1_dataset)} examples from {args.input} from {start_idx} to {end_idx}")
        
    with open(args.prompt, 'r') as f:
        prompt = f.read()
    prompt = prompt.split('---\n')
    
    # if args.structure is not None:
    #     with open(args.structure, 'r') as f:
    #         structure = f.read()
    # else:
    #     structure = None
    
    logger.info(f"Prompt Number: {len(prompt)}")
    for p in prompt:
        logger.info(p)
        logger.info('-'*100)
        
    # Run the asynchronous chat logic
    for i, r in tqdm(enumerate(r1_dataset)):
        client = genai.Client(api_key=api_key)
        uuid = r['uuid']
        thinking = r['thinking']
        prompt_list = prompt.copy()
        try:
            # TODO: Specify the function
            if 'step1' in args.prompt:
                response_list, prompt_list = asyncio.run(run_chat_step1(client, prompt_list, thinking, args.gemini_model))
            elif 'step2' in args.prompt:
                with open(os.path.join(args.structure, f"{uuid}_structure.txt"), 'r') as f:
                    structure = f.read()
                response_list, prompt_list = asyncio.run(run_chat_step2(client, prompt_list, thinking, args.gemini_model, structure))
            else:
                response_list, prompt_list = asyncio.run(run_chat(client, prompt_list, thinking, args.gemini_model))
            final_response = response_list[-1]
            if len(response_list) > 4:  
                structure_response = response_list[4]
            if 'step1' in args.prompt:
                reasoning_path = os.path.join(args.output, f"{uuid}_reasoning.txt")
                structure_path = os.path.join(args.output, f"{uuid}_structure.txt")
            else:
                reasoning_path = os.path.join(args.output, f"{uuid}_reasoning.txt")
            with open(reasoning_path, 'w') as f:
                f.write(final_response)
            if 'step1' in args.prompt:
                with open(structure_path, 'w') as f:
                    f.write(structure_response)
            chat_path = os.path.join(args.chat, f"{uuid}_chat.txt")
            with open(chat_path, 'w') as f:
                for p, r in zip(prompt_list, response_list):
                    f.write(f"Prompt: {p}\n")
                    f.write(f"Response: {r}\n")
        except Exception as e:
            logger.error(f"Error in {uuid}: {e}")
            continue

if __name__ == "__main__":
    main()