import ast
import keyword
import os
import xml.etree.ElementTree as ET
import re


def extract_dynamic_fields_and_create_context(attrs_str):
    """
    Extract dynamic fields from the attrs_str by more accurately distinguishing between dynamic fields
    and string literals, creating a context mapping these fields to placeholders, and also prepare a reverse
    mapping to convert placeholders back to dynamic fields.
    """
    # Match identifiers that are not within quotes
    dynamic_field_pattern = re.compile(r"(\b\w+\b)(?=(?:[^\"']|\"[^\"]*\"|'[^']*')*$)")

    # Extract all potential fields
    potential_fields = set(re.findall(dynamic_field_pattern, attrs_str))

    # Filter out numeric values, reserved Python keywords, and known literals like True, False, None
    dynamic_fields = {field for field in potential_fields if not field.isnumeric()
                      and not keyword.iskeyword(field) and field not in ['True', 'False', 'None']}

    # Creating context for placeholders and reverse context for mapping back
    context = {field: f"'context[{field}]'" for field in dynamic_fields}
    reverse_context = {v: k for k, v in context.items()}

    return context, reverse_context, dynamic_fields


def revert_placeholders_to_dynamic_fields(prepared_str, reverse_context):
    """
    Revert placeholders in the prepared string back to their original dynamic field names using reverse_context.
    """
    for placeholder, field in reverse_context.items():
        prepared_str = prepared_str.replace(placeholder, field)
    return prepared_str


def replace_fields_with_context(attrs_str, context):
    """
    Replace dynamic fields in attrs_str with their corresponding placeholders from the context.
    """
    for field, placeholder in context.items():
        attrs_str = attrs_str.replace(field, placeholder)
    return attrs_str


def prepare_expression(attrs_str):
    """
    Prepare the expression by extracting dynamic fields, creating contexts, and replacing fields with placeholders.
    """
    context, reverse_context, dynamic_fields = extract_dynamic_fields_and_create_context(attrs_str)
    prepared_str = replace_fields_with_context(attrs_str, context)
    return prepared_str, context, reverse_context, dynamic_fields


def convert_domain_to_python(domain):
    string_modified = False
    context = {}
    reverse_context = {}
    dynamic_fields = []

    if isinstance(domain, str):
        prepared_str, context, reverse_context, dynamic_fields = prepare_expression(domain)
        domain = ast.literal_eval(prepared_str)
        string_modified = True

    def convert_tuple_to_expression(domain_tuple):
        field, operator, value = domain_tuple
        if operator == '=':
            operator = '=='
        return f"{field} {operator} {repr(value)}"

    expressions = []
    operators = []

    if len(domain)==3 and '|' not in domain and '&' not in domain:
        expressions.append(convert_tuple_to_expression(domain))
    else:
        for item in domain:
            if isinstance(item, tuple):
                expressions.append(convert_tuple_to_expression(item))
            elif item == '|':
                operators.append(' or ')
            elif item == '&':
                operators.append(' and ')

    # Apply operators to expressions
    while len(expressions) > 1 and operators:
        op = operators.pop()
        right = expressions.pop()
        left = expressions.pop()
        expressions.append(f"({right}{op}{left})")

    # If there are multiple expressions without operators, join them with 'and'
    if len(expressions) > 1:
        expressions = [' and '.join(expressions)]

    if string_modified:
        expressions = revert_placeholders_to_dynamic_fields(expressions[0], reverse_context)
        return expressions
    else:
        return expressions[0] if expressions else ''


def attrs_to_dict(attrs_str):
    """
    Convert the Enigma7 attrs string to a dictionary. This handles the specific structure used by Enigma7,
    which is not strictly valid JSON.
    """
    attrs_str = attrs_str.replace('  ', '')
    # Define a regular expression pattern to match key-value pairs
    pattern = r"'(\w+)'\s*:\s*\[(.*?)\](?=\s*(?:,|\}))"

    # Extract key-value pairs using regular expressions
    key_values = re.findall(pattern, attrs_str)
    converted_dict = {}
    if not len(key_values):
        raise Exception("Unable to find Key Values.")

    def safe_eval(value):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as e:
            return value

    # Create a dictionary from extracted key-value pairs
    for key, value in key_values:
        # Evaluate the value as a Python expression using safe_eval function
        evaluated_value = safe_eval(value)

        # Update the dictionary with the evaluated value
        converted_dict[key] = evaluated_value
    return converted_dict


def modify_field_element(field):
    """
    Modifies a field element by converting its 'attrs' attribute into individual XML attributes.
    """
    if 'attrs' in field.attrib:
        attrs_dict = attrs_to_dict(field.attrib['attrs'])
        for attr, expr in attrs_dict.items():
            field.set(attr, convert_domain_to_python(expr))
        del field.attrib['attrs']


def traverse_and_process(element):
    """
    Recursively traverse and process each element in the XML tree to convert 'attrs'.
    """
    if 'attrs' in element.attrib:
        modify_field_element(element)
    for child in element:
        traverse_and_process(child)


def modify_xml_view(input_path, output_path):
    try:
        """
        Loads the input XML, modifies it, and saves it to the output path.
        """
        tree = ET.parse(input_path)
        root = tree.getroot()

        traverse_and_process(root)

        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        print(f"Modified XML has been saved to: {output_path}")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    folder_path = r'D:\\projects\\xaana_enigma_17\\addons\\report_py3o_fusion_server\\views'


    # Iterate through each file in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".xml"):
            input_path = os.path.join(folder_path, filename)
            output_path = os.path.join(folder_path, f"{filename}")
            modify_xml_view(input_path, output_path)