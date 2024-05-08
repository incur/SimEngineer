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
    
    env.process(wheel(env, observer))
    env.run(until=SIM_TIME)

    plot(observer)

def wheel(env, observer):
    wfi = WFIManager(env, SIM_TIME, 50, observer)
    Lösebehälter = LB(env, SIM_TIME, '2010_A', wfi, observer)
    Abfüllbehälter_A = AB(env, SIM_TIME, '2020_A', wfi, observer)

    while True:
        current_time = int(env.now)
        
        if current_time == 0:
            env.process(Lösebehälter.cip_beh())
            env.process(Abfüllbehälter_A.cip_beh())
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
