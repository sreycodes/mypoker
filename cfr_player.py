from __future__ import division
from collections import defaultdict
import sys
sys.path.insert(0, './pypokerengine/api/')
import game
import operator
from pypokerengine.api.emulator import Emulator
from pypokerengine.engine.dealer import Dealer
from pypokerengine.engine.message_builder import MessageBuilder
from pypokerengine.engine.poker_constants import PokerConstants as Const
from pypokerengine.engine.round_manager import RoundManager
from pypokerengine.engine.table import Table
from pypokerengine.players import BasePokerPlayer
import pprint
pp = pprint.PrettyPrinter(indent=2)
import random
from randomplayer import RandomPlayer

class CFRPlayer(BasePokerPlayer):

  def __init__(self, name="CFR", train=False):
    self.name = name
    self.player_index = 0
    self.imap = {}
    self.emulator = None
    if(train):
      self.train(1)

  def declare_action(self, valid_actions, hole_card, round_state):
    strategy = self.imap.get(str(hole_card) + str(round_state))
    print(strategy)
    if strategy == None:
      return random.choice(valid_actions)["action"]
    else:
      return max(strategy.get_average_strategy.iteritems(), key=operator.itemgetter(1))[0]['action']

  def receive_game_start_message(self, game_info):
    pass

  def receive_round_start_message(self, round_count, hole_card, seats):
    pass

  def receive_street_start_message(self, street, round_state):
    pass

  def receive_game_update_message(self, action, round_state):
    pass

  def receive_round_result_message(self, winners, hand_info, round_state):
    pass

  def __parse_ask_message(self, message):
    hole_card = message["hole_card"]
    valid_actions = message["valid_actions"]
    round_state = message["round_state"]
    return valid_actions, hole_card, round_state

  def setup_game(self, player1, player2):
    # # Init for one game
    # max_round = 1
    # initial_stack = 10000
    # smallblind_amount = 10
    # # Init pot of players
    # agent1_pot = 0
    # agent2_pot = 0
    # # Setting configuration
    # config = game.setup_config(max_round=max_round, initial_stack=initial_stack, small_blind_amount=smallblind_amount)
    # # Register players
    # config.register_player(name=player1.name, algorithm=player1)
    # config.register_player(name="Random", algorithm=player2)
    # config.validation()
    # dealer = Dealer(config.sb_amount, config.initial_stack, config.ante)
    # dealer.set_verbose(2)
    # dealer.set_blind_structure(config.blind_structure)
    # for info in config.players_info:
    #     dealer.register_player(info["name"], info["algorithm"])
    # table = dealer.table
    # ante, sb_amount = dealer.ante, dealer.small_blind_amount
    # if 1 in dealer.blind_structure:
    #   update_info = dealer.blind_structure[round_count]
    #   ante, sb_amount = update_info["ante"], update_info["small_blind"]    
    # table.set_blind_pos(0, 1)
    # if table.seats.players[table.dealer_btn].stack == 0: table.shift_dealer_btn()
    # start_state, msgs = RoundManager.start_new_round(1, smallblind_amount, ante, table)
    # return start_state
    table = Table()
    table.seats.sitdown(player1)
    table.seats.sitdown(player2)
    table.dealer_btn = len(table.seats.players)-1
    return {
      "round_count": 0,
      "small_blind_amount": 10,
      "street": Const.Street.PREFLOP,
      "next_player": None,
      "table": table
    }

  def train(self, num_iterations):
    print("Training")
    player1 = self
    player2 = self
    self.emulator = Emulator()
    self.emulator.set_game_rule(2, 10, 10, 0)
    self.emulator.register_player("cfr1", player1)
    self.emulator.register_player("cfr2", player2)
    util = 0
    for i in range(num_iterations):
      print("Iteration " + str(i))
      start_state, e = self.emulator.start_new_round(self.emulator.generate_initial_game_state({"cfr1": {"stack": 1000, "name": self.name}, "cfr2 ": {"stack": 1000, "name": "Random"}}))
      # print("Starting state: ")
      # pp.pprint(start_state)
      # pp.pprint(self.emulator.generate_possible_actions(start_state))
      # pp.pprint([p for p in start_state['table'].seats.players if p.name == self.name][0].hole_card)
      util += self.cfr(self.emulator.generate_possible_actions(start_state), [p for p in start_state['table'].seats.players if p.name == self.name][0].hole_card, start_state, 1, 1)
      print(util)
    print("Average game value: " + str(util / num_iterations))
    self = player1

  def cfr(self, valid_actions, hole_card, round_state, my_prob, opp_prob):
    print("------------ROUND_STATE(RANDOM)--------")
    pp.pprint(round_state)
    pp.pprint(valid_actions)
    pp.pprint(hole_card)
    if(round_state['street'] == Const.Street.FINISHED):
      print("This is a terminal state")
      return [p for p in round_state['table'].seats.players if p.name == self.name][0].stack - 1000
    info_set = self.imap.get(str(hole_card) + str(round_state))
    if info_set == None:
      print("Creating new info set")
      info_set = InfoSet(info=str(hole_card) + str(round_state), valid_actions=valid_actions)
      self.imap[str(hole_card) + str(round_state)] = info_set
    strategy = info_set.get_strategy(opp_prob if round_state['next_player'] == 0 else my_prob)
    util = defaultdict(int)
    info_set_util = 0
    random.shuffle(valid_actions)
    for action in valid_actions:
      print("Player decided to " + action["action"])
      next_round_state, messages = self.emulator.apply_action(round_state, action['action'])
      # print("Next state: ")
      # pp.pprint(next_round_state)
      valid_actions = self.emulator.generate_possible_actions(next_round_state)
      # pp.pprint(valid_actions)
      util[str(action)] = -1 * self.cfr(valid_actions, hole_card, next_round_state, my_prob, opp_prob * strategy[str(action)]) if round_state['next_player'] == 0 else -1 * self.cfr(valid_actions, hole_card, next_round_state, my_prob * strategy[str(action)], opp_prob)
      print("Utility of performing this action: " + str(util[str(action)]))
      # print("strategy: " + str(strategy[str(action)]))
      info_set_util += strategy[str(action)] * util[str(action)]
      print("Utility of this info set: " + str(info_set_util))
    for action in valid_actions:
      info_set.regret_sum[str(action)] += (opp_prob if round_state['next_player'] == 0 else my_prob) * (util[str(action)] - info_set_util)
    return info_set_util

class InfoSet():

  def __init__(self, info="", valid_actions=[]):
    self.info = info
    self.regret_sum = defaultdict(int)
    self.strategy = defaultdict(int)
    self.strategy_sum = defaultdict(int)
    self.valid_actions = valid_actions
    for action in self.valid_actions:
      self.strategy[str(action)] = (1 / float(len(self.valid_actions)))
      # print("Action: " + str(self.strategy[str(action)]))

  def get_strategy(self, realization_weight):
    norm_sum = 0
    for action in self.valid_actions:
      self.strategy[str(action)] = max(self.regret_sum.get(str(action)), 0)
      norm_sum += self.strategy[str(action)]
    for action in self.valid_actions:
      self.strategy[str(action)] = (self.strategy[str(action)] / norm_sum) if norm_sum > 0 else (1 / len(self.valid_actions))
      self.strategy_sum[str(action)] += realization_weight * self.strategy[str(action)]
    return self.strategy

  def get_average_strategy(self):
    norm_sum = 0
    avg_strategy = defaultdict(int)
    for action in self.valid_actions:
      norm_sum += self.strategy_sum.get(str(action), 0)
    for action in self.valid_actions:
      avg_strategy[str(action)] = self.strategy_sum.get(str(action), 0) / norm_sum if norm_sum > 0 else 1 / len(self.valid_actions)
    return avg_strategy

def setup_ai():
  player = CFRPlayer(name="CFR", train=True)
  player.train(1000)
  return player



