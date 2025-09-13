import lxml.etree as LET
import os
import re
import traceback
import sys
from copy import deepcopy

INLINE_TAGS = {}
INDENT_STRING = ""
ALLOWED_TAGS = {"Think", "Parallel", "Goal", "Path", "Conclusion", "Outline"}
import asyncio
from google import genai
import argparse
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

allowed = [
    '<Think>', '</Think>',
    '<Parallel>', '</Parallel>',
    '<Goal>', '</Goal>',
    '<Path>', '</Path>',
    '<Conclusion>', '</Conclusion>'
]

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

def escape_disallowed_tags(xml_string):
    result = []
    pos = 0
    tag_pattern = re.compile(r"<[^<>]+?>")

    for match in tag_pattern.finditer(xml_string):
        start, end = match.span()
        tag_text = match.group()
        tag_body = tag_text[1:-1].strip()
        tag_name = tag_body.lstrip("/").split()[0]

        if start > pos:
            text_before = xml_string[pos:start]
            text_escaped = text_before.replace("<", "&lt;").replace(">", "&gt;")
            result.append(text_escaped)

        if tag_name in ALLOWED_TAGS:
            result.append(tag_text)
        else:
            escaped_tag = tag_text.replace("<", "&lt;").replace(">", "&gt;")
            result.append(escaped_tag)

        pos = end

    if pos < len(xml_string):
        tail = xml_string[pos:]
        tail_escaped = tail.replace("<", "&lt;").replace(">", "&gt;")
        result.append(tail_escaped)

    return ''.join(result)

def unescape_disallowed_tags(xml_string):
    return xml_string.replace("&lt;", "<").replace("&gt;", ">")

def validate_xml_structure(element, path=""):
    tag = element.tag
    current_path = f"{path}/{tag}" if path else tag

    if tag not in ALLOWED_TAGS:
        raise ValueError(f"Validation Error at {current_path}: Disallowed tag <{tag}> found.")

    if path == "" and tag != 'Think':
        raise ValueError("Validation Error: Root element must be <Think>.")

    if tag == 'Parallel':
        parent = element.getparent()
        if parent is None:
             raise ValueError(f"Validation Error at {current_path}: <Parallel> has no parent.")
        if parent.tag not in ['Think', 'Path']:
             raise ValueError(f"Validation Error at {current_path}: <Parallel> must be a direct child of <Think> or <Path>, not <{parent.tag}>.")

        children = list(element)
        if not children:
             raise ValueError(f"Validation Error at {current_path}: <Parallel> must not be empty.")

        if children[0].tag != 'Goal':
             raise ValueError(f"Validation Error at {current_path}: First child of <Parallel> must be <Goal>, not <{children[0].tag}>.")

        if children[-1].tag != 'Conclusion':
             raise ValueError(f"Validation Error at {current_path}: Last child of <Parallel> must be <Conclusion>, not <{children[-1].tag}>.")

        goal_count = 0
        path_count = 0
        conclusion_count = 0
        allowed_children_tags = {'Goal', 'Path', 'Conclusion'}

        for i, child in enumerate(children):
            child_tag = child.tag
            child_path = f"{current_path}/{child_tag}[{i+1}]"

            if child_tag not in allowed_children_tags:
                 raise ValueError(f"Validation Error at {child_path}: Invalid child <{child_tag}> found inside <Parallel>. Only <Goal>, <Path>, <Conclusion> are allowed.")

            if child_tag == 'Goal':
                 goal_count += 1
                 if i != 0:
                      raise ValueError(f"Validation Error at {child_path}: <Goal> must be the first child of <Parallel>.")
            elif child_tag == 'Path':
                 path_count += 1
                 if i == 0 or i == len(children) - 1:
                      raise ValueError(f"Validation Error at {child_path}: <Path> cannot be the first or last child of <Parallel>.")
            elif child_tag == 'Conclusion':
                 conclusion_count += 1
                 if i != len(children) - 1:
                      raise ValueError(f"Validation Error at {child_path}: <Conclusion> must be the last child of <Parallel>.")

        if goal_count != 1:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain exactly one <Goal>, found {goal_count}.")
        if conclusion_count != 1:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain exactly one <Conclusion>, found {conclusion_count}.")
        if path_count == 0:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain one or more <Path> elements.")

        goal_element = children[0]
        goal_descriptions = extract_goal_descriptions(goal_element)
        if goal_element is not None and not goal_element.xpath('.//Outline') and goal_descriptions:
             if len(goal_descriptions) != path_count:
                 raise ValueError(f"Validation Error at {current_path}: Number of <Path> elements ({path_count}) does not match number of 'Path: ...' lines in <Goal> ({len(goal_descriptions)}).")

    if tag in ['Goal', 'Path', 'Conclusion']:
         parent = element.getparent()
         if parent is None or parent.tag != 'Parallel':
              parent_tag = parent.tag if parent is not None else 'None'
              raise ValueError(f"Validation Error at {current_path}: <{tag}> must be a direct child of <Parallel>, not <{parent_tag}>.")

    for child in element:
        validate_xml_structure(child, current_path)

def extract_goal_descriptions(goal_element):
    descriptions = []
    if goal_element is not None and goal_element.text:
        goal_full_text = goal_element.text.strip()
        lines = goal_full_text.splitlines()
        for line in lines:
            stripped_line = line.strip()
            if re.match(r"^\s*Path.*?:", stripped_line, re.IGNORECASE):
                 descriptions.append(stripped_line)
    return descriptions

def serialize_xml_formatted(element, inline_tags, indent_level=0, indent_str="  "):
    indent = indent_str * indent_level
    output_parts = []
    attrs_str = ""
    if element.attrib:
        attrs = {k: v for k, v in element.attrib.items() if not k.startswith('__')}
        if attrs:
            attrs_str = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())

    if element.tag in inline_tags:
        text_content = element.text.strip() if element.text else ""
        child_output = ""
        for child in element:
             child_output += serialize_xml_formatted(child, inline_tags, indent_level + 1, indent_str)

        if child_output:
             output_parts.append(f"{indent}<{element.tag}{attrs_str}>\n")
             if text_content:
                  output_parts.append(f"{indent + indent_str}{text_content}\n")
             output_parts.append(child_output)
             output_parts.append(f"{indent}</{element.tag}>\n")
        else:
            output_parts.append(f"{indent}<{element.tag}{attrs_str}>{text_content}</{element.tag}>\n")

        if element.tail:
            tail_indent = indent
            tail_lines = element.tail.splitlines()
            indented_tail_lines = []
            for line in tail_lines:
                stripped_line = line.strip()
                if stripped_line:
                    indented_tail_lines.append(f"{tail_indent}{stripped_line}")
            if indented_tail_lines:
                 output_parts.append("\n".join(indented_tail_lines) + "\n")

    else:
        output_parts.append(f"{indent}<{element.tag}{attrs_str}>\n")

        if element.text:
            text_indent = indent + indent_str
            lines = element.text.splitlines()
            indented_lines = []
            for line in lines:
                stripped_line = line.strip()
                if stripped_line:
                    indented_lines.append(f"{text_indent}{stripped_line}")
            if indented_lines:
                output_parts.append("\n".join(indented_lines) + "\n")

        for child in element:
            output_parts.append(serialize_xml_formatted(child, inline_tags, indent_level + 1, indent_str))

        output_parts.append(f"{indent}</{element.tag}>\n")

        if element.tail:
            tail_indent = indent
            lines = element.tail.splitlines()
            indented_lines = []
            for line in lines:
                stripped_line = line.strip()
                if stripped_line:
                    indented_lines.append(f"{tail_indent}{stripped_line}")
            if indented_lines:
                output_parts.append("\n".join(indented_lines) + "\n")

    return "".join(output_parts)

def extract_outermost_parallel_blocks(root_element):
    xpath_query = "/Think/Parallel"
    try:
        parallel_blocks = root_element.xpath(xpath_query)
        return parallel_blocks
    except Exception as e:
        print(f"Error during XPath extraction: {e}")
        return []

def get_element_xml_without_tail(element):
    from copy import deepcopy
    temp_element = deepcopy(element)
    temp_element.tail = None
    return LET.tostring(temp_element, encoding='unicode', pretty_print=True)

def replace_parallel_block(original_parallel_element, new_parallel_xml_string):
    parent = original_parallel_element.getparent()
    if parent is None:
        print("Error: Cannot replace element - original element has no parent.")
        return False

    try:
        original_tail = original_parallel_element.tail
        
        new_parallel_xml_string = new_parallel_xml_string.strip()
        if not new_parallel_xml_string:
             print("Error: The provided XML string is empty or contains only whitespace.")
             return False
        print("ORIGINAL XML STRUCTURE:")
        print_element_structure(original_parallel_element)
        
        parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False, remove_comments=False)
        
        try:
            new_element = LET.fromstring(new_parallel_xml_string, parser)
            print("\nNEW XML STRUCTURE:")
            print_element_structure(new_element)
        except Exception as parse_error:
            print(f"New XML string: {new_parallel_xml_string}")
            print(f"XML PARSE ERROR: {parse_error}")
            print("TRYING TO WRAP WITH ROOT ELEMENT...")
            wrapped_xml = f"<root>{new_parallel_xml_string}</root>"
            root = LET.fromstring(wrapped_xml, parser)
            new_element = root[0]
            print("WRAPPED PARSING SUCCEEDED")
            print("\nNEW XML STRUCTURE (after wrapping):")
            print_element_structure(new_element)
            
        if new_element.tag != 'Parallel':
            print(f"Error: The provided XML string does not represent a <Parallel> block (found <{new_element.tag}>).")
            return False

        index = parent.index(original_parallel_element)
        parent.insert(index + 1, new_element)
        new_element.set('__temp_for_validation__', 'true')

        original_neighbors = {'prev': original_parallel_element.getprevious(),
                              'next': original_parallel_element.getnext(),
                              'parent': parent,
                              'index': index}

        parent.remove(original_parallel_element)

        try:
            print(f"Validating structure of the new <Parallel> block...")
            parent_path = parent.tag
            node_path_segment = f"{parent_path}[?]"
            validate_xml_structure(new_element, path=node_path_segment)
            print("New block structure is valid.")

            if '__temp_for_validation__' in new_element.attrib:
                 del new_element.attrib['__temp_for_validation__']
            
            new_element.tail = original_tail

            return True

        except ValueError as validation_error:
            print(f"Validation Error in new <Parallel> block: {validation_error}")
            parent.remove(new_element)
            if original_neighbors['prev'] is not None:
                 original_neighbors['prev'].addnext(original_parallel_element)
            elif original_neighbors['next'] is not None:
                 original_neighbors['next'].addprevious(original_parallel_element)
            elif parent is not None:
                 parent.insert(original_neighbors['index'], original_parallel_element)
            else:
                 print("Error: Could not restore original element - parent reference lost.")

            print("Replacement aborted due to validation failure. Original block restored.")
            return False
        except Exception as e_val:
             print(f"Unexpected error during validation of new block: {e_val}")
             try:
                 if new_element.getparent() is not None: parent.remove(new_element)
                 if original_parallel_element.getparent() is None:
                     restore_parent = original_neighbors.get('parent')
                     restore_index = original_neighbors.get('index')
                     if restore_parent is not None and restore_index is not None:
                        restore_parent.insert(restore_index, original_parallel_element)
                     else:
                        print("Error: Could not restore original element - parent/index info missing.")
             except Exception as e_restore:
                 print(f"Error trying to restore original element: {e_restore}")
             return False

    except LET.XMLSyntaxError as e_parse:
        print(f"Error parsing the new XML string: {e_parse}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during replacement: {e}")
        traceback.print_exc()
        return False

def print_element_structure(element, indent=0):
    indent_str = "  " * indent
    print(f"{indent_str}<{element.tag}>")
    
    for child in element:
        print_element_structure(child, indent + 1)
    
    print(f"{indent_str}</{element.tag}>")
    
async def async_generate_block(client, prompt, thinking, model, parallel_block):
    chat = client.aio.chats.create(
        model=model,
    )
    basic_info = "** Reasoning Chain **: \n" + "```markdown\n" + thinking + "\n```"
    basic_info = basic_info + "\n\n" + "**Parallel Block**: ```\n" + parallel_block + "\n```"
    prompt = basic_info + "\n\n" + prompt
    response = await chat.send_message(prompt)
    chat = (prompt, response.text)
    return response.text, chat

def main_loop(input_file_path, output_file_path, prompt_path):
    with open(input_file_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    escaped_content = escape_disallowed_tags(original_content)
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False, remove_comments=False)
    root = LET.fromstring(escaped_content, parser)

    validate_xml_structure(root)

    original_parallel_elements = extract_outermost_parallel_blocks(root)

    if not original_parallel_elements:
        print("No outermost <Parallel> blocks found in the document.")
    else:
        successful_replacements = 0
        for i in range(len(original_parallel_elements)):
            block_element = original_parallel_elements[i]

            if block_element.getparent() is None and i > 0:
                    print(f"\n--- Skipping Block {i+1} (element no longer in tree) ---")
                    continue

            print(f"\n--- Processing Block {i+1} ---")
            original_block_xml_string = get_element_xml_without_tail(block_element)

            current_full_doc_string = LET.tostring(root, encoding='unicode', pretty_print=True)

            api_key = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            model = "gemini-2.5-pro-preview-03-25"
            with open(prompt_path, 'r') as f:
                prompt = f.read()
            response, chat = asyncio.run(async_generate_block(client, prompt, current_full_doc_string, model, original_block_xml_string))
            modified_parallel_xml_string = response
            if "```markdown" in modified_parallel_xml_string:
                modified_parallel_xml_string = modified_parallel_xml_string.replace("```markdown", "")
            if "```" in modified_parallel_xml_string:
                modified_parallel_xml_string = modified_parallel_xml_string.replace("```", "")
            
            modified_parallel_xml_string = escape_disallowed_tags(modified_parallel_xml_string)

            if modified_parallel_xml_string is not None:
                print(f"\nAttempting to replace block {i+1}...")
                if block_element.getparent() is not None:
                        success = replace_parallel_block(block_element, modified_parallel_xml_string)
                        if success:
                            print(f"Successfully replaced block {i+1}.")
                            successful_replacements += 1
                        else:
                            print(f"Failed to replace block {i+1}.")
                else:
                        print(f"Skipping replacement for block {i+1} as it seems to have been detached from the tree unexpectedly.")

        if successful_replacements > 0:
            try:
                validate_xml_structure(root)
            except ValueError as final_val_error:
                    print(f"FINAL VALIDATION FAILED: {final_val_error}")

    formatted_xml_string = serialize_xml_formatted(root, INLINE_TAGS, indent_level=0, indent_str=INDENT_STRING)
    formatted_xml_string = formatted_xml_string.rstrip()

    final_output_content = unescape_disallowed_tags(formatted_xml_string)
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(final_output_content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Gemini reasoning.')
    parser.add_argument('--prompt', type=str, help='The prompt file to use.')
    parser.add_argument('--input', type=str, help='The input file to use.')
    parser.add_argument('--output_xml', type=str, help='The output path to store.')
    parser.add_argument('--start_idx', type=int, help='The start index of the input file.')
    parser.add_argument('--end_idx', type=int, help='The end index of the input file.')
    parser.add_argument('--xml_path', type=str, help='The xml file to use.')
    args = parser.parse_args()
    input_file_path = args.input
    output_path = args.output_xml
    xml_path = args.xml_path

    if not os.path.exists(xml_path):
        print(f"XML file does not exist: {xml_path}")
        sys.exit(1)
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    r1_dataset = []
    with open(args.input, 'r') as f:
        for line in f:
            r1_dataset.append(json.loads(line))
    logger.info(f"Loaded {len(r1_dataset)} examples from {input_file_path}")
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
    
    for i, r in enumerate(r1_dataset):
        uuid = r['uuid']
        xml_file_name = f"{uuid}_reasoning.xml"
        xml_file_path = os.path.join(xml_path, xml_file_name)
        output_file_path = os.path.join(output_path, xml_file_name)
        prompt_path = args.prompt
        try:
            main_loop(xml_file_path, output_file_path, prompt_path)
        except Exception as e:
            print(f"Error processing {xml_file_path}: {e}")
            continue