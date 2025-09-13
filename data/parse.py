import lxml.etree as LET
import os
import re
import traceback # Import traceback for detailed error reporting
import argparse
import json
import sys

# --- Configuration ---
# Define tags that should be rendered inline (no newlines before/after tag)
INLINE_TAGS = {}
# Define the indentation string (e.g., 2 spaces, 4 spaces, or a tab)
INDENT_STRING = ""
ALLOWED_TAGS = {"Think", "Parallel", "Goal", "Path", "Conclusion", "Summarization"}

# --- XML Validation Function ---
def validate_xml_structure(element, path=""):
    """
    Recursively validates the XML structure based on predefined rules.
    Raises ValueError if any rule is violated.
    """
    tag = element.tag
    current_path = f"{path}/{tag}" if path else tag

    # 1. Allowed Tags Check (applied recursively)
    if tag not in ALLOWED_TAGS:
        raise ValueError(f"Validation Error at {current_path}: Disallowed tag <{tag}> found.")

    # 2. Root Element Check (only for the initial call)
    if path == "" and tag != 'Think':
        raise ValueError("Validation Error: Root element must be <Think>.")

    # --- Specific Checks for <Parallel> elements ---
    if tag == 'Parallel':
        # 3. Specific Placement Rules for Parallel's parent
        parent = element.getparent()
        if parent is None: # Should not happen if root is <Think>
             raise ValueError(f"Validation Error at {current_path}: <Parallel> has no parent.")
        if parent.tag not in ['Think', 'Path']:
             raise ValueError(f"Validation Error at {current_path}: <Parallel> must be a direct child of <Think> or <Path>, not <{parent.tag}>.")

        # 4. Internal Parallel Structure
        children = list(element)
        if not children:
             raise ValueError(f"Validation Error at {current_path}: <Parallel> must not be empty.")

        # Check first child is Goal
        if children[0].tag != 'Goal':
             raise ValueError(f"Validation Error at {current_path}: First child of <Parallel> must be <Goal>, not <{children[0].tag}>.")

        # Check last child is Conclusion
        if children[-1].tag != 'Conclusion':
             raise ValueError(f"Validation Error at {current_path}: Last child of <Parallel> must be <Conclusion>, not <{children[-1].tag}>.")

        goal_count = 0
        path_count = 0
        conclusion_count = 0
        allowed_children_tags = {'Goal', 'Path', 'Conclusion'}

        for i, child in enumerate(children):
            child_tag = child.tag
            child_path = f"{current_path}/{child_tag}[{i+1}]"

            # Check if child tag is one of the allowed ones for Parallel
            if child_tag not in allowed_children_tags:
                 raise ValueError(f"Validation Error at {child_path}: Invalid child <{child_tag}> found inside <Parallel>. Only <Goal>, <Path>, <Conclusion> are allowed.")

            if child_tag == 'Goal':
                 goal_count += 1
                 if i != 0: # Should be caught by first child check, but good for robustness
                      raise ValueError(f"Validation Error at {child_path}: <Goal> must be the first child of <Parallel>.")
            elif child_tag == 'Path':
                 path_count += 1
                 if i == 0 or i == len(children) - 1:
                      raise ValueError(f"Validation Error at {child_path}: <Path> cannot be the first or last child of <Parallel>.")
            elif child_tag == 'Conclusion':
                 conclusion_count += 1
                 if i != len(children) - 1: # Should be caught by last child check
                      raise ValueError(f"Validation Error at {child_path}: <Conclusion> must be the last child of <Parallel>.")

        # Verify counts
        if goal_count != 1:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain exactly one <Goal>, found {goal_count}.")
        if conclusion_count != 1:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain exactly one <Conclusion>, found {conclusion_count}.")
        if path_count == 0:
            raise ValueError(f"Validation Error at {current_path}: <Parallel> must contain one or more <Path> elements.")

        # 5. Path/Goal Count Match
        goal_element = children[0] # We know it's the Goal element
        goal_descriptions = extract_goal_descriptions(goal_element)
        if len(goal_descriptions) != path_count:
             raise ValueError(f"Validation Error at {current_path}: Number of <Path> elements ({path_count}) does not match number of 'Path: ...' lines in <Goal> ({len(goal_descriptions)}).")


    # --- Specific Placement Rules for Goal, Path, Conclusion ---
    if tag in ['Goal', 'Path', 'Conclusion']:
         parent = element.getparent()
         if parent is None or parent.tag != 'Parallel':
              parent_tag = parent.tag if parent is not None else 'None'
              raise ValueError(f"Validation Error at {current_path}: <{tag}> must be a direct child of <Parallel>, not <{parent_tag}>.")


    # --- Recursively validate children ---
    for child in element:
        # Pass the current path for hierarchical error messages
        validate_xml_structure(child, current_path)

def extract_goal_descriptions(goal_element):
    """
    Extracts potential path description lines from the Goal element's text.
    Returns a list of stripped description lines.
    """
    descriptions = []
    if goal_element is not None and goal_element.text:
        goal_full_text = goal_element.text # Keep original spacing for splitlines
        lines = goal_full_text.splitlines()
        for line in lines:
            stripped_line = line.strip()
            # Regex to find lines likely describing paths (case-insensitive)
            if re.match(r"^\s*Path.*?:", stripped_line, re.IGNORECASE):
                 parts = stripped_line.split(':', 1)
                 if len(parts) > 1 and parts[1].strip():
                    descriptions.append(stripped_line)
    return descriptions


# --- Main function to modify the XML tree in place ---
# (Keep the function modify_xml_tree as defined previously, including the count check)
# This function now assumes all structural validation has already passed for the
# Parallel element it receives.
def modify_xml_tree(parallel_element, parent_id="", current_file=""):
    """
    Recursively traverses the XML tree WITHIN a Parallel element and applies modifications.
    Assumes structure and tag validation has already passed.
    Includes check for mismatch between Path count and Goal description count.
    """
    # --- 1. Process Goal - Extract descriptions ---
    goal_element = parallel_element.find('Goal') # Assumes Goal is present and first (validated before call)
    goal_descriptions_stripped = []
    original_goal_text = ""
    if goal_element is not None: # Still good practice to check
        original_goal_text = goal_element.text or ""
        goal_descriptions_stripped = extract_goal_descriptions(goal_element)
    num_descriptions = len(goal_descriptions_stripped)

    # --- 2. Find Path Elements ---
    # Findall works correctly as Path elements are direct children after Goal
    path_elements = parallel_element.findall('Path')
    num_paths = len(path_elements)

    # --- Check for Path/Goal count mismatch within this Parallel block ---
    
    if num_paths != num_descriptions:
        # (Error reporting for count mismatch remains the same)
        line_info = f" near line {parallel_element.sourceline}" if hasattr(parallel_element, 'sourceline') else ""
        parent_context = f" under parent path ID '{parent_id}'" if parent_id else " at top level"
        goal_text_preview = repr(original_goal_text[:100] + '...') if original_goal_text else "No text found"
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
        print(f"ERROR: Path/Goal Mismatch in <Parallel> element{line_info}{parent_context}.", file=sys.stderr)
        print(f"  - Error file path: {os.path.join(input_file_path, current_file)}", file=sys.stderr)
        print(f"  - Found {num_paths} <Path> elements.", file=sys.stderr)
        print(f"  - Found {num_descriptions} 'Path...:' description lines in <Goal>.", file=sys.stderr)
        print(f"  - Goal Text Snippet: {goal_text_preview}", file=sys.stderr)
        print(f"  - Extracted Descriptions: {goal_descriptions_stripped}", file=sys.stderr)
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", file=sys.stderr)
        print("Critical error: Path/Goal count mismatch. Stopping script.", file=sys.stderr)
        # sys.exit(1)

    # --- If counts match, continue with modifications ---
    path_id_map = []
    path_counter = 0

    # 3. First Pass over Paths: Generate IDs, Modify Paths, Store Mapping
    for path_element in path_elements: # Iterate only through Path elements
        path_counter += 1
        current_path_id = f"{parent_id}.{path_counter}" if parent_id else str(path_counter)

        if path_counter - 1 < len(goal_descriptions_stripped):
             path_id_map.append( (goal_descriptions_stripped[path_counter - 1], current_path_id) )

        # --- Modify Path Element ---
        if 'id' in path_element.attrib: del path_element.attrib['id']
        if 'goal_link' in path_element.attrib: del path_element.attrib['goal_link']
        id_line = f"{current_path_id}: "
        original_text = path_element.text if path_element.text else ""
        path_element.text = id_line + original_text.lstrip()

        # --- Recurse for nested Parallel elements ---
        # Find nested Parallel elements *within this Path*
        nested_parallels = path_element.findall('Parallel')
        for nested_parallel in nested_parallels:
             # *** Before recursive call, validate the nested Parallel's structure ***
             if not validate_parallel_internal_structure(nested_parallel, input_file_path):
                 # Error already printed by validation function
                 continue
             # *** If valid, make the recursive call ***
             modify_xml_tree(nested_parallel, current_path_id, current_file) # Recursive call

    # 4. Second Pass (Post-Path Iteration): Modify Goal Text
    if goal_element is not None and path_id_map:
        desc_to_id_lookup = {desc: pid for desc, pid in path_id_map}
        summarization_data = []
        processed_descriptions = set()

        if original_goal_text:
            original_lines = original_goal_text.splitlines()
            for line in original_lines:
                stripped_line = line.strip()
                if stripped_line in desc_to_id_lookup and stripped_line not in processed_descriptions:
                    pid = desc_to_id_lookup[stripped_line]
                    try:
                        parts = stripped_line.split(':', 1)
                        actual_desc = parts[1].strip() if len(parts) > 1 else ""
                        if actual_desc:
                            summarization_data.append({'pid': pid, 'desc': actual_desc})
                            processed_descriptions.add(stripped_line)
                    except Exception as e_proc:
                        print(f"WARNING: Failed to prepare Summarization data for line '{line}': {e_proc}", file=sys.stderr)

        # --- Clear existing Goal content and add Summarization ---
        goal_element.text = None
        for child in list(goal_element): goal_element.remove(child)
        if summarization_data:
            for item in summarization_data:
                summarization_elem = LET.SubElement(goal_element, "Outline")
                summarization_elem.text = f"{item['pid']}: {item['desc']}"

    # 5. Handle Conclusion (which is assumed present and last)
    # No modification logic needed for Conclusion currently based on requirements


# --- *** NEW: Helper Function for Internal Parallel Structure Validation *** ---
def validate_parallel_internal_structure(parallel_element, filename_for_error):
    """
    Validates the internal structure of a single <Parallel> element.
    Checks for: <Goal> first, <Path>+ in middle, <Conclusion> last.
    Returns True if valid, False otherwise (and prints error).
    """
    children = [child for child in parallel_element if isinstance(child, LET._Element)] # Get only element children
    is_valid = True
    error_messages = []
    min_children = 3 # Need Goal, Path, Conclusion

    if len(children) < min_children:
        error_messages.append(f"  - Expected at least {min_children} children (<Goal>, <Path>+, <Conclusion>), found {len(children)}")
        is_valid = False
    else:
        # Check first element
        if children[0].tag != 'Goal':
            error_messages.append(f"  - Expected first child to be <Goal>, found <{children[0].tag}>")
            is_valid = False
        # Check last element
        if children[-1].tag != 'Conclusion':
            error_messages.append(f"  - Expected last child to be <Conclusion>, found <{children[-1].tag}>")
            is_valid = False
        # Check middle elements
        middle_children = children[1:-1]
        if not middle_children: # Need at least one Path
             error_messages.append(f"  - Expected at least one <Path> between <Goal> and <Conclusion>, found none.")
             is_valid = False
        elif not all(child.tag == 'Path' for child in middle_children):
            incorrect_middle_tags = {child.tag for child in middle_children if child.tag != 'Path'}
            error_messages.append(f"  - Expected only <Path> children between <Goal> and <Conclusion>, found: {', '.join(f'<{t}>' for t in incorrect_middle_tags)}")
            is_valid = False

    if not is_valid:
         print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
         line_info = f" near line {parallel_element.sourceline}" if hasattr(parallel_element, 'sourceline') else ""
         print(f"ERROR: Invalid internal structure for <Parallel> element{line_info} in '{filename_for_error}'.", file=sys.stderr)
         print("Structure must be: <Goal>, followed by one or more <Path>, followed by <Conclusion>.", file=sys.stderr)
         for msg in error_messages:
             print(msg, file=sys.stderr)
         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", file=sys.stderr)
         return False # Indicate failure
    return True # Indicate success


# --- Modified custom serialization function ---
# (Keep the function serialize_xml_formatted as defined previously)
def serialize_xml_formatted(element, inline_tags, indent_level=0, indent_str="  "):
    """ Serializes XML with custom formatting """
    # ... (implementation remains the same) ...
    indent = indent_str * indent_level
    output_parts = []
    attrs_str = ""
    if element.attrib:
        attrs = {k: v for k, v in element.attrib.items() if not k.startswith('__')}
        if attrs: attrs_str = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())

    if element.tag in inline_tags:
        text_content = element.text.strip() if element.text else ""
        output_parts.append(f"{indent}<{element.tag}{attrs_str}>{text_content}</{element.tag}>") # No \n for inline
        if element.tail and element.tail.strip():
             # Tail of inline element needs careful handling - assume it starts on same line or next with indent?
             # Simple approach: add stripped tail text after space
             output_parts.append(" " + element.tail.strip())
        output_parts.append("\n") # End line after inline tag and its tail

    else:
        # Block-level tag
        output_parts.append(f"{indent}<{element.tag}{attrs_str}>\n")
        if element.text and element.text.strip():
            text_indent = indent + indent_str if indent_str else indent
            for line in element.text.strip().splitlines():
                 output_parts.append(f"{text_indent}{line.strip()}\n")
        for child in element:
            output_parts.append(serialize_xml_formatted(child, inline_tags, indent_level + 1, indent_str))
        output_parts.append(f"{indent}</{element.tag}>\n")
        if element.tail and element.tail.strip():
             # Tail of block element starts at same indent level
             for line in element.tail.strip().splitlines():
                 output_parts.append(f"{indent}{line.strip()}\n")

    return "".join(output_parts)


# --- Main Execution Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process XML files')
    parser.add_argument('--input_file_path', type=str, help='Path to the input directory')
    parser.add_argument('--output_file_path', type=str, help='Path to the output directory')
    parser.add_argument('--refer_file_path', type=str, help='Path to the reference file', default=None)
    parser.add_argument('--pattern', type=str, help='pattern of the file')
    args = parser.parse_args()

    input_file_path = args.input_file_path
    output_file_path = args.output_file_path
    refer_file_path = args.refer_file_path
    total = 0
    success = 0
    
    if args.pattern == 's1':
        if not os.path.exists(output_file_path):
            os.makedirs(output_file_path)
        if not os.path.exists(input_file_path):
            print(f"Error: Input file not found at path: {os.path.abspath(input_file_path)}")
        else:
            for file in os.listdir(input_file_path):
                file_path = os.path.join(input_file_path, file)
                total += 1
                try:
                    # --- Step 1: Parse the input XML ---
                    # print(f"Parsing XML file: '{file_path}'...")
                    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False, remove_comments=False, recover=False, collect_ids=False)
                    try:
                        tree = LET.parse(file_path, parser)
                    except LET.XMLSyntaxError as e:
                        print(f"CRITICAL XML Parsing Error in file '{file_path}': {e}", file=sys.stderr)
                        # sys.exit(1)
                        continue
                    # print("Parsing successful.")
                    root = tree.getroot()
                    
                    # --- Step 1.5: Validate the XML structure ---
                    validate_xml_structure(root) # Call the validation function


                    # --- Step 2: Modify the XML tree in memory ---
                    parallel_tags_found = False

                    # Find and process all top-level <Parallel> elements and their descendants
                    for top_parallel_element in root.findall('Parallel'):
                        modify_xml_tree(top_parallel_element, parent_id="") # Call the main modification function
                        parallel_tags_found = True


                    if not parallel_tags_found:
                        # If no <Parallel> tags anywhere, modifications might not happen as expected
                        print("Warning: No <Parallel> tags found in the document.")


                    # --- Step 3: Serialize the modified tree using the custom function ---
                    # Call the serialization function starting from the root element
                    # Ensure INLINE_TAGS and INDENT_STRING are passed
                    formatted_xml_string = serialize_xml_formatted(root, INLINE_TAGS, indent_level=0, indent_str=INDENT_STRING)
                    # Remove any trailing whitespace from the final string
                    formatted_xml_string = formatted_xml_string.rstrip()


                    # --- Step 4: Add XML declaration and write to output file ---
                    # print(f"Writing formatted XML to '{output_file_path}'...")
                    # Prepend the standard XML declaratio
                    
                    final_output_content = formatted_xml_string
                    with open(os.path.join(output_file_path, file.replace('.txt', '.xml')), 'w', encoding='utf-8') as f:
                        f.write(final_output_content)
                    # print("Output file written successfully.")
                    success += 1

                # --- Error Handling ---
                except SystemExit:
                    print("Script terminated due to critical error or validation failure.", file=sys.stderr)
                    continue
                except LET.XMLSyntaxError as e:
                    print(f"XML Parsing Error in file '{file_path}': {e}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    continue
                except IOError as e:
                    print(f"Error writing output file '{output_file_path}': {e}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"An unexpected error occurred during processing of '{file_path}': {e}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    continue

        print(f"Total files processed: {total}")
        print(f"Files processed successfully: {success}")
        print(f"Files processed unsuccessfully: {total - success}")

    elif args.pattern == 'r1':
    
        refer_data = {}
        with open(refer_file_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                refer_data[data['uuid']] = data

        # Check if the input file exists
        if not os.path.exists(input_file_path):
            print(f"Error: Input file not found at path: {os.path.abspath(input_file_path)}")
        else:
            for file in os.listdir(input_file_path):
                total += 1
                try:
                    uuid = file.split('_reasoning')[0]
                    if uuid not in refer_data:
                        print(f"Warning: UUID {uuid} not found in reference data.")
                        continue
                    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False, remove_comments=False)
                    tree = LET.parse(os.path.join(input_file_path, file), parser)
                    root = tree.getroot() # Get the root element (e.g., <Think>)
                    
                    # --- *** Step 1.5: Validate Structure (NEW) *** ---
                    # print("Validating XML structure: Checking Goal/Path/Conclusion placement...")
                    # Find any Goal, Path, or Conclusion element whose immediate parent is NOT Parallel
                    # This XPath selects any element (*) that IS Goal, Path, or Conclusion [self::...]
                    # AND whose immediate parent element is NOT Parallel [not(parent::Parallel)]
                    xpath_expression = ".//*[self::Goal or self::Path or self::Conclusion][not(parent::Parallel)]"
                    violating_elements = root.xpath(xpath_expression)
                    if violating_elements:
                        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
                        print(f"ERROR: Invalid XML structure detected in '{input_file_path}'.", file=sys.stderr)
                        print("Requirement: <Goal>, <Path>, and <Conclusion> must be direct children of <Parallel>.", file=sys.stderr)
                        print("The following tags were found incorrectly placed:", file=sys.stderr)
                        error_found = False
                        for elem in violating_elements:
                            # Double check parent exists, though XPath should guarantee it for non-root elements
                            parent = elem.getparent()
                            if parent is not None:
                                line_info = f" near line {elem.sourceline}" if hasattr(elem, 'sourceline') else ""
                                parent_tag = parent.tag
                                print(f"  - <{elem.tag}> found inside <{parent_tag}> (expected <Parallel>){line_info}", file=sys.stderr)
                                error_found = True
                            # else: # This case means Goal/Path/Conclusion is the root element, which is also invalid
                            #    print(f"  - <{elem.tag}> found as the root element (must be inside <Parallel>)", file=sys.stderr)
                            #    error_found = True

                        # If the loop didn't find errors but list wasn't empty (e.g., root case if handled)
                        if not error_found and violating_elements:
                            print("  - An element (Goal/Path/Conclusion) might be the root or have no parent.", file=sys.stderr)


                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", file=sys.stderr)
                        # sys.exit(1) # Stop script execution due to invalid structure
                    else:
                        print("XML structure validation passed.")

                    # print("Starting XML modification (updating Goal, Path elements)...")
                    parallel_tags_found = False

                    for top_parallel_element in root.findall('Parallel'):
                        modify_xml_tree(top_parallel_element, parent_id="", current_file=file)
                        parallel_tags_found = True


                    if not parallel_tags_found:
                        # If no <Parallel> tags anywhere, modifications might not happen as expected
                        print("Warning: No <Parallel> tags found in the document.")
                    # print("Modification complete.")


                    # --- Step 3: Serialize the modified tree using the custom function ---
                    # print("Generating formatted XML string...")
                    # Call the serialization function starting from the root element
                    # Ensure INLINE_TAGS and INDENT_STRING are passed
                    formatted_xml_string = serialize_xml_formatted(root, INLINE_TAGS, indent_level=0, indent_str=INDENT_STRING)
                    # Remove any trailing whitespace from the final string
                    formatted_xml_string = formatted_xml_string.rstrip()
                    # print("String generation complete.")

                    # --- Step 4: Add XML declaration and write to output file ---
                    # print(f"Writing formatted XML to '{output_file_path}'...")
                    # Prepend the standard XML declaration
                    final_output_content = formatted_xml_string + '\n' + refer_data[uuid]['output']

                    # Write the complete string to the output file using UTF-8 encoding
                    with open(os.path.join(output_file_path, file.replace('.txt', '.xml')), 'w', encoding='utf-8') as f:
                        f.write(final_output_content)
                    # print("Output file written successfully.")
                    success += 1
                # --- Error Handling ---
                except LET.XMLSyntaxError as e:
                    # Handle XML parsing errors
                    print(f"XML Parsing Error in file '{input_file_path + file}': {e}")
                    continue
                except IOError as e:
                    # Handle file writing errors
                    print(f"Error writing output file '{output_file_path + file}': {e}")
                    continue
                except Exception as e:
                    # Catch any other unexpected errors
                    print(f"An unexpected error occurred while processing '{input_file_path + file}': {e}")
                    print(traceback.format_exc()) # Print traceback for debugging details
                    continue

        print(f"Total files processed: {total}")
        print(f"Files processed successfully: {success}")
        print(f"Files processed unsuccessfully: {total - success}")
