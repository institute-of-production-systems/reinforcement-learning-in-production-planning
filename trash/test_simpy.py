import simpy
import gymnasium as gym
import numpy as np

class ProductionSystemEnv(gym.Env):
    def __init__(self, production_system):
        super().__init__()
        self.production_system = production_system
        self.time = 0