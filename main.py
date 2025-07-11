import random
import math
import json
import ast

COUNTRY_COUNT = 10
PERCEPTION_VALUE = 3
country_list = []
power_levels = [0, 5, 10, 16]
max_connections = [0, 1, 3, 5]

q_table = {}
epsilon = 0.01  # chance of mutation
alpha = 0.5  # learning rate
gamma = 0.7  # discount factor

'''
To-Do list:
    - Create playable character
    - Vary strategies
'''

#  Standard Benchmarking Test: 10 countries, 100 turns, 100 games, 0.01 epsilon (0.99 decay rate)
#  Current/Best model benchmarks: ~4.52 B (highest reserve), ~1.54 B (average reserve), ~186 M (highest income per turn)


def load_q_table(filename='q_table.json'):
    global q_table
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            q_table = {ast.literal_eval(k): v for k, v in data.items()}
    except FileNotFoundError:
        q_table = {}


def save_q_table(filename='q_table.json'):
    with open(filename, 'w') as file:
        json.dump({str(k): v for k, v in q_table.items()}, file)


class Countries:
    def __init__(self, index):
        self.name = index
        self.towns = 0
        self.markets = 0
        self.mines = 0
        self.connections = []
        self.power_level = 1
        self.reserve = 0
        self.life_time_earning = 0
        self.perception = [0] * COUNTRY_COUNT
        self.actions = (self.purchase_mine, self.purchase_town, self.purchase_connection, self.purchase_blockade,
                        self.remove_connection, self.remove_blockade, self.do_nothing)

    def __repr__(self):
        return (f"\n{self.name} = Towns: {self.towns} + {self.markets} ({self.power_level}), "
                f"Mines: {self.mines}, Connections: {self.connections}, Money: {self.reserve} ({self.life_time_earning})")

    def find_power_level(self):
        for level, min_towns in enumerate(power_levels):
            if (self.towns + self.markets) >= min_towns:
                self.power_level = level + 1

    def generate_money(self, generated=True):
        income = self.mines + self.power_level

        for connection in self.connections:
            is_not_blockaded = True

            for importer_connection in country_list[connection[0]].connections:
                if importer_connection[0] == self.name and importer_connection[2]:
                    is_not_blockaded = False
                    break

            if is_not_blockaded:
                income += math.floor(self.mines / 2)
                income += math.floor((country_list[connection[0]].towns + country_list[connection[0]].markets) / max(1, 6 - connection[1]))
                if generated:
                    country_list[connection[0]].reserve -= connection[1]

        if generated:
            self.reserve += income
            self.life_time_earning += income
        else:
            return income

    def find_perception(self):
        pre_perception = self.perception
        self.perception = [0] * COUNTRY_COUNT
        for country in country_list:
            for connection in country.connections:
                if connection[0] == self.name:
                    self.perception[country.name] += 10 * connection[1]
                    if connection[2]:
                        self.perception[country.name] -= 15 + 5 * connection[1]

        for connection in self.connections:
            if connection[2]:
                self.perception[connection[0]] += 5 * connection[1]
            else:
                self.perception[connection[0]] += 10 + 4 * connection[1]

        for j, old_perception in enumerate(pre_perception):
            if old_perception > self.perception[j]:
                self.perception[j] -= 10

    def purchase_mine(self, turn):
        mine_cost = 7
        first_mine_cost = 3

        cost = first_mine_cost if self.mines == 0 else mine_cost

        if self.reserve >= cost * turn * 5 and turn > 10:
            self.reserve -= cost * turn * 5
            self.mines += turn * 5
        elif self.reserve >= cost:
            self.reserve -= cost
            self.mines += turn

    def purchase_town(self):
        town_cost = self.power_level

        if self.reserve >= town_cost:
            self.reserve -= town_cost
            self.towns += 1

    def purchase_connection(self, random_importer=False):
        max_connection_level = 3
        first_connection_cost = 3

        if random_importer:
            importer = random.choice([j for j in range(COUNTRY_COUNT) if j != self.name])
        else:
            reward = (-1, None)
            imports, blockaded, reward_list = [], [], []

            for country in country_list:
                for connection in country.connections:
                    if connection[0] == self.name and not connection[2]:
                        imports.append(connection[0])
                        blockaded.append(connection[2])

            for importer_i, importer in enumerate(country_list):
                if importer_i == self.name:
                    continue

                connection_level = 1
                for c in self.connections:
                    if c[0] == importer_i:
                        connection_level = c[1] + 1
                        break

                if connection_level <= 3:
                    value = (4 * math.floor((importer.towns + importer.markets) / max(1, 6 - connection_level))) - connection_level * 6
                    value += PERCEPTION_VALUE * self.perception[importer_i]
                    if value >= reward[0]:
                        if value > reward[0]:
                            reward_list = []
                            reward = (value, importer.name)
                        reward_list.append((value, importer.name))

            if reward[1] is None:
                return
            importer = reward_list[random.randint(0, len(reward_list) - 1)][1]

        connection_found = False
        connection_level = 1
        found_connection = None

        for connection in self.connections:
            if connection[0] == importer:
                if connection[1] < max_connection_level:
                    found_connection = connection
                    connection_found = True
                    connection_level = connection[1] + 1
                else:
                    return
                break

        connection_cost = 6 * connection_level
        cost = first_connection_cost if len(self.connections) == 0 else connection_cost
        if self.reserve >= cost and len(self.connections) + 1 <= max_connections[self.power_level - 1]:
            if connection_found:
                found_connection[1] += 1

            else:
                # [country_index, connection_level, is_blocked]
                self.connections.append([country_list[importer].name, 1, False])

            # Starting bonus for importer, also allows for an instant blockade (blockade cost = 3)
            country_list[importer].reserve += 3
            country_list[importer].life_time_earning += 3
            country_list[importer].markets += 1

            self.reserve -= cost

    def remove_connection(self, random_importer=False):
        if not self.connections:
            return

        if random_importer:
            self.connections.pop(random.randint(0, len(self.connections) - 1))
        else:
            connector_names = {conn[0] for conn in self.connections}
            best_cut_score, fallback_cut_score = float('-inf'), float('-inf')
            best_cut_list, fallback_cut_list = [], []

            for connection in self.connections:
                country = country_list[connection[0]]

                estimated_income = (math.floor(country.mines / 2)
                                    + math.floor((self.towns + self.markets) / max(1, 6 - connection[1]))
                                    + connection[1] * 3)  # Add value to AI losing from connection

                estimated_income += -PERCEPTION_VALUE * self.perception[country_list[connection[0]].name]

                if country.name not in connector_names:
                    if estimated_income >= best_cut_score:
                        if estimated_income == best_cut_score:
                            best_cut_list = []
                        else:
                            best_cut_score = estimated_income
                        best_cut_list.append(country.name)
                else:
                    if estimated_income >= fallback_cut_score:
                        if estimated_income == best_cut_score:
                            fallback_cut_list = []
                        else:
                            fallback_cut_score = estimated_income
                        fallback_cut_list.append(country.name)

            selected = country_list[best_cut_list[random.randint(0, len(best_cut_list) - 1)]] if len(best_cut_list) else (
                country_list)[fallback_cut_list[random.randint(0, len(fallback_cut_list) - 1)]]
            if not selected:
                return
            self.connections = [c for c in self.connections if c[0] != selected]

    def purchase_blockade(self, random_importer=False):  # Smart by default
        blockade_cost = 3
        imports = []

        if self.reserve >= blockade_cost:
            for country in country_list:
                for connection in country.connections:
                    if connection[0] == self.name and not connection[2]:
                        imports.append((country, connection))

            if imports:
                if random_importer:
                    target_country, selected_connection = random.choice(imports)
                else:
                    connector_names = {conn[0] for conn in self.connections}
                    best_cut, fallback_cut = None, None
                    fallback_cut_score, best_cut_score = float('-inf'), float('-inf')
                    best_cut_list, fallback_cut_list = [], []

                    for country, connection in imports:
                        estimated_income = (math.floor(country.mines / 2)
                                            + math.floor((self.towns + self.markets) / max(1, 6 - connection[1]))
                                            + connection[1] * 3)  # Add value to AI losing from connection

                        estimated_income += -PERCEPTION_VALUE * self.perception[country.name]

                        if country.name not in connector_names:
                            if estimated_income >= best_cut_score:
                                if estimated_income == best_cut_score:
                                    best_cut_list = []
                                else:
                                    best_cut = (country, connection)
                                    best_cut_score = estimated_income
                                best_cut_list.append(best_cut)
                        else:
                            if estimated_income >= fallback_cut_score:
                                if estimated_income == best_cut_score:
                                    fallback_cut_list = []
                                else:
                                    fallback_cut = (country, connection)
                                    fallback_cut_score = estimated_income
                                fallback_cut_list.append(fallback_cut)

                    selected = best_cut_list[random.randint(0, len(best_cut_list) - 1)] if len(best_cut_list) else (
                        fallback_cut_list[random.randint(0, len(fallback_cut_list) - 1)])
                    if not selected:
                        return
                    target_country, selected_connection = selected

                selected_connection[2] = True
                target_country.markets = max(0, (target_country.markets - selected_connection[1]))
                self.reserve -= blockade_cost

    def remove_blockade(self, random_removal=False):  # Smart by default
        blocked = [(country, connection) for country in country_list for connection in country.connections if
                   connection[0] == self.name and connection[2]]

        if blocked:
            if random_removal:
                target_country, selected_connection = random.choice(blocked)
            else:
                connector_names = {conn[0] for conn in self.connections}
                best_blocked_score, fallback_blocked_score = float('inf'), float('-inf')
                best_blocked_list, fallback_blocked_list = [], []

                for country, connection in blocked:
                    estimated_income = (math.floor(country.mines / 2)
                                        + math.floor((self.towns + self.markets) / max(1, 6 - connection[1]))
                                        + connection[1] * 3)  # Add value to AI losing from connection

                    estimated_income += PERCEPTION_VALUE * self.perception[country.name]

                    if country.name not in connector_names:
                        if estimated_income > best_blocked_score:
                            best_blocked_score = estimated_income
                            best_blocked_list = [(country, connection)]
                        elif estimated_income == best_blocked_score:
                            best_blocked_list.append((country, connection))

                    else:
                        if estimated_income > fallback_blocked_score:
                            fallback_blocked_score = estimated_income
                            fallback_blocked_list = [(country, connection)]
                        elif estimated_income == fallback_blocked_score:
                            fallback_blocked_list.append((country, connection))

                if best_blocked_list:
                    selected = random.choice(best_blocked_list)
                elif fallback_blocked_list:
                    selected = random.choice(fallback_blocked_list)
                else:
                    return
                target_country, selected_connection = selected

            selected_connection[2] = False
            target_country.markets += selected_connection[1]

    def do_nothing(self):
        pass

    def defensive_block(self):
        incoming = 0
        for country in country_list:
            for connection in country.connections:
                if connection[0] == self.name and not connection[2]:
                    incoming += 1

        if incoming > 5 and self.reserve < 100:
            for _ in range(incoming - 4):
                self.purchase_blockade()

    def rule_based(self, turn):
        self.purchase_connection()
        if self.mines == 0:
            self.purchase_mine(turn)
        elif self.towns < 2 * self.name:
            self.purchase_town()
        else:
            self.purchase_connection()
            self.purchase_mine(turn)

    def can_afford_anything(self):
        return self.reserve >= self.power_level or self.reserve >= (3 if self.mines == 0 else 7) or self.reserve >= 3

    def get_state(self, turn):
        max_money_level = 8
        max_turn_level = 10
        turn_level_incr = 20

        money_level = min(int(max(0, self.reserve) ** (1/2) / 5) + 1, max_money_level)
        turn_level = min(turn // turn_level_incr, max_turn_level - 1) + 1

        return self.power_level, money_level, len(self.connections), turn_level

    def choose_action(self, turn):
        num_of_actions = len(self.actions)
        state = self.get_state(turn)

        if state not in q_table or len(q_table[state]) != num_of_actions:
            q_table[state] = [0] * num_of_actions

        if random.random() < epsilon:
            return random.randint(0, num_of_actions - 1)
        else:
            # lambda function loops through all the q_table values to find the highest one
            return max(range(num_of_actions), key=lambda j: q_table[state][j])

    def execute_actions(self, turn):
        while self.can_afford_anything():
            action_index = self.choose_action(turn)
            if action_index == self.actions.index(self.do_nothing):
                break
            elif action_index == self.actions.index(self.purchase_mine):
                self.purchase_mine(turn)
            else:
                self.actions[action_index]()

        self.defensive_block()

    # Q(s,a)←Q(s,a)+α⋅[r+γ⋅a′maxQ(s′,a′)−Q(s,a)]
    def q_learning(self, turn):
        num_of_actions = len(self.actions)
        old_state = self.get_state(turn)
        pre_income = self.generate_money(False)
        pre_connections = len(self.connections)

        action_index = self.choose_action(turn)
        self.execute_actions(turn)

        new_state = self.get_state(turn)
        post_income = self.generate_money(False)
        connection_gain = (len(self.connections) - pre_connections)

        reward = 10 * (post_income - pre_income) + 7 * connection_gain + 12 * self.mines

        if old_state not in q_table or len(q_table[old_state]) != num_of_actions:
            q_table[old_state] = [0] * num_of_actions
        if new_state not in q_table or len(q_table[new_state]) != num_of_actions:
            q_table[new_state] = [0] * num_of_actions

        old_value = q_table[old_state][action_index]
        future_estimate = max(q_table[new_state])
        q_table[old_state][action_index] = old_value + alpha * (reward + gamma * future_estimate - old_value)


GAMES = 100
TURNS = 100
DECAY_RATE = 0.99
highest_lte, highest_reserve, highest_income, total_reserve = 0, 0, 0, 0
try:
    for game in range(GAMES):
        country_list = []

        # Setup
        load_q_table()
        for i in range(COUNTRY_COUNT):
            country_list.append(Countries(i))

        # Game loop
        for current_turn in range(TURNS):
            for nation in country_list:
                nation.find_power_level()
                nation.generate_money()
                nation.find_perception()
                nation.q_learning(current_turn)

        epsilon = max(0.001, epsilon * DECAY_RATE)
        alpha = max(0.01, alpha * DECAY_RATE)

        print(country_list)
        print(f"Training {math.ceil(game / GAMES * 100)}% complete")
        save_q_table()

        for i in range(len(country_list)):
            total_reserve += country_list[i].reserve
            if country_list[i].reserve > highest_reserve:
                highest_reserve = country_list[i].reserve

        for i in range(len(country_list)):
            country_income = country_list[i].generate_money(False)
            if country_income > highest_income:
                highest_income = country_income

except KeyboardInterrupt:
    pass

print(q_table)
print(f'Average reserve (highest): {total_reserve / 1000} ({highest_reserve})')
print(f'Highest income per turn: {highest_income}')