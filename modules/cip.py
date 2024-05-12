from modules.tools import debug, convertTime, aufteilen
from modules.states import HYG_STAT, change_state

class CIPVesselError(Exception):
    pass


class MissingKeyError(CIPVesselError):
    def __init__(self, key, dictionary):
        super().__init__(f"Schlüssel '{key}' nicht in '{dictionary}' gefunden")


def cip_vessel(self, LB: bool, wfi_rates, fill_rates, durations):
    start_time = self.env.now
    total_duration = durations['mean']

    required_keys = {
        True: ['UV043'],
        False: ['UV043', 'UV363']
    }

    for key in required_keys[LB]:
        if key not in wfi_rates:
            raise MissingKeyError(key, dictionary='wfi_rates')
        if key not in fill_rates:
            raise MissingKeyError(key, dictionary='fill_rates')
        
    zeiten = {
        "time_init_entleeren":              30,
        "time_init_nachlauf":               190,
        'time_druckprüfung_kurz':           convertTime((5, 0)),

        "time_cip_container_zugabe":        self.flow_time(self.fill_rates['UV043'], 60),
        "time_reset_container_zugabe":      33,
        "time_cip_handzugabe":              self.flow_time(self.fill_rates['UV043'], 40),
        "time_reset_handzugabe":            33,
        "time_cip_rohstoffzugabe":          self.flow_time(self.fill_rates['UV043'], 60),
        "time_reset_rohstoffzugabe":        33,
        "time_cip_trans_in":                300,
        "time_reset_trans_in":              33,
        "time_cip_fallrohr":                self.flow_time(self.fill_rates['UV043'], 300),
        "time_reset_fallrohr":              33,
        "time_cip_einlauf":                 self.flow_time(self.fill_rates['UV043'], 80),
        "time_reset_einlauf":               33,
        "time_cip_sprühkugeln":             self.flow_time(self.fill_rates['UV043'], 300),
        "time_reset_sprühkugeln":           33,

        'time_entleeren':                   convertTime((10, 0)),
        "time_entleeren_delay":             60,
        "time_entleeren_nachlauf":          180,
        'time_druckprüfung_lang':           convertTime((5, 0)),

        "time_fill":                        convertTime((5, 0)),
        "time_reset_fill":                  35,
        "time_cip_rührer":                  300,
    }

    with self.resource.request() as req:
        yield req

        yield self.env.process(change_state(self, HYG_STAT.cleaning))
        debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

        cycle = 0
        run = True
        while run:
            if cycle == 0:
                # Init
                yield self.env.timeout(zeiten['time_init_entleeren'])
                yield self.env.timeout(zeiten['time_init_nachlauf'])

                # Druckprüfung kurz
                yield self.env.timeout(zeiten['time_druckprüfung_kurz'])

            if LB and cycle in (1, 3):
                # Container Zugabe
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_container_zugabe']))
                yield self.env.timeout(zeiten['time_reset_container_zugabe'])

                # Handzugabe
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_handzugabe']))
                yield self.env.timeout(zeiten['time_reset_handzugabe'])

                # Rohstoffzugabe
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_rohstoffzugabe']))
                yield self.env.timeout(zeiten['time_reset_rohstoffzugabe'])

                # Einlauf
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_einlauf']))
                yield self.env.timeout(zeiten['time_reset_einlauf'])

                # Sprühkugeln
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_sprühkugeln']))
                yield self.env.timeout(zeiten['time_reset_sprühkugeln'])

            if not LB and cycle in (1, 3):
                # Trans In
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV363'], zeiten['time_cip_trans_in']))
                yield self.env.timeout(zeiten['time_reset_trans_in'])

                # Einlauf
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_einlauf']))
                yield self.env.timeout(zeiten['time_reset_einlauf'])

                # Fallrohr / Glas
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_fallrohr']))
                yield self.env.timeout(zeiten['time_reset_fallrohr'])

                # Sprühkugeln
                yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV043'], zeiten['time_cip_sprühkugeln']))
                yield self.env.timeout(zeiten['time_reset_sprühkugeln'])
            
            if cycle == 2:
                # Entleeren Kurz
                yield self.env.timeout(zeiten['time_entleeren'])
                yield self.env.timeout(zeiten['time_entleeren_delay'])
                yield self.env.timeout(zeiten['time_entleeren_nachlauf'])

                # Druckprüfung Lang
                yield self.env.timeout(zeiten['time_druckprüfung_lang'])
            
            if cycle == 3:
                # Füllen
                yield self.env.timeout(zeiten['time_fill'])
                yield self.env.timeout(zeiten['time_reset_fill'])

                # Rührer
                yield self.env.timeout(zeiten['time_cip_rührer'])

                # Abschluss Berechnung
                rest_zeit = int(total_duration - (self.env.now - start_time))
                
                if rest_zeit > 0:
                    yield self.env.timeout(rest_zeit)

            if cycle == 4:
                run = False
            
            cycle += 1

        debug(self.env, f'CIP', f'{self.name} - Reinigung beendet, Soll: {total_duration}, Ist: {self.env.now - start_time}')
        yield self.env.process(change_state(self, HYG_STAT.cleaned))
        self.last_clean_time = int(self.env.now)