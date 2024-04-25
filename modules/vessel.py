import simpy.resources
from modules.states import HYG_STAT, change_state
from modules.tools import debug, convertTime
from modules.wfi_manager import WFIManager

import simpy
import numpy as np
from typing import Self

class Container:
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager) -> None:
        self.name = name
        self.env = env
        self.sT = sT
        self.track_state = np.zeros(sT)
        self.track_volume = np.zeros(sT)
        self.state = HYG_STAT.dirty
        self.resource = simpy.Resource(env, capacity=1)
        self.volume = simpy.Container(env, init=0, capacity=100)
        self.cht = convertTime((2, 0, 0))
        self.last_clean_time = 0
        self.wfi_manager = wfi_manager
        self.required_wfi = 30

    def cycle(self):
        current_time = int(self.env.now)
        if current_time < self.sT:
            # Tracking
            self.track_state[current_time] = self.state.value
            self.track_volume[current_time] = self.volume.level

            # CHT Monitoring
            if self.state in [HYG_STAT.cleaned, HYG_STAT.sanitized] and current_time - self.last_clean_time >= self.cht:
                self.state = HYG_STAT.dirty
                debug(self.env, 'VesselCycle', f'{self.name} - Reinigungssstandzeit überschritten')

    def cip(self):
        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.cleaning))
            debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

            while not self.wfi_manager.request_wfi(self.required_wfi):
                yield self.env.timeout(1)

            time = convertTime((35, 0))
            wfi_time = time / 3
            dry_time = time - wfi_time

            yield self.env.timeout(wfi_time)
            self.wfi_manager.release_wfi(self.required_wfi)

            yield self.env.timeout(dry_time)

            debug(self.env, f'CIP', f'{self.name} - Reinigung beendet')
            yield self.env.process(change_state(self, HYG_STAT.cleaned))
            self.last_clean_time = int(self.env.now)

    def sip(self):
        while not self.state == HYG_STAT.cleaned:
            yield self.env.timeout(1)

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.sanitizing))
            debug(self.env, f'SIP', f'{self.name} - Sanitisierung gestartet')

            yield self.env.timeout(convertTime((30, 0)))

            debug(self.env, f'SIP', f'{self.name} - Sanitisierung beendet')
            yield self.env.process(change_state(self, HYG_STAT.sanitized))
            self.last_clean_time = int(self.env.now)

    def prod_lb(self):
        while not self.state == HYG_STAT.sanitized:
            yield self.env.timeout(1)

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.production))
            debug(self.env, f'PROD', f'{self.name} - Produktion gestartet')

            yield self.env.process(self.fill(wfi_rate=10, fill_rate=12, amount=2))
            debug(self.env, f'PROD', f'{self.name} - Produktion beendet')

    def prod(self, donator: Self):
        while not self.state == HYG_STAT.sanitized or not donator.state == HYG_STAT.production:
            yield self.env.timeout(1)

        with donator.resource.request() as don_req:
            yield don_req

            with self.resource.request() as own_req:
                yield own_req

                target_volume = 30

                yield self.env.process(change_state(self, HYG_STAT.production))
                debug(self.env, f'PROD', f'{donator.name} - {self.name} - Produktion gestartet')

                yield self.env.process(self.fill(wfi_rate=19, fill_rate=12, amount=10))             # Abfüllbehälter vordosieren
                yield self.env.process(self.transfer(donator))                                      # Sole Transfer
                yield self.env.timeout(convertTime((1, 0)))

                for _ in range(3):
                    yield self.env.process(donator.fill(wfi_rate=10, fill_rate=12, amount=0.5))     # Spülzyklus 
                    yield self.env.process(donator.transfer(donator))                               # Transfer zyklus
                    yield self.env.timeout(convertTime((1, 0)))

                yield self.env.process(change_state(donator, HYG_STAT.dirty))

                rest_volume = target_volume - self.volume.level
                yield self.env.process(self.fill(wfi_rate=10, fill_rate=12, amount=rest_volume))     # Abfüllbehälter enddosieren

    def transfer(self, donator: Self):
        transfer_volume = donator.volume.level
        transfer_rate = 10
        transfer_time = int((transfer_volume / transfer_rate) * convertTime((1, 0, 0)))

        for _ in range(transfer_time):
            step_volume = transfer_volume / transfer_time
            yield donator.volume.get(step_volume)
            yield self.volume.put(step_volume)
            yield self.env.timeout(1)

    def fill(self, wfi_rate: int, fill_rate: int, amount: int):
        fill_time = int((amount / fill_rate) * convertTime((1, 0, 0)))

        while not self.wfi_manager.request_wfi(wfi_rate):
            yield self.env.timeout(1)

        for _ in range(fill_time):
            self.volume.put(amount / fill_time)
            yield self.env.timeout(1)

        self.wfi_manager.release_wfi(wfi_rate)