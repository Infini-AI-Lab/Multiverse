import os
import json
import re
from tqdm import tqdm
import argparse

def main(args):
    input_path = args.input_file_path
    output_path = args.output_file_path

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    for file in tqdm(os.listdir(input_path)):
        with open(os.path.join(input_path, file), "r") as f:
            with open(os.path.join(output_path, file.replace(".xml", ".txt")), "w") as f_out:
                text = f.read()
                # remove all the material between <Goal> and </Goal> tags
                text = re.sub(r'<Goal>.*?</Goal>', '', text, flags=re.DOTALL)
                # remove all the material between <Conclusion> and </Conclusion> tags
                text = re.sub(r'<Conclusion>.*?</Conclusion>', '', text, flags=re.DOTALL)
                # remove all the <Parallel> and </Parallel> token itself
                text = re.sub(r'<Parallel>', '', text)
                text = re.sub(r'</Parallel>', '', text)
                text = re.sub(r'<Path>', '', text)
                text = re.sub(r'</Path>', '', text)
                text = re.sub(r'<Outline>', '', text)
                text = re.sub(r'</Outline>', '', text)
                text = re.sub(r'\n\n\n', '', text)
                text = re.sub(r'Let\'s think in parallel.\n', '', text)
                f_out.write(text)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file_path", type=str, required=True)
    parser.add_argument("--output_file_path", type=str, required=True)
    args = parser.parse_args()
    main(args)
