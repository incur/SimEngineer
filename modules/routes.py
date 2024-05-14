import simpy

class Routes:
    def __init__(self, env: simpy.Environment) -> None:
        self.env = env
        self.name = 'Routes'
        self.rLB_P = simpy.Resource(env, capacity=1)
        self.rP_T = simpy.Resource(env, capacity=1)
        self.rT_AB1 = simpy.Resource(env, capacity=1)
        self.rT_AB2 = simpy.Resource(env, capacity=1)
        self.rAB1_K1 = simpy.Resource(env, capacity=1)
        self.rAB2_K2 = simpy.Resource(env, capacity=1)
        self.rK1_VK = simpy.Resource(env, capacity=1)
        self.rK2_VK = simpy.Resource(env, capacity=1)
