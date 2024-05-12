import simpy.resources
from modules.states import HYG_STAT, change_state
from modules.tools import debug, convertTime, aufteilen, generate_random_time
from modules.wfi_manager import WFIManager
from modules.observer import Observer
from modules.cip import cip_vessel

import simpy
import numpy as np
from typing import Self

class Container:
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer) -> None:
        self.name = name
        self.env = env
        self.sT = sT
        self.state = HYG_STAT.dirty
        self.resource = simpy.Resource(env, capacity=1)
        self.wfi_manager = wfi_manager
        self.cht = convertTime((2, 0, 0))
        self.last_clean_time = 0

        observer.add_variable(f'state', self, 'state.value')

    def cycle(self):
        current_time = int(self.env.now)
        if current_time < self.sT:
            # CHT Monitoring
            if self.state in [HYG_STAT.cleaned, HYG_STAT.sanitized] and current_time - self.last_clean_time >= self.cht:
                self.state = HYG_STAT.dirty
                debug(self.env, 'Container', f'{self.name} - Reinigungssstandzeit überschritten')

    def flow_time(self, fill_rate, amount):
        amount = amount / 1000
        return int((amount / fill_rate) * convertTime((1, 0, 0)))

    def request_and_release_wfi(self, require_wfi: int, duration: int):
        while not self.wfi_manager.request_wfi(require_wfi):
            yield self.env.timeout(1)

        yield self.env.timeout(duration)
        self.wfi_manager.release_wfi(require_wfi)

    def sip(self):
        duration = generate_random_time(self.sip_durations)

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

class Vessel(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer)

        self.volume = simpy.Container(env, init=0, capacity=capacity)
        observer.add_variable(f'volume', self, 'volume.level')

    def fill(self, wfi_rate: int, fill_rate: int, amount: int):
        fill_time = int((amount / fill_rate) * convertTime((1, 0, 0)))

        while not self.wfi_manager.request_wfi(wfi_rate):
            yield self.env.timeout(1)

        for _ in range(fill_time):
            self.volume.put(amount / fill_time)
            yield self.env.timeout(1)

        self.wfi_manager.release_wfi(wfi_rate)


class LB(Vessel):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, capacity=6)

        self.wfi_rates = {
            'UV043': 18,    # 90°C für CIP über Medieneinlauf
            'UV042': 18,    # 60°C für Produkt Füllen
        }

        # TODO: Find real fill rate values
        self.fill_rates = {
            'UV043': 12,
            'UV042': 12,
            'UV373': 12,
        }

        self.cip_durations = {
            'lower': convertTime((48, 0)),
            'mean': convertTime((58, 0)),
            'upper': convertTime((118, 0)),
        }

        self.sip_durations = {
            'lower': convertTime((34, 0)),
            'mean': convertTime((50, 0)),
            'upper': convertTime((77, 0)),
        }

    def cip_beh(self):
        yield self.env.process(cip_vessel(self=self, LB=True, wfi_rates=self.wfi_rates, fill_rates=self.fill_rates, durations=self.cip_durations))

    def prod_lb(self):
        LB_amount = 2

        while not self.state == HYG_STAT.sanitized:
            yield self.env.timeout(1)

        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.production))
            debug(self.env, f'PROD', f'{self.name} - Produktion gestartet')

            yield self.env.process(self.fill(wfi_rate=self.wfi_rates['UV042'], fill_rate=self.fill_rates['UV042'], amount=LB_amount))


class AB(Vessel):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, capacity=100)

        self.wfi_rates = {
            'UV043': 30,    # 90°C für CIP über Medieneinlauf
            'UV042': 30,    # 60°C für Produkt Füllen
            'UV363': 10,    # 90°C für CIP über Transferleitung
        }

        # TODO: Find real fill rate values
        self.fill_rates = {
            'UV043': 12,
            'UV042': 12,
            'UV363': 10,
            'UV373': 12,
        }

        self.cip_durations = {
            'lower': convertTime((64, 0)),
            'mean': convertTime((73, 0)),
            'upper': convertTime((80, 0)),
        }

        self.sip_durations = {
            'lower': convertTime((53, 0)),
            'mean': convertTime((90, 0)),
            'upper': convertTime((131, 0)),
        }

    def cip_beh(self):
        yield self.env.process(cip_vessel(self=self, LB=True, wfi_rates=self.wfi_rates, fill_rates=self.fill_rates, durations=self.cip_durations))

    def prod(self, donator: Self):
        time_between_cycles = 5
        AB_predose_wfi_rate = self.wfi_rates['UV042']
        AB_predose_fill_rate = self.fill_rates['UV042']
        AB_predose_amount = 10
        LB_flush_wfi_rate = donator.wfi_rates['UV042']
        LB_flush_fill_rate = donator.fill_rates['UV042']
        LB_flush_amount = 0.5
        AB_enddose_wfi_rate = self.wfi_rates['UV042']
        AB_enddose_fill_rate = self.fill_rates['UV042']
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
                    yield self.env.process(self.transfer(donator))                                                                              # Transfer zyklus
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

class Partikel(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer)

        self.rate_wfi_uv373 = 10    # 90°C für CIP

class Sole_Transfer(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer)

        self.rate_wfi_uv373 = 10    # 90°C für CIP

class Keimfilter(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer)

        self.rate_wfi_uv373 = 10   # 90°C für CIP
        self.rate_wfi_uv374 = 2    # 20°C für filter kühlen

class VK(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer)

        self.rate_wfi_uv373 = 10    # 90°C für CIP