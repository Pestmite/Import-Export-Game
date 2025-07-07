import random
import math
import json
import ast

COUNTRY_COUNT = 10
NUM_OF_ACTIONS = 7
country_list = []
power_levels = [0, 5, 10, 16]
max_connections = [0, 1, 3, 5]

q_table = {}
epsilon = 0.01  # chance of mutation
alpha = 0.2  # learning rate
gamma = 0.7  # discount factor


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

    def purchase_mine(self):
        mine_cost = 7
        first_mine_cost = 3

        cost = first_mine_cost if self.mines == 0 else mine_cost

        if self.reserve >= cost:
            self.reserve -= cost
            self.mines += 1

    def purchase_town(self):
        town_cost = self.power_level

        if self.reserve >= town_cost:
            self.reserve -= town_cost
            self.towns += 1

    def purchase_connection(self, import_index=-1):
        max_connection_level = 3
        first_connection_cost = 3

        importer = random.choice([j for j in range(COUNTRY_COUNT) if j != self.name]) if import_index < 0 else import_index
        connection_found = False
        connection_level = 1
        found_connection = None

        for connection in self.connections:
            if connection[0] == country_list[importer].name:
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

    def remove_connection(self, import_index=-1):
        if not self.connections:
            return
        else:
            if import_index == -1:
                self.connections.pop(random.randint(0, len(self.connections) - 1))
            else:
                self.connections = [c for c in self.connections if c[0] != import_index]

    def purchase_blockade(self, import_index=-1):
        blockade_cost = 3
        imports = []

        if self.reserve >= blockade_cost:
            for other_country in country_list:
                for connection in other_country.connections:
                    if connection[0] == self.name and not connection[2]:
                        imports.append((other_country, connection))

            if imports:
                target_country, selected_connection = random.choice(imports) if import_index < 0 else imports[import_index]
                selected_connection[2] = True
                target_country.markets = max(0, (target_country.markets - selected_connection[1]))
                self.reserve -= blockade_cost

    def remove_blockade(self, import_index=-1):
        blocked = [
            (other_country, connection)
            for other_country in country_list
            for connection in other_country.connections
            if connection[0] == self.name and connection[2]]

        if blocked:
            target_country, selected_connection = random.choice(blocked) if import_index < 0 else blocked[import_index]
            selected_connection[2] = False
            target_country.markets += selected_connection[1]

    def do_nothing(self):
        pass

    def rule_based(self):
        self.purchase_connection()
        if self.mines == 0:
            self.purchase_mine()
        elif self.towns < 2 * self.name:
            self.purchase_town()
        else:
            self.purchase_connection()
            self.purchase_mine()

    def can_afford_anything(self):
        return (
            self.reserve >= self.power_level or
            self.reserve >= (3 if self.mines == 0 else 7) or
            self.reserve >= 3)

    def get_state(self):
        max_mine_level = 10
        mine_level_incr = 5
        max_money_level = 5
        money_level_incr = 25

        mine_level = min(self.mines // mine_level_incr, max_mine_level - 1) + 1
        money_level = min(self.reserve // money_level_incr, max_money_level - 1) + 1

        return self.power_level, mine_level, money_level, len(self.connections)

    def choose_action(self):
        state = self.get_state()

        if state not in q_table or len(q_table[state]) != NUM_OF_ACTIONS:
            q_table[state] = [0] * NUM_OF_ACTIONS

        if random.random() < epsilon:
            return random.randint(0, NUM_OF_ACTIONS - 1)
        else:
            # lambda function loops through all the q_table values to find the highest one
            return max(range(NUM_OF_ACTIONS), key=lambda j: q_table[state][j])

    def execute_actions(self):
        actions = (self.purchase_mine, self.purchase_town, self.purchase_connection, self.purchase_blockade,
                   self.remove_connection, self.remove_blockade, self.do_nothing)
        while self.can_afford_anything():
            action_index = self.choose_action()

            if action_index == 2:
                reward = [-1, None]

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
                        reward = [value, importer.name] if value > reward[0] else reward

                if reward[0] > 0:
                    self.purchase_connection(reward[1])

            elif action_index == 6:
                break
            else:
                actions[action_index]()

    # Q(s,a)←Q(s,a)+α⋅[r+γ⋅a′maxQ(s′,a′)−Q(s,a)]
    def q_learning(self):
        old_state = self.get_state()

        pre_income = self.generate_money(False)
        action_index = self.choose_action()

        self.execute_actions()

        new_state = self.get_state()

        post_income = self.generate_money(False)
        reward = (post_income - pre_income) + len(self.connections) * 10 + self.mines

        if old_state not in q_table or len(q_table[old_state]) != NUM_OF_ACTIONS:
            q_table[old_state] = [0] * NUM_OF_ACTIONS
        if new_state not in q_table or len(q_table[new_state]) != NUM_OF_ACTIONS:
            q_table[new_state] = [0] * NUM_OF_ACTIONS

        old_value = q_table[old_state][action_index]
        future_estimate = max(q_table[new_state])
        q_table[old_state][action_index] = old_value + alpha * (
            reward + gamma * future_estimate - old_value
        )


games = 100
highest_lte = 0
highest_reserve = 0
for game in range(games):
    country_list = []

    # Setup
    load_q_table()
    for i in range(COUNTRY_COUNT):
        country_list.append(Countries(i))

    # Game loop
    for _ in range(100):
        for country in country_list:
            country.find_power_level()
            country.generate_money()
            country.q_learning()

    epsilon = max(0.01, epsilon * 0.99)
    alpha = max(0.01, alpha * 0.99)

    print(country_list)
    print(f"{math.ceil(game / games * 100)}% complete")
    save_q_table()

    for i in range(len(country_list)):
        if country_list[i].reserve > highest_reserve:
            highest_reserve = country_list[i].reserve

    for i in range(len(country_list)):
        if country_list[i].life_time_earning > highest_lte:
            highest_lte = country_list[i].life_time_earning

print(q_table)
print(highest_lte, highest_reserve)
