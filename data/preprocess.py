import os
import re
import json
import uuid
import argparse

def escape_xml_tags(text, allowed_tags):
    """
    Replaces '<' with '&lt;' and '>' with '&gt;' in a string,
    except when they are part of specified allowed tags.

    Args:
        text (str): The input string potentially containing XML-like tags.
        allowed_tags (list): A list of exact tag strings (including '/')
                             that should NOT be escaped.
                             Example: ['<Think>', '</Think>', '<Goal>', '</Goal>']

    Returns:
        str: The text with appropriate characters escaped.
    """
    if not text:
        return ""
    if not allowed_tags:
        # If no tags are allowed, escape all < and >
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Create unique placeholders for each allowed tag
    placeholders = {}
    reverse_placeholders = {}
    for i, tag in enumerate(allowed_tags):
        # Using UUID ensures placeholders are unique and unlikely to exist in the text
        placeholder = f"__PLACEHOLDER_{uuid.uuid4()}__"
        placeholders[tag] = placeholder
        reverse_placeholders[placeholder] = tag

    # --- Step 1: Protect allowed tags ---
    modified_text = text
    # Replace longer tags first to avoid partial replacements if tags are substrings
    # (e.g., if '<T>' and '</T>' were allowed, replace '</T>' first)
    # Although with the specific list given, order doesn't strictly matter here.
    # A simple sort by length descending is a good general strategy.
    sorted_tags = sorted(placeholders.keys(), key=len, reverse=True)
    for tag in sorted_tags:
        # Use regex replacement for exact match (though str.replace works too here)
        # Ensure we don't accidentally replace parts of other placeholders if generated differently
        modified_text = modified_text.replace(tag, placeholders[tag])

    # --- Step 2: Escape remaining '<' and '>' ---
    # First, handle '&' to avoid double-escaping if it appears before < or >
    modified_text = modified_text.replace('&', '&amp;')
    modified_text = modified_text.replace('<', '&lt;')
    modified_text = modified_text.replace('>', '&gt;')

    # --- Step 3: Restore allowed tags ---
    # No specific order needed for restoring placeholders
    for placeholder, tag in reverse_placeholders.items():
        modified_text = modified_text.replace(placeholder, tag)

    return modified_text

# --- Example Usage ---

# Define the tags that should remain untouched
allowed = [
    '<Think>', '</Think>',
    '<Parallel>', '</Parallel>',
    '<Goal>', '</Goal>',
    '<Path>', '</Path>',
    '<Conclusion>', '</Conclusion>'
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process XML files')
    parser.add_argument('--input_dir_path', type=str, help='Path to the input directory')
    parser.add_argument('--output_dir_path', type=str, help='Path to the output directory')
    parser.add_argument('--ref_path', type=str, help='Path to the reference file')
    parser.add_argument('--pattern', type=str, help='pattern of the file')
    args = parser.parse_args()
    
    dir_path = args.input_dir_path
    output_dir_path = args.output_dir_path
    ref_path = args.ref_path

    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)
    
    if args.pattern == 's1':
        total = 0
        for file in os.listdir(dir_path):
            if 'structure' in file or 'answer' in file:
                continue
            if os.path.isdir(dir_path + file):
                continue
            with open(dir_path + file, 'r') as f:
                material = f.read()
            # check whether starts with ```text and ends with ```, if so remove them
            if material.startswith('```text') and material.endswith('```'):
                material = material[len('```text'):-len('```')]
            # check whether starts with ```json and ends with ```, if so remove them
            elif material.startswith('```json') and material.endswith('```'):
                material = material[len('```json'):-len('```')]
            # check whether starts with ```markdown and ends with ```, if so remove them
            elif material.startswith('```markdown') and material.endswith('```'):
                material = material[len('```markdown'):-len('```')]
            # check whether starts with ``` and ends with ```, if so remove them
            elif material.startswith('```') and material.endswith('```'):
                material = material[len('```'):-len('```')]
                
            material = '<Think>' + material + '</Think>'
            material = escape_xml_tags(material, allowed)
            # material = material + '\n' + ref_data[id_]['output']
            
            # write to output file
            with open(output_dir_path + file, 'w') as f:
                f.write(material)
            total += 1
        print(f"Total number of preprocessed files: {total}")
                
    elif args.pattern == 'r1':
        
        ref_data = {}
        with open(ref_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                ref_data[data['uuid']] = data

        for file in os.listdir(dir_path):
            with open(dir_path + file, 'r') as f:
                material = f.read()
            # check whether starts with ```text and ends with ```, if so remove them
            if material.startswith('```text') and material.endswith('```'):
                material = material[len('```text'):-len('```')]
            # check whether starts with ```json and ends with ```, if so remove them
            elif material.startswith('```json') and material.endswith('```'):
                material = material[len('```json'):-len('```')]
            # check whether starts with ```markdown and ends with ```, if so remove them
            elif material.startswith('```markdown') and material.endswith('```'):
                material = material[len('```markdown'):-len('```')]
            elif material.startswith('```') and material.endswith('```'):
                print(material)
            # Add <Think> and </Think> tags
            material = '<Think>\n' + material + '\n</Think>'
            # id_ = file.split('_reasoning')[0]
            # if id_ not in ref_data:
            #     print(f"Warning: UUID {id_} not found in reference data.")
            #     continue
            
            # check the < and > symbol, if it is not in the case of <Think>, </Think>, <Parallel> </Parallel> <Goal> </Goal> <Path> </Path> <Conclusion> </Conclusion>, then change it to &lt; and &gt;
            material = escape_xml_tags(material, allowed)
            # material = material + '\n' + ref_data[id_]['output']
            
            # write to output file
            with open(output_dir_path + file, 'w') as f:
                f.write(material)
                
            

