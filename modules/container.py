import simpy.resources
from modules.states import HYG_STAT, change_state
from modules.tools import debug, convertTime, aufteilen
from modules.wfi_manager import WFIManager
from modules.observer import Observer

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

        self.rate_wfi_uv043 = 18    # 90°C für CIP über Medieneinlauf
        self.rate_wfi_uv042 = 18    # 60°C für Produkt Füllen

        # TODO: Find real fill rate values
        self.rate_fill_uv043 = 12
        self.rate_fill_uv042 = 12
        self.rate_fill_uv373 = 12

        self.time_cip_lower = convertTime((48, 0))
        self.time_cip_mean = convertTime((58, 0))
        self.time_cip_upper = convertTime((118, 0))

        self.time_sip_lower = convertTime((34, 0))
        self.time_sip_mean = convertTime((50, 0))
        self.time_sip_upper = convertTime((77, 0))

    def cip_beh(self):
        zeiten = {
            "time_init_entleeren":              30,
            "time_init_nachlauf":               190,
            "time_cip_container_zugabe":        self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_container_zugabe":      33,
            "time_cip_handzugabe":              self.flow_time(self.rate_fill_uv043, 40),
            "time_reset_handzugabe":            33,
            "time_cip_rohstoffzugabe":          self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_rohstoffzugabe":        33,
            "time_cip_einlauf":                 self.flow_time(self.rate_fill_uv043, 80),
            "time_reset_einlauf":               33,
            "time_cip_sprühkugeln":             self.flow_time(self.rate_fill_uv043, 300),
            "time_reset_sprühkugeln":           33,
            "time_entleeren_delay":             60,
            "time_entleeren_nachlauf":          180,
            "time_cip_container_zugabe_2":      self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_container_zugabe_2":    33,
            "time_cip_handzugabe_2":            self.flow_time(self.rate_fill_uv043, 40),
            "time_reset_handzugabe_2":          33,
            "time_cip_rohstoffzugabe_2":        self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_rohstoffzugabe_2":      33,
            "time_cip_einlauf_2":               self.flow_time(self.rate_fill_uv043, 80),
            "time_reset_einlauf_2":             33,
            "time_cip_sprühkugeln_2":           self.flow_time(self.rate_fill_uv043, 300),
            "time_reset_sprühkugeln_2":         33,
            "time_fill":                        convertTime((5, 0)),
            "time_reset_fill":                  35,
            "time_cip_rührer":                  300,
            "time_entleeren_2":                 180,
            "time_entleeren_delay_2":           60,
            "time_entleeren_nachlauf_2":        180,
            "time_abschluss_druck":             self.flow_time(self.rate_fill_uv043, 20),
            "time_abschluss_push":              self.flow_time(self.rate_fill_uv043, 10),
        }

        total_duration = self.time_cip_mean
        summe = sum(zeiten.values())
        remaining_duration = total_duration - summe
        gewichtung = [1, 10, 3, 20, 15, 10]
        aufteilung = aufteilen(remaining_duration, gewichtung)

        zeiten['time_druck_1'] = aufteilung[0]
        zeiten['time_entleeren'] = aufteilung[1]
        zeiten['time_druck_2'] = aufteilung[2]
        zeiten['time_entleeren_2'] = aufteilung[3]
        zeiten['time_abschluss_druck'] = aufteilung[4]
        zeiten['time_abschluss_push'] = aufteilung[5]


        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.cleaning))
            debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

            # Init
            yield self.env.timeout(zeiten['time_init_entleeren'])       # Entleeren
            yield self.env.timeout(zeiten['time_init_nachlauf'])        
            # Nachlauf

            # Zyklus 1

            # Druckprüfung
            yield self.env.timeout(zeiten['time_druck_1'])

            # Container Zugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_container_zugabe']))
            yield self.env.timeout(zeiten['time_reset_container_zugabe'])

            # Handzugabe
            # time = self.flow_time(self.rate_fill_uv043, 40)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_handzugabe']))
            yield self.env.timeout(zeiten['time_reset_handzugabe'])

            # Rohstoffzugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_rohstoffzugabe']))
            yield self.env.timeout(zeiten['time_reset_rohstoffzugabe'])

            # Einlauf
            # time = self.flow_time(self.rate_fill_uv043, 80)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_einlauf']))
            yield self.env.timeout(zeiten['time_reset_einlauf'])

            # Sprühkugeln
            # time = self.flow_time(self.rate_fill_uv043, 300)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_sprühkugeln']))
            yield self.env.timeout(zeiten['time_reset_sprühkugeln'])

            # Entleeren
            yield self.env.timeout(zeiten['time_entleeren'])                # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_delay'])          # Delay
            yield self.env.timeout(zeiten['time_entleeren_nachlauf'])       # Nachlauf

            # Zyklus 2

            # Druckprüfung
            yield self.env.timeout(zeiten['time_druck_2'])

            # Container Zugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_container_zugabe_2']))
            yield self.env.timeout(zeiten['time_reset_container_zugabe_2'])

            # Handzugabe
            # time = self.flow_time(self.rate_fill_uv043, 40)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_handzugabe_2']))
            yield self.env.timeout(zeiten['time_reset_handzugabe_2'])

            # Rohstoffzugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_rohstoffzugabe_2']))
            yield self.env.timeout(zeiten['time_reset_rohstoffzugabe_2'])

            # Einlauf
            # time = self.flow_time(self.rate_fill_uv043, 80)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_einlauf_2']))
            yield self.env.timeout(zeiten['time_reset_einlauf_2'])

            # Sprühkugeln
            # time = self.flow_time(self.rate_fill_uv043, 300)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_sprühkugeln_2']))
            yield self.env.timeout(zeiten['time_reset_sprühkugeln_2'])

            # Füllen
            yield self.env.timeout(zeiten['time_fill'])
            yield self.env.timeout(zeiten['time_reset_fill'])

            # CIP Rührer
            yield self.env.timeout(zeiten['time_cip_rührer'])

            # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_2'])              # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_delay_2'])        # Delay
            yield self.env.timeout(zeiten['time_entleeren_nachlauf_2'])     # Nachlauf

            # Abschluss
            yield self.env.timeout(zeiten['time_abschluss_druck'])          # Druckaufbau
            yield self.env.timeout(zeiten['time_abschluss_push'])           # Leer Drücken

            debug(self.env, f'CIP', f'{self.name} - Reinigung beendet')
            yield self.env.process(change_state(self, HYG_STAT.cleaned))
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


class AB(Vessel):
    def __init__(self, env: simpy.Environment, sT: int, name: str, wfi_manager: WFIManager, observer: Observer) -> None:
        super().__init__(env, sT, name, wfi_manager, observer, capacity=100)

        self.rate_wfi_uv043 = 30    # 90°C für CIP über Medieneinlauf
        self.rate_wfi_uv042 = 30    # 60°C für Produkt Füllen
        self.rate_wfi_uv363 = 10    # 90°C für CIP über Transferleitung

        # TODO: Find real fill rate values
        self.rate_fill_uv043 = 12
        self.rate_fill_uv042 = 12
        self.rate_fill_uv363 = 10 
        self.rate_fill_uv373 = 12

        self.time_cip_lower = convertTime((64, 0))
        self.time_cip_mean = convertTime((73, 0))
        self.time_cip_upper = convertTime((80, 0))

        self.time_sip_lower = convertTime((53, 0))
        self.time_sip_mean = convertTime((90, 0))
        self.time_sip_upper = convertTime((131, 0))

    def cip_beh(self):
        zeiten = {
            "time_init_entleeren":              30,
            "time_init_nachlauf":               190,
            "time_cip_container_zugabe":        self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_container_zugabe":      33,
            "time_cip_handzugabe":              self.flow_time(self.rate_fill_uv043, 40),
            "time_reset_handzugabe":            33,
            "time_cip_rohstoffzugabe":          self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_rohstoffzugabe":        33,
            "time_cip_einlauf":                 self.flow_time(self.rate_fill_uv043, 80),
            "time_reset_einlauf":               33,
            "time_cip_sprühkugeln":             self.flow_time(self.rate_fill_uv043, 300),
            "time_reset_sprühkugeln":           33,
            "time_entleeren_delay":             60,
            "time_entleeren_nachlauf":          180,
            "time_cip_container_zugabe_2":      self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_container_zugabe_2":    33,
            "time_cip_handzugabe_2":            self.flow_time(self.rate_fill_uv043, 40),
            "time_reset_handzugabe_2":          33,
            "time_cip_rohstoffzugabe_2":        self.flow_time(self.rate_fill_uv043, 60),
            "time_reset_rohstoffzugabe_2":      33,
            "time_cip_einlauf_2":               self.flow_time(self.rate_fill_uv043, 80),
            "time_reset_einlauf_2":             33,
            "time_cip_sprühkugeln_2":           self.flow_time(self.rate_fill_uv043, 300),
            "time_reset_sprühkugeln_2":         33,
            "time_fill":                        convertTime((5, 0)),
            "time_reset_fill":                  35,
            "time_cip_rührer":                  300,
            "time_entleeren_2":                 180,
            "time_entleeren_delay_2":           60,
            "time_entleeren_nachlauf_2":        180,
            "time_abschluss_druck":             self.flow_time(self.rate_fill_uv043, 20),
            "time_abschluss_push":              self.flow_time(self.rate_fill_uv043, 10),
        }

        total_duration = self.time_cip_mean
        summe = sum(zeiten.values())
        remaining_duration = total_duration - summe
        gewichtung = [1, 10, 3, 20, 15, 10]
        aufteilung = aufteilen(remaining_duration, gewichtung)

        zeiten['time_druck_1'] = aufteilung[0]
        zeiten['time_entleeren'] = aufteilung[1]
        zeiten['time_druck_2'] = aufteilung[2]
        zeiten['time_entleeren_2'] = aufteilung[3]
        zeiten['time_abschluss_druck'] = aufteilung[4]
        zeiten['time_abschluss_push'] = aufteilung[5]


        with self.resource.request() as req:
            yield req

            yield self.env.process(change_state(self, HYG_STAT.cleaning))
            debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

            # Init
            yield self.env.timeout(zeiten['time_init_entleeren'])       # Entleeren
            yield self.env.timeout(zeiten['time_init_nachlauf'])        
            # Nachlauf

            # Zyklus 1

            # Druckprüfung
            yield self.env.timeout(zeiten['time_druck_1'])

            # Container Zugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_container_zugabe']))
            yield self.env.timeout(zeiten['time_reset_container_zugabe'])

            # Handzugabe
            # time = self.flow_time(self.rate_fill_uv043, 40)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_handzugabe']))
            yield self.env.timeout(zeiten['time_reset_handzugabe'])

            # Rohstoffzugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_rohstoffzugabe']))
            yield self.env.timeout(zeiten['time_reset_rohstoffzugabe'])

            # Einlauf
            # time = self.flow_time(self.rate_fill_uv043, 80)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_einlauf']))
            yield self.env.timeout(zeiten['time_reset_einlauf'])

            # Sprühkugeln
            # time = self.flow_time(self.rate_fill_uv043, 300)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_sprühkugeln']))
            yield self.env.timeout(zeiten['time_reset_sprühkugeln'])

            # Entleeren
            yield self.env.timeout(zeiten['time_entleeren'])                # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_delay'])          # Delay
            yield self.env.timeout(zeiten['time_entleeren_nachlauf'])       # Nachlauf

            # Zyklus 2

            # Druckprüfung
            yield self.env.timeout(zeiten['time_druck_2'])

            # Container Zugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_container_zugabe_2']))
            yield self.env.timeout(zeiten['time_reset_container_zugabe_2'])

            # Handzugabe
            # time = self.flow_time(self.rate_fill_uv043, 40)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_handzugabe_2']))
            yield self.env.timeout(zeiten['time_reset_handzugabe_2'])

            # Rohstoffzugabe
            # time = self.flow_time(self.rate_fill_uv043, 60)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_rohstoffzugabe_2']))
            yield self.env.timeout(zeiten['time_reset_rohstoffzugabe_2'])

            # Einlauf
            # time = self.flow_time(self.rate_fill_uv043, 80)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_einlauf_2']))
            yield self.env.timeout(zeiten['time_reset_einlauf_2'])

            # Sprühkugeln
            # time = self.flow_time(self.rate_fill_uv043, 300)
            yield self.env.process(self.request_and_release_wfi(30, zeiten['time_cip_sprühkugeln_2']))
            yield self.env.timeout(zeiten['time_reset_sprühkugeln_2'])

            # Füllen
            yield self.env.timeout(zeiten['time_fill'])
            yield self.env.timeout(zeiten['time_reset_fill'])

            # CIP Rührer
            yield self.env.timeout(zeiten['time_cip_rührer'])

            # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_2'])              # Entleeren
            yield self.env.timeout(zeiten['time_entleeren_delay_2'])        # Delay
            yield self.env.timeout(zeiten['time_entleeren_nachlauf_2'])     # Nachlauf

            # Abschluss
            yield self.env.timeout(zeiten['time_abschluss_druck'])          # Druckaufbau
            yield self.env.timeout(zeiten['time_abschluss_push'])           # Leer Drücken

            debug(self.env, f'CIP', f'{self.name} - Reinigung beendet')
            yield self.env.process(change_state(self, HYG_STAT.cleaned))
            self.last_clean_time = int(self.env.now)

    def prod(self, donator: Self):
        time_between_cycles = 5
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