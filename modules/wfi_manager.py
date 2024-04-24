import simpy
import numpy as np

class WFIManager:
    def __init__(self, env: simpy.Environment, sT: int, total_capacity: int) -> None:
        self.env = env
        self.sT = sT
        self.total_capacity = total_capacity
        self.available_capacity = total_capacity
        self.reserved_capacity = 0
        self.container_queue = []
        self.track_capacity = np.zeros(sT)
        self.track_reserved = np.zeros(sT)

    def cycle(self):
        current_time = int(self.env.now)
        if current_time < self.sT:
            self.track_capacity[current_time] = self.available_capacity
            self.track_reserved[current_time] = self.reserved_capacity

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

