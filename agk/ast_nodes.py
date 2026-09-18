"""AST nodes for AGK-Real v1.

Every node carries source line/column for error reporting (file:line:col).
Positions are excluded from equality (compare=False) so tests can assert
AST shape without caring about positions.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any


@dataclass
class Node:
    line: int = field(default=0, compare=False, kw_only=True)
    col: int = field(default=0, compare=False, kw_only=True)


# -- program ------------------------------------------------------------

@dataclass
class Program(Node):
    statements: List[Any]  # top-level: Import, ConstantDef, FunctionDef, ClassDef


@dataclass
class Import(Node):
    module: str  # e.g. "math", "os.path"


@dataclass
class ConstantDef(Node):
    name: str
    type_name: str
    value: Any  # IntLit | FloatLit | StringLit | BoolLit


@dataclass
class Param(Node):
    name: str
    type_name: str
    default: Optional[Any] = None  # v2: literal default value


@dataclass
class FunctionDef(Node):
    name: str
    params: List[Param]
    return_type: Optional[str]
    body: List[Any]


@dataclass
class ConstructorDef(Node):
    params: List[Param]
    body: List[Any]


@dataclass
class FieldDecl(Node):
    name: str
    type_name: str


@dataclass
class ClassDef(Node):
    name: str
    base: Optional[str]
    fields: List[FieldDecl]
    constructor: Optional[ConstructorDef]
    methods: List[FunctionDef]


# -- statements ----------------------------------------------------------

@dataclass
class CreateStmt(Node):
    name: str
    type_name: str


@dataclass
class SetStmt(Node):
    name: str
    value: Any


@dataclass
class SetAttr(Node):
    """Assignment to an attribute, e.g. self.name = value.
    Produced by the semantic phase when `set <field>` targets a class field."""
    obj: Any
    attr: str
    value: Any


@dataclass
class IfStmt(Node):
    condition: Any
    then_body: List[Any]
    elifs: List[Tuple[Any, List[Any]]] = field(default_factory=list)
    else_body: Optional[List[Any]] = None


@dataclass
class WhileStmt(Node):
    condition: Any
    body: List[Any]


@dataclass
class ForEachStmt(Node):
    var: str
    iterable: Any
    body: List[Any]


@dataclass
class ForRangeStmt(Node):
    """v2: `for i from <start> to <end> [step <step>]:` — inclusive."""
    var: str
    start: Any
    end: Any
    step: Optional[Any]  # None => step 1
    body: List[Any]


@dataclass
class TryStmt(Node):
    """v2: try/catch/finally. catch_name None => bare `catch:`."""
    body: List[Any]
    catch_name: Optional[str]
    catch_body: Optional[List[Any]]
    finally_body: Optional[List[Any]]


@dataclass
class RaiseStmt(Node):
    """v2: `raise <expr>` or bare `raise` (re-raise)."""
    value: Optional[Any]


@dataclass
class ReturnStmt(Node):
    value: Optional[Any]  # None => bare `return`


@dataclass
class ExprStmt(Node):
    """A bare expression used as a statement (e.g. a call like print(x))."""
    expr: Any


# -- expressions ----------------------------------------------------------

@dataclass
class IntLit(Node):
    value: int


@dataclass
class FloatLit(Node):
    value: float


@dataclass
class StringLit(Node):
    value: str


@dataclass
class BoolLit(Node):
    value: bool


@dataclass
class Name(Node):
    id: str


@dataclass
class BinOp(Node):
    left: Any
    op: str      # '+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>=', 'and', 'or'
    right: Any


@dataclass
class UnaryOp(Node):
    op: str      # '-', 'not'
    operand: Any


@dataclass
class Call(Node):
    func: Any
    args: List[Any]


@dataclass
class Attribute(Node):
    obj: Any
    attr: str


@dataclass
class Index(Node):
    obj: Any
    index: Any


@dataclass
class ListLit(Node):
    elements: List[Any]


@dataclass
class DictLit(Node):
    pairs: List[Tuple[Any, Any]]
