# Classical pathfinding algorithms
from warehouse import warehouse, ROWS, COLS
import time

TURN_PENALTY = 0.5
BATTERY_CAPACITY = 10
BATTERY_RESERVE = 0.20

def inflate_obstacles(clearance=1):

    # Make a copy of the original warehouse
    inflated_grid = [row.copy() for row in warehouse]

    # Find every original obstacle
    for row in range(ROWS):
        for col in range(COLS):

            if warehouse[row][col] == 1:

                # Expand the obstacle in every direction
                for row_offset in range(-clearance, clearance + 1):
                    for col_offset in range(-clearance, clearance + 1):

                        new_row = row + row_offset
                        new_col = col + col_offset

                        # Make sure the position is inside the warehouse
                        if 0 <= new_row < ROWS and 0 <= new_col < COLS:
                            inflated_grid[new_row][new_col] = 1

    return inflated_grid

def find_charging_stations():
    stations = []

    for row in range(ROWS):
        for col in range(COLS):
            if warehouse[row][col] == 2:
                stations.append([row, col])

    return stations

def find_best_charging_station(start):
    stations = find_charging_stations()

    best_station = None
    lowest_energy = float("inf")
    best_path = None

    for station in stations:
        path = astar(start, station, stop_adjacent=False)

        if path is not None:
            energy = calculate_energy(path)

            if energy < lowest_energy:
                lowest_energy = energy
                best_station = station
                best_path = path

    return best_station, best_path, lowest_energy

def decide_next_destination(start, goal):
    path = astar(start, goal)

    if path is None:
        print("No valid route to destination.")
        return

    energy_needed = calculate_energy(path)

    if check_battery(energy_needed):
        print("Battery sufficient. Proceeding to destination.")
        return

    print("Battery insufficient. Finding charging station...")

    station, charging_path, charging_energy = find_best_charging_station(start)

    available_energy = BATTERY_CAPACITY * (1 - BATTERY_RESERVE)

    if station is not None and charging_energy <= available_energy:
        print("Redirecting to charging station:", station)
        print("Charging route:", charging_path)
    else:
        print("No charging station is safely reachable.")

def calculate_octile_distance(current_position, goal_position):
    row_distance = abs(current_position[0] - goal_position[0])
    col_distance = abs(current_position[1] - goal_position[1])

    diagonal_moves = min(row_distance, col_distance)
    straight_moves = max(row_distance, col_distance) - diagonal_moves
    return (diagonal_moves * 1.414 + straight_moves)


def get_neighbors(position, blocked_cells=None):
    row = position[0]
    col = position[1]

    if blocked_cells is None:
        blocked_cells = []
    neighbors = [
        ([row - 1, col], "up"), 
        ([row + 1, col], "down"),
        ([row, col - 1], "left"),
        ([row, col + 1], "right"), 

        #DIAGONALS
        ([row - 1, col - 1], "up-left"), 
        ([row - 1, col + 1], "up-right"), 
        ([row + 1, col - 1], "down-left"), 
        ([row + 1, col + 1], "down-right")  
    ]

    valid_neighbors = []

    for neighbor, direction in neighbors:
        new_row = neighbor[0]
        new_col = neighbor[1]

        if new_row < 0 or new_row >= ROWS:
            continue

        if new_col < 0 or new_col >= COLS:
            continue

        if inflated_warehouse[new_row][new_col] == 1:
            continue
        if neighbor in blocked_cells:
            continue
        # Prevent diagnol movement too close to obstacle edges
        if new_row != row and new_col != col:

            if (
                inflated_warehouse[row][new_col] == 1
                or inflated_warehouse[new_row][col] == 1
                or [row, new_col] in blocked_cells
                or [new_row, col] in blocked_cells
            ):
                continue
        valid_neighbors.append((neighbor, direction))

    return valid_neighbors

def calculate_energy(path):
    total_energy = 0
    previous_direction = None

    for i in range(len(path) - 1):
        current = path[i]
        next_position = path[i + 1]

        row_change = next_position[0] - current[0]
        col_change = next_position[1] - current[1]

        # Calculate movement energy
        if abs(row_change) == 1 and abs(col_change) == 1:
            total_energy += 1.414
        else:
            total_energy += 1.0

        # Determine movement direction
        current_direction = (
            row_change,
            col_change
        )

        # Add energy when direction changes
        if previous_direction is not None:
            if current_direction != previous_direction:
                total_energy += TURN_PENALTY

        previous_direction = current_direction

    return total_energy

def calculate_remaining_battery(energy_used):
    remaining_battery = BATTERY_CAPACITY - energy_used

    if remaining_battery < 0:
        return 0

    return remaining_battery

def calculate_battery_percentage(remaining_battery):
    return (remaining_battery / BATTERY_CAPACITY) * 100

def check_battery(energy_used):
    minimum_battery = BATTERY_CAPACITY * BATTERY_RESERVE
    available_energy = BATTERY_CAPACITY - minimum_battery

    if energy_used <= available_energy:
        return True
    else:
        return False
    
def reconstruct_path(came_from, current):
    path = [current]

    while current in came_from:
        current = came_from[current]
        path.append(current)

    path.reverse()

    return [[position[0], position[1]] for position in path]


def astar(start, goal, stop_adjacent=False, blocked_cells=None):
    if blocked_cells is None:
        blocked_cells = []
    start_state = (start[0], start[1], None)

    open_list = [start_state]

    came_from = {}

    g_score = {start_state: 0}

    f_score = {
        start_state: calculate_octile_distance(start, goal)
    }

    while open_list:
        current = min(open_list, key=lambda state: f_score[state])

        if [current[0], current[1]] == goal:
            return reconstruct_path(came_from, current)

        if (
            stop_adjacent and abs(current[0] - goal[0]) + abs(current[1] - goal[1]) == 1
        ):
            return reconstruct_path(came_from, current)

        open_list.remove(current)

        current_position = [current[0], current[1]]
        previous_direction = current[2]

        for neighbor, direction in get_neighbors(current_position, blocked_cells):
            neighbor_row = neighbor[0]
            neighbor_col = neighbor[1]

            neighbor_state = (neighbor_row, neighbor_col, direction)

            if neighbor_row != current[0] and neighbor_col != current[1]:
                move_cost = 1.414  # Diagonal movement
            else:
                move_cost = 1      # Straight movement

            turn_cost = 0

            if previous_direction is not None and previous_direction != direction:
                turn_cost = TURN_PENALTY
            tentative_g_score = g_score[current] + move_cost + turn_cost

            if neighbor_state not in g_score or tentative_g_score < g_score[neighbor_state]:

                came_from[neighbor_state] = current

                g_score[neighbor_state] = tentative_g_score

                f_score[neighbor_state] = tentative_g_score + calculate_octile_distance(neighbor, goal)

                if neighbor_state not in open_list:
                    open_list.append(neighbor_state)

    return None
def display_path(path, goal):

    # Create a copy of the warehouse
    display_grid = [row.copy() for row in inflated_warehouse]

    # Mark the path
    for position in path:
        row = position[0]
        col = position[1]

        if display_grid[row][col] == 0:
            display_grid[row][col] = 3

    # Mark starting position and destination
    start_row, start_col = path[0]
    goal_row, goal_col = goal

    display_grid[start_row][start_col] = 4
    display_grid[goal_row][goal_col] = 5


    #print column numbers
    print("   ", end="")
    for col in range(COLS):
        print(f"{col:2}", end=" ")
    print()

    # Print warehouse
    for row_number, row in enumerate(display_grid):
        print(f"{row_number:2} ", end="")

        for cell in row:
            if cell == 0:
                print(" . ", end="")
            elif cell == 1:
                print(" # ", end="")
            elif cell == 2:
                print(" C ", end="")
            elif cell == 3:
                print(" * ", end="")
            elif cell == 4:
                print(" S ", end="")
            elif cell == 5:
                print(" G ", end="")
            else:
                print(f" {cell} ", end="")

        print()
inflated_warehouse = inflate_obstacles()
if __name__ == "__main__":
    print("Robot 1 start/goal:", [10, 5], [0, 5])
    print("Robot 2 start/goal:", [10, 8], [0, 8])
    print("\nInflated Warehouse:")

    for row in inflated_warehouse:
        for cell in row:
            if cell == 0:
                print(". ", end="")
            elif cell == 1:
                print("# ", end="")
            elif cell == 2:
                print("C ", end="")
        print()
    robots = [
        {
            "id": 1,
            "start": [10, 5],
            "goal": [0, 5]
        },
        {
            "id": 2,
            "start": [10, 8],
            "goal": [0, 8]
        }
    ]

    for robot in robots:
        start = robot["start"]
        goal = robot["goal"]

        print(f"\n--- Robot {robot['id']} ---")

        runs = 100
        total_time = 0
        for _ in range(runs):
            start_time = time.perf_counter()
            path = astar(start, goal, stop_adjacent=False)
            end_time = time.perf_counter()

            total_time += end_time - start_time

        execution_time = total_time / runs

        if path is not None:
            print(f"Execution time: {execution_time:.8f} seconds")

            energy_used = calculate_energy(path)
            print("Path energy cost:", energy_used)
            remaining_battery = calculate_remaining_battery(energy_used)

            decide_next_destination(start, goal)

            print("Remaining battery:", remaining_battery)
            battery_percentage = calculate_battery_percentage(remaining_battery)
            print("Battery remaining:", battery_percentage, "%")

            best_station, charging_path, charging_energy = find_best_charging_station(start)

            print("Best charging station:", best_station)
            print("Charging route:", charging_path)
            print("Energy to charging station:", charging_energy)

            battery_ok = check_battery(energy_used)

            if battery_ok:
                print("Battery status: Sufficient")
            else:
                print("Battery status: Insufficient - recharge required")

            display_path(path, goal)

        else:
            print("\nNo valid path found.")
    test_path = astar(
    [5, 4],
    [5, 9],
    stop_adjacent=False,
    blocked_cells=[[4, 4], [3, 4]]
    )

    print("Test path with temporary obstacles:", test_path)
    reroute_test = astar(
    [2, 6],
    [3, 3],
    stop_adjacent=False,
    blocked_cells=[[2, 5]]
    )

    print("Robot 2 alternate route:", reroute_test) 