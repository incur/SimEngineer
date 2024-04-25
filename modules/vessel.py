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

    def cip(self, duration: int):
        required_wfi = 30
        # TODO: Die Spülzeit ist nicht genau ein drittel. Mehr Prozessdaten sammeln
        time = duration
        wfi_time = time / 3
        dry_time = time - wfi_time

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.cleaning))
            debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

            while not self.wfi_manager.request_wfi(required_wfi):
                yield self.env.timeout(1)


            yield self.env.timeout(wfi_time)
            self.wfi_manager.release_wfi(required_wfi)

            yield self.env.timeout(dry_time)

            debug(self.env, f'CIP', f'{self.name} - Reinigung beendet')
            yield self.env.process(change_state(self, HYG_STAT.cleaned))
            self.last_clean_time = int(self.env.now)

    def sip(self, duration: int):
        while not self.state == HYG_STAT.cleaned:
            yield self.env.timeout(1)

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.sanitizing))
            debug(self.env, f'SIP', f'{self.name} - Sanitisierung gestartet')

            yield self.env.timeout(duration)

            debug(self.env, f'SIP', f'{self.name} - Sanitisierung beendet')
            yield self.env.process(change_state(self, HYG_STAT.sanitized))
            self.last_clean_time = int(self.env.now)

    def prod_lb(self):
        LB_wfi_rate = 10
        LB_fill_rate = 12
        LB_amount = 2

        while not self.state == HYG_STAT.sanitized:
            yield self.env.timeout(1)

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.production))
            debug(self.env, f'PROD', f'{self.name} - Produktion gestartet')

            yield self.env.process(self.fill(wfi_rate=LB_wfi_rate, fill_rate=LB_fill_rate, amount=LB_amount))

    def prod(self, donator: Self):
        time_between_cycles = convertTime((1, 0))
        AB_predose_wfi_rate = 19
        AB_predose_fill_rate = 12
        AB_predose_amount = 10
        LB_flush_wfi_rate = 10
        LB_flush_fill_rate = 12
        LB_flush_amount = 0.5
        AB_enddose_wfi_rate = 10
        AB_enddose_fill_rate = 12
        AB_enddose_target = 30

        while not self.state == HYG_STAT.sanitized or not donator.state == HYG_STAT.production:
            yield self.env.timeout(1)

        with donator.resource.request() as don_req:
            yield don_req

            with self.resource.request() as own_req:
                yield own_req

                yield self.env.process(change_state(self, HYG_STAT.production))
                debug(self.env, f'PROD', f'{donator.name} -> {self.name} - Produktion gestartet')

                yield self.env.process(self.fill(wfi_rate=AB_predose_wfi_rate, fill_rate=AB_predose_fill_rate, amount=AB_predose_amount))       # Abfüllbehälter vordosieren
                yield self.env.process(self.transfer(donator))                                                                                  # Sole Transfer
                yield self.env.timeout(time_between_cycles)

                for _ in range(3):
                    yield self.env.process(donator.fill(wfi_rate=LB_flush_wfi_rate, fill_rate=LB_flush_fill_rate, amount=LB_flush_amount))      # Spülzyklus 
                    yield self.env.process(self.transfer(donator))                                                                           # Transfer zyklus
                    yield self.env.timeout(time_between_cycles)

                debug(self.env, f'PROD', f'{donator.name} - Produktion beendet')
                yield self.env.process(change_state(donator, HYG_STAT.dirty))

                rest_volume = AB_enddose_target - self.volume.level
                yield self.env.process(self.fill(wfi_rate=AB_enddose_wfi_rate, fill_rate=AB_enddose_fill_rate, amount=rest_volume))             # Abfüllbehälter enddosieren
                debug(self.env, f'PROD', f'{self.name} - Produkt steht bereit')

    def transfer(self, donator: Self):
        transfer_rate = 10

        transfer_volume = donator.volume.level
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