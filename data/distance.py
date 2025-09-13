import json
import os
import argparse
import datasets
from transformers import AutoTokenizer
import Levenshtein

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file_path", type=str, help="Path to the input file")
    parser.add_argument("--output_file_path", type=str, help="Path to the output file")
    parser.add_argument("--reasoning_dir", type=str, help="Path to the reasoning directory")
    parser.add_argument("--afterwards_dir", type=str, help="Path to the afterwards directory")
    parser.add_argument("--answer_dir", type=str, help="Path to the answer directory", default=None)
    parser.add_argument("--pattern", type=str, help="Pattern of the data")
    parser.add_argument("--threshold", type=float, help="Threshold of the distance", default=0.4)
    args = parser.parse_args()
    
    if args.pattern == 's1':
        ori_data = dict()
        with open(args.input_file_path, "r") as f:
            for line in f:
                data = json.loads(line)
                ori_data[data["uuid"]] = data
                
        dataset = datasets.load_dataset("simplescaling/s1K-1.1", split='train')
        reasoning_dir = args.reasoning_dir
        files = os.listdir(reasoning_dir)
        rebase_data = list()
        for file in files:
            id_ = file.split("_reasoning")[0]
            index = id_.split("simple-scaling-1.1k-")[1]
            index = int(index)
            if ori_data[id_]['problem'] != dataset[index]['question']:
                raise ValueError(f"problem not match: {ori_data[id_]['problem']} != {dataset[index]['question']}")
            d = dataset[index]
            ori_deepseek_thinking_trajectory = dataset[index]['deepseek_thinking_trajectory']
            # find the final word of "**Final Answer** and later part"
            if "**Final Answer**" not in ori_deepseek_thinking_trajectory:
                if "**[Final Answer]**" in ori_deepseek_thinking_trajectory:
                    final_word = "**Final Answer**"
                else:
                    print(f"no **Final Answer** or **[Final Answer]** in original data: {index}")
                    final_word = ""
            else:
                final_word = ori_deepseek_thinking_trajectory.split("**Final Answer**")[1]
                final_word = "**Final Answer** " + final_word
            new_deepseek_thinking_trajectory = open(os.path.join(reasoning_dir, file), "r").read()
            new_deepseek_thinking_trajectory = new_deepseek_thinking_trajectory.replace("<Think>", "")
            new_deepseek_thinking_trajectory = new_deepseek_thinking_trajectory.replace("</Think>", "")
            if "**Final Answer**" not in new_deepseek_thinking_trajectory:
                new_deepseek_thinking_trajectory = new_deepseek_thinking_trajectory + final_word
            new_deepseek_thinking_trajectory = "<Think>" + new_deepseek_thinking_trajectory + "</Think>"
                
            d['deepseek_thinking_trajectory_parallel'] = new_deepseek_thinking_trajectory
            d['deepseek_thinking_trajectory'] = dataset[index]['deepseek_thinking_trajectory']
            if args.afterwards_dir is not None:
                with open(os.path.join(args.afterwards_dir, file.replace("xml", "txt")), "r") as f:
                    after_text = f.read()
                d['deepseek_thinking_trajectory_sequential'] = after_text
            if args.answer_dir is not None:
                with open(os.path.join(args.answer_dir, file.replace("_reasoning.xml", "_answer.txt")), "r") as f:
                    answer = f.read()
                d['deepseek_attempt'] = answer
            distance = Levenshtein.distance(d['deepseek_thinking_trajectory_sequential'], d['deepseek_thinking_trajectory']) / max(len(d['deepseek_thinking_trajectory_sequential']), len(d['deepseek_thinking_trajectory']))
            # Set a threshold for the distance
            if distance > args.threshold:
                print(f"Warning: distance > {args.threshold}, the data will be skipped")
                continue
            d['distance'] = distance
            rebase_data.append(d)
            
        with open(args.output_file_path, "w") as f:
            for d in rebase_data:
                f.write(json.dumps(d) + "\n")
            
        
    elif args.pattern == 'r1':
        raise NotImplementedError("Not implemented")
            
        
