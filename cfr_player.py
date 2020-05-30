from __future__ import division
from collections import defaultdict
import sys
sys.path.insert(0, './pypokerengine/api/')
import game
import operator
from pypokerengine.api.emulator import Emulator
from pypokerengine.engine.hand_evaluator import HandEvaluator
from pypokerengine.engine.poker_constants import PokerConstants as Const
from pypokerengine.players import BasePokerPlayer
from pypokerengine.engine.card import Card
from randomplayer import RandomPlayer
import pprint
pp = pprint.PrettyPrinter(indent=2)
import random
import pickle
from os import path
from multiprocessing import Pool

def pause():
  _ = input("Press any key to continue\n")
  pass

class Node:

  def __init__(self, parent, to_move, actions, actions_history):
    self.parent = parent
    self.to_move = to_move
    self.actions = actions
    self.actions_history = actions_history
    self.children = {}

  def play(self, action):
    return self.children[action]

  def is_chance(self):
    return type(self.to_move) == str and self.to_move.upper() == "CHANCE"

  def inf_set(self):
    raise NotImplementedError("Please implement information_set method")

class RootChanceNode(Node):

  def __init__(self):
    super().__init__(parent=None, to_move="CHANCE", actions=["P", "S", "N"], actions_history = [])

  def add_child(self, game_state, emulator, reach_a, reach_b):
    hole_card = game_state['table'].seats.players[0].hole_card
    card1, card2 = hole_card
    if card1.is_pair(card2):
      if "PAIRED" not in self.children.keys():
        self.children["PAIRED"] = PlayerNode(self, game_state['next_player'], ["PAIRED"], 
          [action['action'] for action in emulator.generate_possible_actions(game_state)])
      self.children["PAIRED"].add_child(game_state, emulator, reach_a, reach_b)
    elif card1.is_suited(card2):
      if "SUITED" not in self.children.keys():
          self.children["SUITED"] = PlayerNode(self, game_state['next_player'], ["SUITED"], 
            [action['action'] for action in emulator.generate_possible_actions(game_state)])
      self.children["SUITED"].add_child(game_state, emulator, reach_a, reach_b)
    else:
      if "NA" not in self.children.keys():
        self.children["NA"] = PlayerNode(self, game_state['next_player'], ["NA"], 
          [action['action'] for action in emulator.generate_possible_actions(game_state)])
      self.children["NA"].add_child(game_state, emulator, reach_a, reach_b)

  def is_terminal(self):
    return False

  def inf_set(self):
    return ""

  def sample_one(self):
    return random.choice(list(self.children.values()))

  def chance_prob(self):
    return (1 / len(self.actions))

  def compute_nash_equilibrium(self):
    for child in self.children.values():
      child.compute_nash_equilibrium()

class ComChanceNode(Node):

  def __init__(self, parent, actions_history):
    super().__init__(parent=parent, to_move="CHANCE", actions=["HC", "OP", "TP", "TC", "S", "F", "FH", "FC", "SF"],
      actions_history=actions_history)
    self._information_set = "".join(self.actions_history)

  def add_child(self, game_state, emulator, reach_a, reach_b):
    hole_card = game_state['table'].seats.players[0].hole_card
    community_cards = game_state['table']._community_card
    strength = HandEvaluator.gen_hand_rank_info(hole_card, community_cards)['hand']['strength']
    # print(strength)
    # print(self.children.keys())
    if strength not in self.children.keys():
      self.children[strength] = PlayerNode(self, game_state['next_player'], self.actions_history + [strength],
        [action['action'] for action in emulator.generate_possible_actions(game_state)])
    return self.children[strength].add_child(game_state, emulator, reach_a, reach_b)

  def is_terminal(self):
    return False

  def inf_set(self):
    return self._information_set

  def sample_one(self):
    return random.choice(list(self.children.values()))

  def chance_prob(self):
    return (1 / len(self.actions))  

  def compute_nash_equilibrium(self):
    for child in self.children.values():
      child.compute_nash_equilibrium()

class PlayerNode(Node):

  def __init__(self, parent, to_move, actions_history, actions):
    super().__init__(parent = parent, to_move = to_move, actions = actions, actions_history = actions_history)
    self._information_set = "".join(self.actions_history)
    self.utility = []
    if len(self.actions) > 0:
      self.sigma = {action: 1. / len(self.actions) for action in self.actions}
      self.cumulative_sigma = {action: 1e-5 for action in self.actions}
      self.cumulative_regret = {action: 1e-5 for action in self.actions}
      self.nash_equilibrium = {action: 1e-5 for action in self.actions}

  def add_child(self, game_state, emulator, reach_a, reach_b):
    # print(self.actions)
    if self.is_terminal():
      # print("here")
      reward = game_state['table'].seats.players[0].stack - 100 #Make better
      self.utility.append(reward)
      return self.evaluation()
    else:
      value = 0.
      csu = {}
      for a in self.actions:
        child_reach_a = reach_a * (self.sigma[a] if self.to_move == 0 else 1)
        child_reach_b = reach_b * (self.sigma[a] if self.to_move == 1 else 1)
        next_game_state, _ = emulator.apply_action(game_state, a)
        if next_game_state['street'] != game_state['street']:
          streets = ["PREFLOP,", "FLOP", "TURN", "RIVER", "SHOWDOWN"]
          if next_game_state['street'] in [Const.Street.FLOP, Const.Street.TURN, Const.Street.RIVER]:
            if a not in self.children.keys():
              self.children[a] = ComChanceNode(self, self.actions_history + [a])
            u = self.children[a].add_child(next_game_state, emulator, child_reach_a, child_reach_b)
          else:
            # print(a)
            self.children[a] = PlayerNode(self, next_game_state['next_player'], self.actions_history + [a], [])
            u = self.children[a].add_child(next_game_state, emulator, child_reach_a, child_reach_b)
        else:
          self.children[a] = PlayerNode(self, next_game_state['next_player'], self.actions_history + [a],
            [action['action'] for action in emulator.generate_possible_actions(next_game_state)])
          u = self.children[a].add_child(next_game_state, emulator, child_reach_a, child_reach_b)
        value +=  self.sigma[a] * u
        csu[a] = u
      (cfr_reach, reach) = (reach_b, reach_a) if self.to_move == 0 else (reach_a, reach_b)
      rgrt_sum = 0.
      for a in self.actions:
        self.cumulative_regret[a] += (1 if self.to_move == 0 else -1) * cfr_reach * (csu[a] - value)
        rgrt_sum += self.cumulative_regret[a] if self.cumulative_regret[a] > 0 else 0
      for a in self.actions:
        self.sigma[a] = max(self.cumulative_regret[a], 1e-5) / rgrt_sum if rgrt_sum > 0 else 1. / len(self.cumulative_regret.keys())
        self.cumulative_sigma[a] += reach * self.sigma[a]
      return value

  def inf_set(self):
    return self._information_set

  def is_terminal(self):
    return self.actions == []

  def evaluation(self):
    if self.is_terminal() == False:
      raise RuntimeError("trying to evaluate non-terminal node")

    return sum(self.utility) / len(self.utility)

  def compute_nash_equilibrium(self):
    if self.is_terminal():
      return
    sigma_sum = sum(self.cumulative_sigma.values())
    self.nash_equilibrium = {a: self.cumulative_sigma[a] / sigma_sum for a in self.actions}
    for child in self.children.values():
      child.compute_nash_equilibrium()

def setup_ai():
  if path.exists('./tree-test3-10000.pkl'):
    with open('tree-test3-10000.pkl', 'rb') as file:
      return pickle.load(file)

  root_node = RootChanceNode()
  num_iterations = 10000
  emulator = Emulator()
  emulator.set_game_rule(player_num=2, max_round=1, small_blind_amount=5, ante_amount=1)
  player_info = {"CFR1": {"name": "CFR-1", "stack": 100}, "CFR2": {"name": "CFR-2", "stack": 100}}
  initial_state = emulator.generate_initial_game_state(player_info) 
  for i in range(num_iterations):
    game_state, events = emulator.start_new_round(initial_state)
    root_node.add_child(game_state, emulator, 1, 1)

  with open('tree-test3-10000-incomplete.pkl', 'wb') as file:
    pickle.dump(root_node, file)

  root_node.compute_nash_equilibrium()

  with open('tree-test3-10000.pkl', 'wb') as file:
    pickle.dump(root_node, file)

  return root_node

def get_prefix(hole_card):
  card1, card2 = hole_card
  if card1.is_pair(card2):
    prefix = "PAIRED"
  elif card1.is_suited(card2):
    prefix = "SUITED"
  else:
    prefix = "NA"
  return prefix

def test_ai():
  root_node = setup_ai()
  emulator = Emulator()
  emulator.set_game_rule(player_num=2, max_round=10, small_blind_amount=5, ante_amount=1)
  earnings = []
  for i in range(10):
    game_worked = True
    actions = ""
    curr_node = root_node
    player_info = {"CFR1": {"name": "CFR-1", "stack": 1000}, "Random2": {"name": "Random-2", "stack": 1000}}
    initial_state = emulator.generate_initial_game_state(player_info)
    game_state, events = emulator.start_new_round(initial_state)
    curr_node = curr_node.children[get_prefix(game_state['table'].seats.players[0].hole_card)]
    curr_street = 0
    while(game_state['street'] <= 3):
      if(game_state['street'] > curr_street):
        curr_street = game_state['street']
        try:
          curr_node = curr_node.children[HandEvaluator.gen_hand_rank_info(game_state['table'].seats.players[0].hole_card,
            game_state['table']._community_card)['hand']['strength']]
        except Exception as e:
          print(curr_node.children, curr_node.parent.inf_set(), actions)
          print(e)
          game_worked = False
          break
      if game_state['next_player'] == 0:
        current_strategy = curr_node.nash_equilibrium
        action = max(current_strategy, key=current_strategy.get) 
        curr_node = curr_node.children[action]
        game_state, events = emulator.apply_action(game_state, action)
      else:
        # current_strategy = curr_node.nash_equilibrium
        # action = max(current_strategy, key=current_strategy.get) 
        # curr_node = curr_node.children[action]
        # game_state, events = emulator.apply_action(game_state, action)
        # pa = [a['action'] for a in emulator.generate_possible_actions(game_state)]
        # if 'raise' in pa:
        #   action = 'raise'
        # else:
        action = random.choice(pa)
        curr_node = curr_node.children[action]
        game_state, events = emulator.apply_action(game_state, action)
      actions += (action)
    if game_worked:
      earnings.append(game_state['table'].seats.players[0].stack - 1000)
  print(earnings)

if __name__ == '__main__':
  test_ai()
  




