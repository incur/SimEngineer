import simpy

def debug(env: simpy.Environment, function: str, msg: str):
    time = convertTime(env.now)
    time = f'{time[0]}:{time[1]:02d}:{time[2]:02d}'
    print(f'{time: ^20}{function: <25}{msg}')

def convertTime(value: int | float | tuple) -> int | tuple | bool:
    match value:
        case (_, _, _):
            hour, minute, seconds = value
            seconds = round(seconds + (minute * 60) + (hour * 3600))
            return seconds
        case (_, _):
            minute, seconds = value
            seconds = round(seconds + (minute * 60))
            return seconds
        case int() | float() | (int()):
            if isinstance(value, float):
                value = round(value)
            hour = value // 3600
            minute = (value % 3600) // 60
            seconds = value % 60
            return (hour, minute, seconds)
        case _:
            return False
