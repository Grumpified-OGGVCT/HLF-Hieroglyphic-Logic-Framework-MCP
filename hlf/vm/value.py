"""
HLF Value Types
Runtime values for the VM
"""

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum, auto
from dataclasses import dataclass, field

class ValueType(Enum):
    NIL = auto()
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    ATOM = auto()
    LIST = auto()
    TUPLE = auto()
    RECORD = auto()
    FUNCTION = auto()
    CLOSURE = auto()

@dataclass
class Value:
    """Runtime value"""
    type: ValueType
    data: Any
    
    def __init__(self, type_: ValueType, data: Any):
        self.type = type_
        self.data = data
    
    # Constructors
    @classmethod
    def nil(cls) -> "Value":
        return cls(ValueType.NIL, None)
    
    @classmethod
    def bool(cls, value: bool) -> "Value":
        return cls(ValueType.BOOL, bool(value))
    
    @classmethod
    def int(cls, value: int) -> "Value":
        return cls(ValueType.INT, int(value))
    
    @classmethod
    def float(cls, value: float) -> "Value":
        return cls(ValueType.FLOAT, float(value))
    
    @classmethod
    def string(cls, value: str) -> "Value":
        return cls(ValueType.STRING, value)
    
    @classmethod
    def atom(cls, value: str) -> "Value":
        return cls(ValueType.ATOM, value)
    
    @classmethod
    def list_(cls, elements: List["Value"]) -> "Value":
        return cls(ValueType.LIST, elements)
    
    @classmethod
    def tuple_(cls, elements: List["Value"]) -> "Value":
        return cls(ValueType.TUPLE, tuple(elements))
    
    @classmethod
    def record(cls, fields: Dict[str, "Value"]) -> "Value":
        return cls(ValueType.RECORD, fields)
    
    @classmethod
    def function(cls, func) -> "Value":
        return cls(ValueType.FUNCTION, func)
    
    # Type checking
    def is_nil(self) -> bool:
        return self.type == ValueType.NIL
    
    def is_bool(self) -> bool:
        return self.type == ValueType.BOOL
    
    def is_int(self) -> bool:
        return self.type == ValueType.INT
    
    def is_float(self) -> bool:
        return self.type == ValueType.FLOAT
    
    def is_number(self) -> bool:
        return self.is_int() or self.is_float()
    
    def is_string(self) -> bool:
        return self.type == ValueType.STRING
    
    def is_atom(self) -> bool:
        return self.type == ValueType.ATOM
    
    def is_list(self) -> bool:
        return self.type == ValueType.LIST
    
    def is_tuple(self) -> bool:
        return self.type == ValueType.TUPLE
    
    def is_record(self) -> bool:
        return self.type == ValueType.RECORD
    
    def is_function(self) -> bool:
        return self.type in (ValueType.FUNCTION, ValueType.CLOSURE)
    
    # Accessors
    def as_bool(self) -> bool:
        if self.is_bool():
            return self.data
        if self.is_nil():
            return False
        if self.is_int():
            return self.data != 0
        return True
    
    def as_int(self) -> int:
        if self.is_int():
            return self.data
        if self.is_float():
            return int(self.data)
        if self.is_bool():
            return 1 if self.data else 0
        raise TypeError(f"Cannot convert {self.type} to int")
    
    def as_float(self) -> float:
        if self.is_float():
            return self.data
        if self.is_int():
            return float(self.data)
        raise TypeError(f"Cannot convert {self.type} to float")
    
    def as_string(self) -> str:
        if self.is_string():
            return self.data
        if self.is_atom():
            return self.data
        return str(self)
    
    def as_atom(self) -> str:
        if self.is_atom():
            return self.data
        raise TypeError(f"Cannot convert {self.type} to atom")
    
    def as_list(self) -> List["Value"]:
        if self.is_list():
            return self.data
        raise TypeError(f"Cannot convert {self.type} to list")
    
    def as_tuple(self) -> Tuple["Value", ...]:
        if self.is_tuple():
            return self.data
        raise TypeError(f"Cannot convert {self.type} to tuple")
    
    def as_record(self) -> Dict[str, "Value"]:
        if self.is_record():
            return self.data
        raise TypeError(f"Cannot convert {self.type} to record")
    
    # Collection operations
    def __len__(self) -> int:
        if self.is_list():
            return len(self.data)
        if self.is_tuple():
            return len(self.data)
        if self.is_string():
            return len(self.data)
        if self.is_record():
            return len(self.data)
        raise TypeError(f"Cannot get length of {self.type}")
    
    def __iter__(self):
        if self.is_list():
            return iter(self.data)
        if self.is_tuple():
            return iter(self.data)
        raise TypeError(f"Cannot iterate over {self.type}")
    
    def __getitem__(self, key):
        if self.is_list():
            return self.data[key]
        if self.is_tuple():
            return self.data[key]
        if self.is_record():
            return self.data[key]
        raise TypeError(f"Cannot index {self.type}")
    
    def get_index(self, idx: int) -> "Value":
        """Safe index access"""
        if self.is_list():
            if 0 <= idx < len(self.data):
                return self.data[idx]
            return Value.nil()
        if self.is_tuple():
            if 0 <= idx < len(self.data):
                return self.data[idx]
            return Value.nil()
        raise TypeError(f"Cannot index {self.type}")
    
    def get_field(self, name: str) -> "Value":
        """Get record field"""
        if self.is_record():
            return self.data.get(name, Value.nil())
        raise TypeError(f"Cannot access fields on {self.type}")
    
    # Equality
    def __eq__(self, other) -> bool:
        if not isinstance(other, Value):
            return False
        if self.type != other.type:
            # Compare numbers
            if self.is_number() and other.is_number():
                return self.as_float() == other.as_float()
            return False
        return self.data == other.data
    
    def __hash__(self) -> int:
        return hash((self.type, self._hashable_data()))
    
    def _hashable_data(self):
        """Convert data to hashable form"""
        if self.is_tuple():
            return tuple(v._hashable_data() for v in self.data)
        if self.is_list():
            return tuple(v._hashable_data() for v in self.data)
        if self.is_record():
            return tuple(sorted((k, v._hashable_data()) for k, v in self.data.items()))
        return self.data
    
    # Representation
    def __repr__(self) -> str:
        if self.is_nil():
            return "nil"
        if self.is_bool():
            return "true" if self.data else "false"
        if self.is_int():
            return str(self.data)
        if self.is_float():
            return repr(self.data)
        if self.is_string():
            return repr(self.data)
        if self.is_atom():
            return f":{self.data}"
        if self.is_list():
            return f"[{', '.join(repr(v) for v in self.data)}]"
        if self.is_tuple():
            return f"({', '.join(repr(v) for v in self.data)})"
        if self.is_record():
            fields = ', '.join(f"{k}: {repr(v)}" for k, v in sorted(self.data.items()))
            return f"{{{fields}}}"
        return f"<{self.type.name}: {self.data}>"
    
    def __str__(self) -> str:
        if self.is_string():
            return self.data
        return self.__repr__()
    
    # Copy
    def copy(self) -> "Value":
        """Deep copy"""
        if self.is_list():
            return Value.list_([v.copy() for v in self.data])
        if self.is_tuple():
            return Value.tuple_([v.copy() for v in self.data])
        if self.is_record():
            return Value.record({k: v.copy() for k, v in self.data.items()})
        # Immutable types
        return Value(self.type, self.data)
    
    # Conversion
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type.name,
            "value": self._to_serializable()
        }
    
    def _to_serializable(self):
        """Convert data to serializable form"""
        if self.is_list():
            return [v._to_serializable() for v in self.data]
        if self.is_tuple():
            return [v._to_serializable() for v in self.data]
        if self.is_record():
            return {k: v._to_serializable() for k, v in self.data.items()}
        return self.data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Value":
        """Create from dictionary"""
        type_name = data["type"]
        value = data["value"]
        
        type_map = {
            "NIL": ValueType.NIL,
            "BOOL": ValueType.BOOL,
            "INT": ValueType.INT,
            "FLOAT": ValueType.FLOAT,
            "STRING": ValueType.STRING,
            "ATOM": ValueType.ATOM,
            "LIST": ValueType.LIST,
            "TUPLE": ValueType.TUPLE,
            "RECORD": ValueType.RECORD,
        }
        
        vtype = type_map.get(type_name, ValueType.NIL)
        
        if vtype == ValueType.LIST:
            return cls.list_([cls.from_dict(v) for v in value])
        if vtype == ValueType.TUPLE:
            return cls.tuple_([cls.from_dict(v) for v in value])
        if vtype == ValueType.RECORD:
            return cls.record({k: cls.from_dict(v) for k, v in value.items()})
        
        return cls(vtype, value)
