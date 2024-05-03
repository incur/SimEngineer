import numpy as np
from typing import Dict, Any
from collections import namedtuple

def get_nested_attribute(obj, attr_string):
    attrs = attr_string.split('.')
    for attr in attrs:
        try:
            obj = getattr(obj, attr)
        except AttributeError:
            return None
    return obj

SubjectData = namedtuple('SubjectData', ['Obj', 'name', 'variables'])

class Observer:
    def __init__(self, sT: int) -> None:
        self.sT: int = sT
        self.subjects: Dict[str, SubjectData] = {}

    def add_variable(self, name: str, subject: Any, variable_name: str):
        values = np.zeros(self.sT)
        if subject.name not in self.subjects:
            self.subjects[subject.name] = SubjectData(subject, name, {})

        self.subjects[subject.name].variables[variable_name] = values

    def cycle(self, current_time: int):
        for sub, data in self.subjects.items():
            obj = data.Obj

            for variable_name, values in data.variables.items():
                if '.' in variable_name:
                    value = get_nested_attribute(obj, variable_name)
                else:
                    value = getattr(obj, variable_name)
                values[current_time] = value
