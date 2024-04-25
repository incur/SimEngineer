from modules.tools import convertTime, debug
from modules.wfi_manager import WFIManager
from modules.vessel import Container

import simpy
import numpy as np
import matplotlib.pyplot as plt

SIM_TIME = convertTime((5, 0, 0))

def plot(vessels: list[Container], wfi: WFIManager):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True)
    fig.subplots_adjust(hspace=0)
    ax1.plot(vessels[0].track_state)
    ax1.plot(vessels[1].track_state)
    ax2.plot(vessels[0].track_volume)
    ax2.plot(vessels[1].track_volume)
    ax3.plot(wfi.track_capacity)
    ax3.plot(wfi.track_reserved)

    n_ticks = 20
    x = np.arange(SIM_TIME)
    x_labels = [f"{int(hour):02d}:{int(minute):02d}" for hour, minute in zip(x // 3600, (x % 3600) // 60)]
    tick_position = np.arange(0, SIM_TIME, SIM_TIME // n_ticks)
    tick_labels = [x_labels[i] for i in tick_position]

    ax3.set_xticks(tick_position)
    ax3.set_xticklabels(tick_labels, rotation=90)
    plt.show()

def main():
    env = simpy.Environment()
    wfi = WFIManager(env, SIM_TIME, 50)

    vessels = [
        Container(env, SIM_TIME, '2010_A', wfi),
        Container(env, SIM_TIME, '2020_A', wfi),
    ]
    
    env.process(wheel(env, vessels, wfi))
    env.run(until=SIM_TIME)

    plot(vessels, wfi)

def wheel(env, vessels, wfi):
    while True:
        if env.now == 0:
            env.process(vessels[0].cip(duration=convertTime((35, 0))))
            env.process(vessels[1].cip(duration=convertTime((35, 0))))
            env.process(vessels[1].sip(duration=convertTime((30, 0))))
            env.process(vessels[0].sip(duration=convertTime((30, 0))))
            env.process(vessels[0].prod_lb())
            env.process(vessels[1].prod(vessels[0]))

        wfi.cycle()
        for vessel in vessels:
            vessel.cycle()
        
        yield env.timeout(1)

if __name__ == '__main__':
    main()
