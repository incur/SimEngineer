import simpy
import numpy as np
from modules.observer import Observer

class WFIManager:
    def __init__(self, env: simpy.Environment, sT: int, total_capacity: int, observer: Observer) -> None:
        self.env = env
        self.sT = sT
        self.name = 'WFI-Manager'
        self.total_capacity = total_capacity
        self.available_capacity = total_capacity
        self.reserved_capacity = 0
        self.container_queue = []
        observer.add_variable(f'capacity', self, 'available_capacity')
        observer.add_variable(f'reserved', self, 'reserved_capacity')

    def cycle(self):
        current_time = int(self.env.now)
        if current_time < self.sT:
            pass

    def request_wfi(self, amount):
        # TODO: Implementiere ein priority Flag der WFI reserviert obwohl nicht genügend 
        # verfügbar ist. available = max(0, available - amount)
        # Wichtig für das CEW verhalten.
        if amount <= self.available_capacity:
            self.available_capacity -= amount
            self.reserved_capacity += amount
            return True
        else:
            return False
        
    def release_wfi(self, amount):
        self.available_capacity += amount
        self.reserved_capacity -= amount
