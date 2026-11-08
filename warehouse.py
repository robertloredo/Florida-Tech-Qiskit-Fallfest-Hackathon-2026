# Warehouse grid, shelves, obstacles

# warehouse size
ROWS = 12
COLS = 12

# Warehouse code grid
# 0 - open space
# 1 - obstacle
# 2 - charging station

warehouse = []

for i in range(ROWS):
    current_row = []
    for j in range(COLS):
        warehouse_grid_spot = 0
        current_row.append(warehouse_grid_spot)
    warehouse.append(current_row)

#obstacles
warehouse[4][6] = 1
warehouse[5][6] = 1
warehouse[6][7] = 1

# charging stations
warehouse[11][5] = 2
warehouse[11][6] = 2
warehouse[11][7] = 2

robot_1 = [10, 5]
robot_2 = [10, 6]
robot_3 = [10, 7]

#robot 1 position
robot_1_row = robot_1[0]
robot_1_column = robot_1[1]

#robot 2 position
robot_2_row = robot_2[0]
robot_2_column = robot_2[1]

#robot 3 position
robot_3_row = robot_3[0]
robot_3_column = robot_3[1]

robot_1_task_destination = [1, 1]
robot_2_task_destination = [8, 3]
robot_3_task_destination = [1, 10]

if __name__ == "__main__":
    print("   ", end="")
    for col in range(COLS):
        print(col, end=" ")
    print()

    # Print warehouse rows
    for row_number, row in enumerate(warehouse):
        print(f"{row_number:2} ", end="")

        for cell in row:
            if cell == 0:
                print(".", end=" ")
            elif cell == 1:
                print("#", end=" ")
            elif cell == 2:
                print("C", end=" ")

        print()
# for row in warehouse:
    #print(row)

def move_robot(robot, direction, other_robots):
    new_row = robot[0]
    new_col = robot[1]

    if direction == "up": 
        new_row -= 1
    elif direction == "down":
        new_row += 1
    elif direction == "left":
        new_col -= 1
    elif direction == "right":
        new_col += 1
    else:
        print("Invalid direction")
        return robot

    #Warehouse boundaries
    if new_row < 0 or new_row >= ROWS or new_col < 0 or new_col >= COLS:
        print("Invalid move: Outside warehouse")
        return robot

    #check obstacles
    if warehouse[new_row][new_col] == 1:
        print("Invalid move: Obstacle detected")
        return robot

    # check other robots
    if [new_row, new_col] in other_robots:
        print("Invalid move: Another robot is in the way")
        return robot

    return [new_row, new_col]
