"""Tree-sitter grammar per file extension and the node types the graph reads from it."""
import os
from dataclasses import dataclass, field, replace

KEYWORD = "keyword"


@dataclass(frozen=True)
class Language:
    module: str
    grammar: str
    types: dict
    members: dict
    containers: frozenset
    calls: frozenset
    accesses: frozenset
    strings: frozenset
    parents: frozenset = frozenset()
    heritage: frozenset = frozenset()
    parent_fields: tuple = ()
    names: dict = field(default_factory=dict)
    body_opener: str = "{"


SWIFT_MEMBERS = ("function_declaration", "init_declaration", "property_declaration", "subscript_declaration",
                 "protocol_function_declaration", "protocol_property_declaration", "deinit_declaration")

SWIFT = Language(
    "tree_sitter_swift", "language",
    types={"class_declaration": KEYWORD, "protocol_declaration": KEYWORD},
    members={t: t.replace("_declaration", "") for t in SWIFT_MEMBERS},
    containers=frozenset({"class_body", "protocol_body", "enum_class_body", "statements"}),
    calls=frozenset({"call_expression"}), accesses=frozenset({"navigation_suffix"}),
    strings=frozenset({"line_string_literal"}), parents=frozenset({"inheritance_specifier"}),
    names={"init_declaration": "init", "deinit_declaration": "deinit", "subscript_declaration": "subscript"})

KOTLIN = Language(
    "tree_sitter_kotlin", "language",
    types={"class_declaration": KEYWORD, "object_declaration": "class"},
    members={"function_declaration": "function", "property_declaration": "property", "secondary_constructor": "init"},
    containers=frozenset({"class_body", "enum_class_body", "companion_object"}),
    calls=frozenset({"call_expression"}), accesses=frozenset({"navigation_expression"}),
    strings=frozenset({"string_literal"}), parents=frozenset({"delegation_specifier"}),
    heritage=frozenset({"delegation_specifiers"}), names={"secondary_constructor": "init"})

TYPESCRIPT = Language(
    "tree_sitter_typescript", "language_typescript",
    types={"class_declaration": "class", "abstract_class_declaration": "class",
           "interface_declaration": "protocol", "enum_declaration": "enum"},
    members={"method_definition": "function", "method_signature": "function", "abstract_method_signature": "function",
             "function_declaration": "function", "generator_function_declaration": "function",
             "public_field_definition": "property", "field_definition": "property", "property_signature": "property",
             "lexical_declaration": "property", "type_alias_declaration": "type"},
    containers=frozenset({"export_statement", "class_body", "interface_body", "ambient_declaration",
                          "internal_module", "module", "statement_block"}),
    calls=frozenset({"call_expression", "new_expression"}), accesses=frozenset({"member_expression"}),
    strings=frozenset({"string", "template_string"}),
    heritage=frozenset({"class_heritage", "extends_clause", "implements_clause", "extends_type_clause"}))

PYTHON = Language(
    "tree_sitter_python", "language",
    types={"class_definition": "class"}, members={"function_definition": "function"},
    containers=frozenset({"decorated_definition", "block"}),
    calls=frozenset({"call"}), accesses=frozenset({"attribute"}), strings=frozenset({"string"}),
    heritage=frozenset({"argument_list"}), body_opener=":\n")

JAVA = Language(
    "tree_sitter_java", "language",
    types={"class_declaration": "class", "record_declaration": "class", "interface_declaration": "protocol",
           "enum_declaration": "enum"},
    members={"method_declaration": "function", "constructor_declaration": "init", "field_declaration": "property",
             "constant_declaration": "property"},
    containers=frozenset({"class_body", "interface_body", "enum_body", "enum_body_declarations"}),
    calls=frozenset({"method_invocation", "object_creation_expression"}), accesses=frozenset({"field_access"}),
    strings=frozenset({"string_literal"}),
    heritage=frozenset({"superclass", "super_interfaces", "extends_interfaces", "type_list"}),
    names={"constructor_declaration": "init"})

RUST = Language(
    "tree_sitter_rust", "language",
    types={"struct_item": "struct", "union_item": "struct", "enum_item": "enum", "trait_item": "protocol",
           "impl_item": "extension"},
    members={"function_item": "function", "function_signature_item": "function", "const_item": "property",
             "static_item": "property", "type_item": "type"},
    containers=frozenset({"mod_item", "declaration_list"}),
    calls=frozenset({"call_expression", "macro_invocation"}), accesses=frozenset({"field_expression"}),
    strings=frozenset({"string_literal", "raw_string_literal"}), parent_fields=("trait",))

BY_EXTENSION = {
    ".swift": SWIFT, ".kt": KOTLIN, ".kts": KOTLIN, ".py": PYTHON, ".java": JAVA, ".rs": RUST,
    ".ts": TYPESCRIPT, ".mts": TYPESCRIPT, ".cts": TYPESCRIPT, ".tsx": replace(TYPESCRIPT, grammar="language_tsx"),
    **dict.fromkeys((".js", ".jsx", ".mjs", ".cjs"), replace(TYPESCRIPT, module="tree_sitter_javascript", grammar="language")),
}
EXTENSIONS = tuple(BY_EXTENSION)


def of(path):
    return BY_EXTENSION.get(os.path.splitext(path)[1])
