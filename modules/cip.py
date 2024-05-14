from modules.tools import debug, convertTime, aufteilen, generate_random_time
from modules.states import HYG_STAT, change_state

DEBUG = False

class CIPError(Exception):
    pass


class MissingKeyError(CIPError):
    def __init__(self, key, dictionary):
        super().__init__(f"Schlüssel '{key}' nicht in '{dictionary}' gefunden")


def cip_vessel(self, LB: bool, wfi_rates, fill_rates, durations):
    start_time = self.env.now
    total_duration = generate_random_time(durations)

    if DEBUG:
        total_duration = durations['lower']

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
        "time_init_entleeren":              convertTime((0, 30)),
        "time_init_nachlauf":               convertTime((0, 190)),
        'time_druckprüfung_kurz':           convertTime((5, 0)),

        "time_cip_container_zugabe":        self.flow_time(self.fill_rates['UV043'], 60),
        "time_reset_container_zugabe":      convertTime((0, 33)),
        "time_cip_handzugabe":              self.flow_time(self.fill_rates['UV043'], 40),
        "time_reset_handzugabe":            convertTime((0, 33)),
        "time_cip_rohstoffzugabe":          self.flow_time(self.fill_rates['UV043'], 60),
        "time_reset_rohstoffzugabe":        convertTime((0, 33)),
        "time_cip_trans_in":                convertTime((0, 300)),
        "time_reset_trans_in":              convertTime((0, 33)),
        "time_cip_fallrohr":                self.flow_time(self.fill_rates['UV043'], 300),
        "time_reset_fallrohr":              convertTime((0, 33)),
        "time_cip_einlauf":                 self.flow_time(self.fill_rates['UV043'], 80),
        "time_reset_einlauf":               convertTime((0, 33)),
        "time_cip_sprühkugeln":             self.flow_time(self.fill_rates['UV043'], 300),
        "time_reset_sprühkugeln":           convertTime((0, 33)),

        'time_entleeren':                   convertTime((10, 0)),
        "time_entleeren_delay":             convertTime((0, 60)),
        "time_entleeren_nachlauf":          convertTime((0, 180)),
        'time_druckprüfung_lang':           convertTime((5, 0)),

        "time_fill":                        convertTime((5, 0)),
        "time_reset_fill":                  convertTime((0, 35)),
        "time_cip_rührer":                  convertTime((0, 300)),
    }

    # with self.resource.request() as req:
    #     yield req

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
            
            if rest_zeit > 0 and not DEBUG:
                yield self.env.timeout(convertTime((0, rest_zeit)))

        if cycle == 4:
            run = False
        
        cycle += 1

    debug(self.env, f'CIP', f'{self.name} - Reinigung beendet, Soll: {total_duration}, Ist: {self.env.now - start_time}')
    yield self.env.process(change_state(self, HYG_STAT.cleaned))
    self.last_clean_time = int(self.env.now)


def cip_transf(self, wfi_rates, durations):
    start_time = self.env.now
    total_duration = generate_random_time(durations)

    if DEBUG:
        total_duration = durations['lower']

    required_keys = {
        True: ['UV373']
    }

    for key in required_keys[True]:
        if key not in wfi_rates:
            raise MissingKeyError(key, dictionary='wfi_rates')
        
    zeiten = {
        "time_start":                   convertTime((0, 60)),
        "time_ausblasen":               convertTime((0, 60)),
        "time_transfer":                convertTime((0, 60)),
        "time_entleeren":               convertTime((0, 120)),
        "time_route_sleep":             convertTime((0, 3)),
        "time_delay":                   convertTime((0, 5)),
    }

    # with self.resource.request() as req:
    #     yield req

    yield self.env.process(change_state(self, HYG_STAT.cleaning))
    debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

    cycle = 0
    run = True
    while run:
        if cycle == 0:
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_entleeren'])

        if cycle in (1, 2, 3):
            # CIP Start
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_start']))

            # Start Trans A
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_transfer']))

            # Start Trans B
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_transfer']))

            # Ausblasen
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_ausblasen'])

            # Medien Grundstellung
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_delay'])

        if cycle == 4:
            # Grundstellung
            yield self.env.timeout(zeiten['time_route_sleep'])

            # Abschluss Berechnung
            rest_zeit = int(total_duration - (self.env.now - start_time))
            
            if rest_zeit > 0 and not DEBUG:
                yield self.env.timeout(convertTime((0, rest_zeit)))

            run = False
        
        cycle += 1

    debug(self.env, f'CIP', f'{self.name} - Reinigung beendet, Soll: {total_duration}, Ist: {self.env.now - start_time}')
    yield self.env.process(change_state(self, HYG_STAT.cleaned))
    self.last_clean_time = int(self.env.now)

def cip_filter(self, wfi_rates, durations):
    start_time = self.env.now
    total_duration = generate_random_time(durations)

    if DEBUG:
        total_duration = durations['lower']

    required_keys = {
        True: ['UV373']
    }

    for key in required_keys[True]:
        if key not in wfi_rates:
            raise MissingKeyError(key, dictionary='wfi_rates')
        
    zeiten = {
        "time_start":                   convertTime((0, 10)),
        "time_filter":                  convertTime((0, 10)),
        "time_ausblasen":               convertTime((0, 180)),
        "time_transfer":                   convertTime((0, 120)),
        "time_entleeren":               convertTime((0, 120)),
        "time_route_sleep":             convertTime((0, 3)),
        "time_delay":                   convertTime((0, 5)),
    }

    # with self.resource.request() as req:
    #     yield req

    yield self.env.process(change_state(self, HYG_STAT.cleaning))
    debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

    cycle = 0
    run = True
    while run:
        if cycle == 0:
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_entleeren'])

        if cycle in (1, 2, 3):
            # CIP Start
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_start']))

            # Start Filter 1
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_filter']))

            # Start Filter 2
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_filter']))

            # Start Transfer
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_transfer']))

            # Ausblasen
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_ausblasen'])

            # Ausblasen Ende
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_delay'])

        if cycle == 4:
            # Entleeren
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_entleeren'])
            
            # Grundstellung
            yield self.env.timeout(zeiten['time_route_sleep'])

            # Abschluss Berechnung
            rest_zeit = int(total_duration - (self.env.now - start_time))
            
            if rest_zeit > 0 and not DEBUG:
                yield self.env.timeout(convertTime((0, rest_zeit)))

            run = False
        
        cycle += 1

    debug(self.env, f'CIP', f'{self.name} - Reinigung beendet, Soll: {total_duration}, Ist: {self.env.now - start_time}')
    yield self.env.process(change_state(self, HYG_STAT.cleaned))
    self.last_clean_time = int(self.env.now)

def cip_knoten(self, wfi_rates, durations):
    start_time = self.env.now
    total_duration = generate_random_time(durations)

    if DEBUG:
        total_duration = durations['lower']

    required_keys = {
        True: ['UV373']
    }

    for key in required_keys[True]:
        if key not in wfi_rates:
            raise MissingKeyError(key, dictionary='wfi_rates')
        
    zeiten = {
        "time_ausblasen":                   convertTime((0, 60)),
        "time_cip_afknt":                   convertTime((0, 60)),
        "time_cip_a":                       convertTime((0, 60)),
        "time_cip_b":                       convertTime((0, 60)),
        "time_entleeren":                   convertTime((0, 60)),

        "time_route_sleep":             convertTime((0, 10)),
        "time_delay":                   convertTime((0, 5)),
    }

    # with self.resource.request() as req:
    #     yield req

    yield self.env.process(change_state(self, HYG_STAT.cleaning))
    debug(self.env, f'CIP', f'{self.name} - Reinigung gestartet')

    cycle = 0
    run = True
    while run:
        if cycle == 0:
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_entleeren'])

        if cycle in (1, 2):
            # CIP AFKNT
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_cip_afknt']))

            # Ausblasen AFKNT
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_ausblasen'])

            # CIP A
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_cip_a']))

            # Ausblasen A
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_ausblasen'])

            # CIP B
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.process(self.request_and_release_wfi(self.wfi_rates['UV373'], zeiten['time_cip_b']))

            # Ausblasen B
            yield self.env.timeout(zeiten['time_route_sleep'])
            yield self.env.timeout(zeiten['time_ausblasen'])

            # Grundstellung
            yield self.env.timeout(zeiten['time_route_sleep'])

        if cycle == 3:
            yield self.env.timeout(zeiten['time_delay'])

            # Abschluss Berechnung
            rest_zeit = int(total_duration - (self.env.now - start_time))
            
            if rest_zeit > 0 and not DEBUG:
                yield self.env.timeout(convertTime((0, rest_zeit)))

            run = False
        
        cycle += 1

    debug(self.env, f'CIP', f'{self.name} - Reinigung beendet, Soll: {total_duration}, Ist: {self.env.now - start_time}')
    yield self.env.process(change_state(self, HYG_STAT.cleaned))
    self.last_clean_time = int(self.env.now)

def sip_default(self, durations):
    total_duration = generate_random_time(durations)

    yield self.env.process(change_state(self, HYG_STAT.sanitizing))
    debug(self.env, f'SIP', f'{self.name} - Sanitisierung gestartet')

    yield self.env.timeout(total_duration)

    debug(self.env, f'SIP', f'{self.name} - Sanitisierung beendet')
    yield self.env.process(change_state(self, HYG_STAT.sanitized))
    self.last_clean_time = int(self.env.now)


