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
        if amount <= self.available_capacity:
            self.available_capacity -= amount
            self.reserved_capacity += amount
            return True
        else:
            return False
        
    def release_wfi(self, amount):
        self.available_capacity += amount
        self.reserved_capacity -= amount

    def monitor_wfi(self):
        while True:
            # Überwache und verwalte die WFI-Resource
            yield self.env.timeout(1) # Überprüfe jede sekunde
            if self.available_capacity < self.total_capacity:
                for container in self.container_queue:
                    if self.request_wfi(container.required_wfi):
                        container.process = self.env.process(container.clean())
                        self.container_queue.remove(container)
                        break

