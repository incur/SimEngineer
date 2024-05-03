from enum import Enum
from modules.tools import debug, convertTime

class HYG_STAT(Enum):
    dirty = 1
    cleaning = 2
    cleaned = 3
    sanitizing = 4
    sanitized = 5
    production = 6

def change_state(container, new_state):
    time_required = convertTime((1, 0))

    allowed_transitions = {
        HYG_STAT.dirty: [HYG_STAT.cleaning],
        HYG_STAT.cleaning: [HYG_STAT.dirty, HYG_STAT.cleaned],
        HYG_STAT.cleaned: [HYG_STAT.dirty, HYG_STAT.cleaning, HYG_STAT.sanitizing],
        HYG_STAT.sanitizing: [HYG_STAT.dirty, HYG_STAT.sanitized],
        HYG_STAT.sanitized: [HYG_STAT.dirty, HYG_STAT.cleaning, HYG_STAT.sanitizing, HYG_STAT.production],
        HYG_STAT.production: [HYG_STAT.dirty],
    }

    if new_state in allowed_transitions.get(container.state, []):
        yield container.env.timeout(time_required)
        container.state = new_state
        debug(container.env, f'Status Change', f'{container.name} - {container.state}')
