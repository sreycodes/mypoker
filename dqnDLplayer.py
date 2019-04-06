from pypokerengine.players import BasePokerPlayer
import numpy as np
from agent.dqn_agent import DQNAgent


RAISE_AMTS = [10]


class DQNPlayer(BasePokerPlayer):
    def __init__(self, agent, init_stack_size):
        super(DQNPlayer, self).__init__()
        self.agent = agent
        self.prev_stack_size = init_stack_size
        self.prev_state = None
        self.prev_action = None
        self.prev_reward = 0
        self.player_idx = None
        self.player_uuid = None
        self.bb_amount = None

    def declare_action(self, valid_actions, hole_cards, game_state):
        if self.player_idx is None:
            self.player_idx = game_state['next_player']
            self.player_uuid = game_state['seats'][self.player_idx]['uuid']
            self.bb_amount = game_state['small_blind_amount'] * 2

        print('dqnplayer')
        valid_actions_list = []
        for actions_dict in valid_actions:
            valid_actions_list.append(actions_dict['action'])
        features = self.agent.make_features(valid_actions, hole_cards, game_state)
        actions = self.agent.act(features)

        action_str, chosen_action, amount = None, None, 0
        sorted_by_best_action = np.argsort(actions)[::-1]   # first entry is index of best action

        _valid_action, _valid_action_idx = False, 0

        while not _valid_action:     # find best valid action
            chosen_action = sorted_by_best_action[_valid_action_idx]
            if chosen_action == 0:
                action_str = 'fold'
                # amount = 0
                _valid_action = True
                break
            elif chosen_action == 1:
                action_str = 'call'
                # amount = valid_actions[1]['amount']
                _valid_action = True
                break
            else:
                action_str = 'raise'
                if action_str not in valid_actions_list:
                    _valid_action_idx = _valid_action_idx + 1
                    continue
                # amount = RAISE_AMTS[chosen_action-2] * self.bb_amount
                # if valid_actions[2]['amount']['min'] <= amount <= valid_actions[2]['amount']['max']:
                #     _valid_action = True
                #     break
                # else:
                #     _valid_action_idx += 1
                _valid_action = True
                break

        new_stack_size = game_state['seats'][self.player_idx]['stack']
        reward = (new_stack_size - self.prev_stack_size) / self.bb_amount
        # print('Going to remember {} reward for {} action'.format(reward, self.prev_action))
        if self.prev_action is not None:
            self.agent.remember(self.prev_state, self.prev_action, reward, features, 0)

        self.prev_reward = reward # reward for chosen_action
        self.prev_stack_size = new_stack_size
        self.prev_state = features
        self.prev_action = chosen_action
        return action_str  # , amount

    def receive_round_result_message(self, winners, hand_info, round_state):
        pass

    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, new_action, round_state):
        pass


N_AGENTS = 2
STATE_SIZE = 125
BB_SIZE = 10
STACK_SIZE = 200
N_ACTIONS = 3
EPSILON = 0.01


def setup_ai(model_path):
    agent = DQNAgent(STATE_SIZE, N_ACTIONS, N_AGENTS, EPSILON, None, None, 0.95)
    agent.load(model_path)
    return DQNPlayer(agent, STACK_SIZE)
