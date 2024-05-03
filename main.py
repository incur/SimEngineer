from modules.tools import convertTime, debug
from modules.wfi_manager import WFIManager
from modules.container import Container, LB, AB
from modules.make_plots import plot
from modules.observer import Observer
from modules.states import HYG_STAT

import simpy

SIM_TIME = convertTime((5, 0, 0))


def main():
    env = simpy.Environment()
    observer = Observer(sT=SIM_TIME)
    wfi = WFIManager(env, SIM_TIME, 50, observer)

    vessels = [
        LB(env, SIM_TIME, '2010_A', wfi, observer),
        AB(env, SIM_TIME, '2020_A', wfi, observer),
    ]
    
    env.process(wheel(env, vessels, wfi, observer))
    env.run(until=SIM_TIME)

    plot(observer)

def wheel(env, vessels, wfi, observer):
    Lösebehälter = vessels[0]
    Abfüllbehälter_A = vessels[1]

    while True:
        current_time = int(env.now)
        
        if env.now == 10:
            env.process(Lösebehälter.cip(duration=convertTime((35, 0))))
            env.process(Abfüllbehälter_A.cip(duration=convertTime((35, 0))))
            env.process(Abfüllbehälter_A.sip(duration=convertTime((30, 0))))
            env.process(Lösebehälter.sip(duration=convertTime((30, 0))))
            env.process(Lösebehälter.prod_lb())
            env.process(Abfüllbehälter_A.prod(Lösebehälter))

        wfi.cycle()
        Lösebehälter.cycle()
        Abfüllbehälter_A.cycle()
        observer.cycle(current_time)

        yield env.timeout(1)

if __name__ == '__main__':
    main()
