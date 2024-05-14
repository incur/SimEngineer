import simpy.resources
from modules.states import HYG_STAT, change_state
from modules.tools import debug, convertTime, aufteilen, generate_random_time
from modules.wfi_manager import WFIManager
from modules.observer import Observer
from modules.routes import Routes
from modules.cip import cip_vessel, cip_transf, cip_filter, cip_knoten, sip_default

import simpy
import numpy as np
from typing import Self

class Container:
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        self.name = name
        self.env = env
        self.sT = sT
        self.state = HYG_STAT.dirty
        self.sip_state = HYG_STAT.dirty
        self.resource = simpy.Resource(env, capacity=1)
        self.observer = observer
        self.routes = routes
        self.wfi_manager = wfi_manager
        self.cht = convertTime((72, 0, 0))
        self.last_clean_time = 0
        self.last_sip_time = 0

        observer.add_variable(f'cip state', self, 'state.value')
        observer.add_variable(f'sip state', self, 'sip_state.value')

    def cycle(self):
        current_time = int(self.env.now)
        if current_time < self.sT:
            # CHT Monitoring
            if self.state in [HYG_STAT.cleaned] and current_time - self.last_clean_time >= self.cht:
                self.state = HYG_STAT.dirty
                debug(self.env, 'Container', f'{self.name} - Reinigungssstandzeit überschritten')

            if self.sip_state in [HYG_STAT.sanitized] and current_time - self.last_sip_time >= self.cht:
                self.sip_state = HYG_STAT.dirty
                debug(self.env, 'Container', f'{self.name} - Sterilstandzeit überschritten')

    def flow_time(self, fill_rate, amount):
        amount = amount / 1000
        return int((amount / fill_rate) * convertTime((1, 0, 0)))

    def request_and_release_wfi(self, require_wfi: int, duration: int):
        while not self.wfi_manager.request_wfi(require_wfi):
            yield self.env.timeout(convertTime((0, 1)))

        yield self.env.timeout(duration)
        self.wfi_manager.release_wfi(require_wfi)

class Vessel(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes, capacity: int) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes)

        self.volume = simpy.Container(env, init=0, capacity=capacity)
        observer.add_variable(f'volume', self, 'volume.level')

    def fill(self, wfi_rate: int, fill_rate: int, amount: int):
        fill_time = int((amount / fill_rate) * convertTime((1, 0, 0)))

        while not self.wfi_manager.request_wfi(wfi_rate):
            yield self.env.timeout(convertTime((0, 1)))

        for _ in range(fill_time):
            self.volume.put(amount / fill_time)
            yield self.env.timeout(convertTime((0, 1)))

        self.wfi_manager.release_wfi(wfi_rate)


class LB(Vessel):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes, capacity=6)

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

    def cip(self):
        r1 = self.routes.rLB_P

        with r1.request() as req:
            yield req

            with self.resource.request() as req1:
                yield req1

                start = self.env.now
                yield self.env.process(cip_vessel(self=self, LB=True, wfi_rates=self.wfi_rates, fill_rates=self.fill_rates, durations=self.cip_durations))
                self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        r1 = self.routes.rLB_P

        with r1.request() as req:
            yield req

            with self.resource.request() as req1:
                yield req1

                start = self.env.now
                yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def prod_lb(self):
        LB_amount = 2

        while not self.state == HYG_STAT.cleaned:
            yield self.env.timeout(convertTime((0, 1)))

        while not self.sip_state == HYG_STAT.sanitized:
            yield self.env.timeout(convertTime((0, 1)))

        with self.resource.request() as req:
            yield req

            start = self.env.now
            yield self.env.process(change_state(self, HYG_STAT.production, 'cip'))
            yield self.env.process(change_state(self, HYG_STAT.production, 'sip'))
            debug(self.env, f'PROD', f'{self.name} - Produktion gestartet')

            yield self.env.process(self.fill(wfi_rate=self.wfi_rates['UV042'], fill_rate=self.fill_rates['UV042'], amount=LB_amount))
            self.observer.add_task(task="Produktion", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))


class AB(Vessel):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes, capacity=100)

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

    def cip(self):
        if self.name == '2020_A':
            r1 = self.routes.rT_AB1
            r2 = self.routes.rAB1_K1
        else:
            r1 = self.routes.rT_AB2
            r2 = self.routes.rAB2_K2

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(cip_vessel(self=self, LB=True, wfi_rates=self.wfi_rates, fill_rates=self.fill_rates, durations=self.cip_durations))
                    self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        if self.name == '2020_A':
            r1 = self.routes.rT_AB1
            r2 = self.routes.rAB1_K1
        else:
            r1 = self.routes.rT_AB2
            r2 = self.routes.rAB2_K2

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                    self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

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

        r1 = self.routes.rLB_P
        r2 = self.routes.rP_T
        if self.name == '2020_A':
            r3 = self.routes.rT_AB1
        else:
            r3 = self.routes.rT_AB2

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with r3.request() as req2:
                    yield req2

                    with donator.resource.request() as don_req:
                        yield don_req

                        with self.resource.request() as own_req:
                            yield own_req

                            start = self.env.now

                            while not self.state == HYG_STAT.cleaned or not donator.state == HYG_STAT.production:
                                yield self.env.timeout(convertTime((0, 1)))

                            while not self.sip_state == HYG_STAT.sanitized or not donator.sip_state == HYG_STAT.production:
                                yield self.env.timeout(convertTime((0, 1)))

                            yield self.env.process(change_state(self, HYG_STAT.production, 'cip'))
                            yield self.env.process(change_state(self, HYG_STAT.production, 'sip'))
                            debug(self.env, f'PROD', f'{donator.name} -> {self.name} - Produktion gestartet')

                            yield self.env.process(self.fill(wfi_rate=AB_predose_wfi_rate, fill_rate=AB_predose_fill_rate, amount=AB_predose_amount))       # Abfüllbehälter vordosieren
                            yield self.env.process(self.transfer(donator))                                                                                  # Sole Transfer
                            yield self.env.timeout(time_between_cycles)

                            for _ in range(3):
                                yield self.env.process(donator.fill(wfi_rate=LB_flush_wfi_rate, fill_rate=LB_flush_fill_rate, amount=LB_flush_amount))      # Spülzyklus 
                                yield self.env.process(self.transfer(donator))                                                                              # Transfer zyklus
                                yield self.env.timeout(time_between_cycles)

                            debug(self.env, f'PROD', f'{donator.name} - Produktion beendet')
                            yield self.env.process(change_state(donator, HYG_STAT.dirty, 'cip'))

                            rest_volume = AB_enddose_target - self.volume.level
                            yield self.env.process(self.fill(wfi_rate=AB_enddose_wfi_rate, fill_rate=AB_enddose_fill_rate, amount=rest_volume))             # Abfüllbehälter enddosieren
                            debug(self.env, f'PROD', f'{self.name} - Produkt steht bereit')
                            self.observer.add_task(task="Produktion", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def transfer(self, donator: Self):
        transfer_rate = 10

        transfer_volume = donator.volume.level
        transfer_time = int((transfer_volume / transfer_rate) * convertTime((1, 0, 0)))

        for _ in range(transfer_time):
            step_volume = transfer_volume / transfer_time
            yield donator.volume.get(step_volume)
            yield self.volume.put(step_volume)
            yield self.env.timeout(convertTime((0, 1)))

class Sole_Transfer(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes)

        self.wfi_rates = {
            'UV373': 10,    # 90°C für CIP
        }

        self.cip_durations = {
            'lower': convertTime((15, 34)),
            'mean': convertTime((15, 47)),
            'upper': convertTime((16, 0)),
        }

        self.sip_durations = {
            'lower': convertTime((25, 1)),
            'mean': convertTime((25, 38)),
            'upper': convertTime((39, 29)),
        }

    def cip(self):
        r1 = self.routes.rP_T
        r2 = self.routes.rT_AB1
        r3 = self.routes.rT_AB2

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with r3.request() as req2:
                    yield req2

                    with self.resource.request() as req3:
                        yield req3

                        start = self.env.now
                        yield self.env.process(cip_transf(self=self, wfi_rates=self.wfi_rates, durations=self.cip_durations))
                        self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        r1 = self.routes.rP_T
        r2 = self.routes.rT_AB1
        r3 = self.routes.rT_AB2

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with r3.request() as req2:
                    yield req2

                    with self.resource.request() as req3:
                        yield req3

                        start = self.env.now
                        yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                        self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

class Partikel(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes)

        self.wfi_rates = {
            'UV373': 10,    # 90°C für CIP
        }

        self.cip_durations = {
            'lower': convertTime((23, 13)),
            'mean': convertTime((23, 36)),
            'upper': convertTime((25, 30)),
        }

        self.sip_durations = {
            'lower': convertTime((22, 53)),
            'mean': convertTime((23, 49)),
            'upper': convertTime((25, 39)),
        }

    def cip(self):
        r1 = self.routes.rLB_P
        r2 = self.routes.rP_T

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(cip_filter(self=self, wfi_rates=self.wfi_rates, durations=self.cip_durations))
                    self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        r1 = self.routes.rLB_P
        r2 = self.routes.rP_T

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                    self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))


class Keimfilter(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes)

        self.wfi_rates = {
            'UV373': 10,    # 90°C für CIP
            'UV374': 2,     # 20°C für filter kühlen
        }

        self.cip_durations = {
            'lower': convertTime((58, 49)),
            'mean': convertTime((74, 7)),
            'upper': convertTime((122, 29)),
        }

        self.sip_durations = {
            'lower': convertTime((25, 52)),
            'mean': convertTime((26, 52)),
            'upper': convertTime((41, 7)),
        }

    def cip(self):
        if self.name == '2021_A':
            r1 = self.routes.rAB1_K1
            r2 = self.routes.rK1_VK
        else:
            r1 = self.routes.rAB2_K2
            r2 = self.routes.rK2_VK

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(cip_filter(self=self, wfi_rates=self.wfi_rates, durations=self.cip_durations))
                    self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        if self.name == '2021_A':
            r1 = self.routes.rAB1_K1
            r2 = self.routes.rK1_VK
        else:
            r1 = self.routes.rAB2_K2
            r2 = self.routes.rK2_VK

        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                    self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))


class VK(Container):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer, routes: Routes) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, routes)

        self.wfi_rates = {
            'UV373': 10,    # 90°C für CIP
        }

        self.cip_durations = {
            'lower': convertTime((17, 21)),
            'mean': convertTime((17, 32)),
            'upper': convertTime((17, 50)),
        }

        self.sip_durations = {
            'lower': convertTime((25, 25)),
            'mean': convertTime((25, 43)),
            'upper': convertTime((26, 14)),
        }

    def cip(self):
        r1 = self.routes.rK1_VK
        r2 = self.routes.rK2_VK
        
        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(cip_knoten(self=self, wfi_rates=self.wfi_rates, durations=self.cip_durations))
                    self.observer.add_task(task="CIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))

    def sip(self):
        r1 = self.routes.rK1_VK
        r2 = self.routes.rK2_VK
        
        with r1.request() as req:
            yield req

            with r2.request() as req1:
                yield req1

                with self.resource.request() as req2:
                    yield req2

                    start = self.env.now
                    yield self.env.process(sip_default(self=self, durations=self.sip_durations))
                    self.observer.add_task(task="SIP", resource=self.name, start=convertTime(start), end=convertTime(self.env.now))
