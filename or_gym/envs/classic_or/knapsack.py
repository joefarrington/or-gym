import numpy as np
import gym
from gym import spaces, logger
from gym.utils import seeding
from or_gym.utils.env_config import *
import copy

class KnapsackEnv(gym.Env):
    '''
    Unbounded Knapsack Problem

    The Knapsack Problem (KP) is a combinatorial optimization problem which
    requires the user to select from a range of goods of different values and
    weights in order to maximize the value of the selected items within a 
    given weight limit. This version is unbounded meaning that we can select
    items without limit. 

    The episodes proceed by selecting items and placing them into the
    knapsack one at a time until the weight limit is reached or exceeded, at
    which point the episode ends.

    Observation:
        Type: Tuple, Discrete
        0: list of item weights
        1: list of item values
        2: maximum weight of the knapsack
        3: current weight in knapsack

    Actions:
        Type: Discrete
        0: Place item 0 into knapsack
        1: Place item 1 into knapsack
        2: ...

    Reward:
        Value of item successfully placed into knapsack or 0 if the item
        doesn't fit, at which point the episode ends.

    Starting State:
        Lists of available items and empty knapsack.

    Episode Termination:
        Full knapsack or selection that puts the knapsack over the limit.
    '''
    
    def __init__(self, *args, **kwargs):
        # Generate data with consistent random seed to ensure reproducibility
        self.N = 200
        self.item_numbers = np.arange(self.N)
        self.max_weight = 200
        self.current_weight = 0
        self._max_reward = 6000
        self.seed = 0
        # Add env_config, if any
        assign_env_config(self, kwargs)
        values = np.random.randint(30, size=self.N)
        weights = np.random.randint(1, 20, size=self.N)
        limits = np.random.randint(1, 10, size=self.N)
        self.item_weights = weights
        self.item_values = values
        
        self.action_space = spaces.Discrete(self.N)
        self.observation_space = spaces.Box(
            0, self.max_weight, shape=(2, self.N + 1), 
            dtype=np.int16)
        
        self.set_seed(self.seed)
        self.reset()
        
    def step(self, item):
        # Check that item will fit
        if self.item_weights[item] + self.current_weight <= self.max_weight:
            self.current_weight += self.item_weights[item]
            reward = self.item_values[item]
            if self.current_weight == self.max_weight:
                done = True
            else:
                done = False
        else:
            # End trial if over weight
            reward = 0
            done = True
            
        self._update_state()
        return self.state, reward, done, {}
    
    def _get_obs(self):
        return self.state
    
    def _update_state(self):
        self.state = np.vstack([
            self.item_weights,
            self.item_values
        ])
        self.state = np.hstack([
            self.state, 
            np.array([[self.max_weight],
                      [self.current_weight]])
        ])
    
    def reset(self):
        self.current_weight = 0
        self._update_state()
        return self.state
    
    def sample_action(self):
        return np.random.choice(self.item_numbers)

    def set_seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]


class BoundedKnapsackEnv(KnapsackEnv):
    '''
    Bounded Knapsack Problem

    The Knapsack Problem (KP) is a combinatorial optimization problem which
    requires the user to select from a range of goods of different values and
    weights in order to maximize the value of the selected items within a 
    given weight limit. This version is bounded meaning each item can be
    selected a limited number of times.

    The episodes proceed by selecting items and placing them into the
    knapsack one at a time until the weight limit is reached or exceeded, at
    which point the episode ends.

    Observation:
        Type: Tuple, Discrete
        0: list of item weights
        1: list of item values
        2: list of item limits
        3: maximum weight of the knapsack
        4: current weight in knapsack

    Actions:
        Type: Discrete
        0: Place item 0 into knapsack
        1: Place item 1 into knapsack
        2: ...

    Reward:
        Value of item successfully placed into knapsack or 0 if the item
        doesn't fit, at which point the episode ends.

    Starting State:
        Lists of available items and empty knapsack.

    Episode Termination:
        Full knapsack or selection that puts the knapsack over the limit.
    '''
    def __init__(self, *args, **kwargs):
        self.item_limits_init = np.random.randint(1, 10, size=200)
        self.item_limits = self.item_limits_init.copy()
        super().__init__()
        obs_space = spaces.Box(
            0, self.max_weight, shape=(3, self.N + 1), dtype=np.int32)
        self.observation_space = spaces.Dict({
            "action_mask": spaces.Box(0, 1, shape=(len(self.item_limits),)),
            "avail_actions": spaces.Box(0, 1, shape=(len(self.item_limits),)),
            "state": obs_space
            })
        # self.observation_space = spaces.Box(
        #     0, self.max_weight, shape=(3, self.N + 1), dtype=np.int32)
        self._max_reward = 1800 # Used for VF clipping
        
    def step(self, item):
        # Check item limit
        if self.item_limits[item] > 0:
            # Check that item will fit
            if self.item_weights[item] + self.current_weight <= self.max_weight:
                self.current_weight += self.item_weights[item]
                reward = self.item_values[item]
                if self.current_weight == self.max_weight:
                    done = True
                else:
                    done = False
                self._update_state(item)
            else:
                # End if over weight
                reward = 0
                done = True
        else:
            # End if item is unavailable
            reward = 0
            done = True
            
        return self.state, reward, done, {}

    def _update_state(self, item=None):
        if item is not None:
            self.item_limits[item] -= 1
        state_items = np.vstack([
            self.item_weights,
            self.item_values,
            self.item_limits
        ])
        state = np.hstack([
            state_items, 
            np.array([[self.max_weight],
                      [self.current_weight], 
                      [0] # Serves as place holder
                ])
        ])
        mask = np.where(self.current_weight + self.item_weights > self.max_weight,
            0, 1)
        mask = np.where(self.item_limits > 0, mask, 0)
        self.state = {
            "action_mask": mask,
            "avail_actions": np.ones(self.N),
            "state": state
        }
        
    def sample_action(self):
        return np.random.choice(
            self.item_numbers[np.where(self.item_limits!=0)])
    
    def reset(self):
        self.current_weight = 0
        self.item_limits = self.item_limits_init.copy()
        self._update_state()
        return self.state

class OnlineKnapsackEnv(BoundedKnapsackEnv):
    '''
    Online Knapsack Problem

    The Knapsack Problem (KP) is a combinatorial optimization problem which
    requires the user to select from a range of goods of different values and
    weights in order to maximize the value of the selected items within a 
    given weight limit. This version is online meaning each item is randonly
    presented to the algorithm one at a time, at which point the algorithm 
    can either accept or reject the item. After seeing a fixed number of 
    items are shown, the episode terminates. If the weight limit is reached
    before the episode ends, then it terminates early.

    Observation:
        Type: Tuple, Discrete
        0: list of item weights
        1: list of item values
        2: list of item limits
        3: maximum weight of the knapsack
        4: current weight in knapsack


    Actions:
        Type: Discrete
        0: Reject item
        1: Place item into knapsack

    Reward:
        Value of item successfully placed into knapsack or 0 if the item
        doesn't fit, at which point the episode ends.

    Starting State:
        Lists of available items and empty knapsack.

    Episode Termination:
        Full knapsack, selection that puts the knapsack over the limit, or
        the number of items to be drawn has been reached.
    '''
    def __init__(self, *args, **kwargs):
        BoundedKnapsackEnv.__init__(self)
        self.action_space = spaces.Discrete(2)
        # self.observation_space = spaces.Tuple((
        #     spaces.Box(0, self.max_weight, shape=(self.N,)), # Weights
        #     spaces.Box(0, self.max_weight, shape=(self.N,)), # Values
        #     spaces.Box(0, self.max_weight, shape=(self.N,)), # Probs
        #     spaces.Box(0, self.max_weight, shape=(3,))))
        self.observation_space = spaces.Box(0, self.max_weight, shape=(4,))

        self.step_counter = 0
        self.step_limit = 50
        
        self.state = self.reset()
        self._max_reward = 600
        
    def step(self, action):
        # Check that item will fit
        if bool(action):
            # Check that item will fit
            if self.item_weights[self.current_item] + self.current_weight <= self.max_weight:
                self.current_weight += self.item_weights[self.current_item]
                reward = self.item_values[self.current_item]
                if self.current_weight == self.max_weight:
                    done = True
                else:
                    done = False
                self._update_state()
            else:
                # End if over weight
                reward = 0
                done = True
        else:
            reward = 0
            done = False
            
        self.step_counter += 1
        if self.step_counter >= self.step_limit:
            done = True
            
        return self.state, reward, done, {}
    
    def _update_state(self):
        self.current_item = np.random.choice(self.item_numbers, p=self.item_probs)
        self.state = (
            # self.item_weights,
            # self.item_values,
            # self.item_probs,
            np.array([
                # self.max_weight,
                self.current_weight,
                self.current_item,
                self.item_weights[self.current_item],
                self.item_values[self.current_item]
            ]))
        
    def sample_action(self):
        return np.random.choice([0, 1])
    
    def reset(self):
        if not hasattr(self, 'item_probs'):
            self.item_probs = self.item_limits_init / self.item_limits_init.sum()
        self.current_weight = 0
        self.step_counter = 0
        self.item_limits = self.item_limits_init.copy()
        self._update_state()
        return self.state

