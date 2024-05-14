from modules.tools import convertTime, debug
from modules.wfi_manager import WFIManager
from modules.container import Container, LB, AB, Partikel, Sole_Transfer, Keimfilter, VK
from modules.make_plots import plot, gantt
from modules.observer import Observer
from modules.states import HYG_STAT
from modules.routes import Routes

import simpy


SIM_TIME = convertTime((20, 0, 0))


def main():
    env = simpy.Environment()
    observer = Observer(sT=SIM_TIME)
    routes = Routes(env=env)
    
    env.process(wheel(env, observer, routes))
    env.run(until=SIM_TIME)

    plot(observer)
    gantt(observer)

def wheel(env, observer, routes):
    wfi = WFIManager(env, SIM_TIME, 40, observer)
    system = {
        "Lösebehälter": LB(env, SIM_TIME, 'LB', wfi, observer, routes),
        "Partikelfiltration": Partikel(env, SIM_TIME, 'Partikel', wfi, observer, routes),
        "Transferstrecke": Sole_Transfer(env, SIM_TIME, 'Transfer', wfi, observer, routes),
        "Abfüllbehälter_A": AB(env, SIM_TIME, 'AB1', wfi, observer, routes),
        "Abfüllbehälter_B": AB(env, SIM_TIME, 'AB2', wfi, observer, routes),
        "Keimfilter_A": Keimfilter(env, SIM_TIME, 'Keim1', wfi, observer, routes),
        "Keimfilter_B": Keimfilter(env, SIM_TIME, 'Keim2', wfi, observer, routes),
        "Ventilknoten": VK(env, SIM_TIME, 'VK', wfi, observer, routes),
    }

    stack = [
        env.process(system["Lösebehälter"].cip()),
        env.process(system["Lösebehälter"].sip()),
        env.process(system["Lösebehälter"].prod_lb()),
        env.process(system["Abfüllbehälter_A"].cip()),
        env.process(system["Abfüllbehälter_A"].sip()),
        env.process(system["Ventilknoten"].cip()),
        env.process(system["Ventilknoten"].sip()),
        env.process(system["Transferstrecke"].cip()),
        env.process(system["Transferstrecke"].sip()),
        env.process(system["Abfüllbehälter_A"].prod(system['Lösebehälter'])),
        env.process(system["Keimfilter_A"].cip()),
        env.process(system["Keimfilter_A"].sip()),
        env.process(system["Partikelfiltration"].cip()),
        env.process(system["Partikelfiltration"].sip()),

        # env.process(system["Abfüllbehälter_B"].cip()),
        # env.process(system["Keimfilter_B"].cip()),
        # env.process(system["Abfüllbehälter_B"].sip()),
        # env.process(system["Keimfilter_B"].sip()),
    ]

    stack_iter = iter(stack)

    while True:
        current_time = int(env.now)

        try:
            next(stack_iter)
        except StopIteration:
            pass

        for s in system:
            system[s].cycle()

        wfi.cycle()        
        observer.cycle(current_time)

        yield env.timeout(convertTime((0, 1)))

if __name__ == '__main__':
    main()
