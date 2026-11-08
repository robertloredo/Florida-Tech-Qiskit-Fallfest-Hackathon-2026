import random
import sys
import time
import traceback
import threading
import csv

import pygame

import warehouse as warehouse_module
import pathfinding
from pathfinding import astar, calculate_energy
from quantum_optimizer import generate_candidate_routes, solve_route_problem


pygame.init()
font = pygame.font.SysFont("Arial", 16, bold=True)
small_font = pygame.font.SysFont("Arial", 14, bold=True)
status_font = pygame.font.SysFont("Arial", 18)
title_font = pygame.font.SysFont("Arial", 28, bold=True)
panel_font = pygame.font.SysFont("Arial", 15, bold=True)

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 840
ROWS = warehouse_module.ROWS
COLS = warehouse_module.COLS
CELL_SIZE = 20
ROBOT_SPEED = 450

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Warehouse Pathfinding: Classical A* vs Quantum QAOA")
clock = pygame.time.Clock()

CHARGING_CELLS = [[11, 5]]
START_POSITION = [11, 5]
USE_QUANTUM_HARDWARE = False
PROTECTED_CELLS = [
    *CHARGING_CELLS,
]

button_rect = pygame.Rect(20, 70, 230, 44)
regenerate_rect = pygame.Rect(270, 70, 230, 44)
generated_layouts = []
status_message = "Generate three layouts to compare both methods"
generation_in_progress = False


def reset_warehouse(layout_obstacles):
    new_grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]

    for row, col in layout_obstacles:
        new_grid[row][col] = 1

    for row, col in CHARGING_CELLS:
        new_grid[row][col] = 2

    warehouse_module.warehouse[:] = new_grid
    pathfinding.inflated_warehouse = pathfinding.inflate_obstacles(clearance=1)


def create_three_layouts():
    layouts = []
    trial_results = []
    attempts = 0
    max_attempts = 60
    candidate_cells = [
        (row, col)
        for row in range(1, 11)
        for col in range(1, 11)
        if [row, col] not in PROTECTED_CELLS
    ]

    while len(layouts) < 3 and attempts < max_attempts:
        attempts += 1
        obstacles = random.sample(candidate_cells, 10)
        reset_warehouse(obstacles)
        task_cell = random.choice(
            [
                (row, col)
                for row in range(1, 11)
                for col in range(1, 11)
                if (row, col) not in obstacles
                and [row, col] not in PROTECTED_CELLS
                and abs(row - START_POSITION[0]) + abs(col - START_POSITION[1]) >= 4
            ]
        )
        comparison_start = START_POSITION.copy()
        comparison_goal = [task_cell[0], task_cell[1]]
        print(
            f"Layout {len(layouts) + 1}: "
            f"Start = {comparison_start}, Goal = {comparison_goal}"
        )

        classical_start = time.perf_counter()
        classical_path = astar(
            comparison_start,
            comparison_goal,
            stop_adjacent=False,
        )
        classical_time = time.perf_counter() - classical_start

        if classical_path is None:
            continue

        candidate_routes = generate_candidate_routes(
            comparison_start,
            comparison_goal,
        )
        if not candidate_routes:
            continue

        quantum_start = time.perf_counter()

        try:
            print("\nNumber of candidate routes:", len(candidate_routes))

            qaoa_runs = 1 if USE_QUANTUM_HARDWARE else 1
            selected_backend = "hardware" if USE_QUANTUM_HARDWARE else "simulator"
            optimal_probabilities = []
            correct_selections = 0
            total_route_shots = [0] * len(candidate_routes)

            best_energy = min(
                calculate_energy(route)
                for route in candidate_routes
            )

            optimal_indices = [
                i for i, route in enumerate(candidate_routes)
                if abs(calculate_energy(route) - best_energy) < 1e-9
            ]

            for run in range(qaoa_runs):
                print(f"\nLayout QAOA Run {run + 1}/{qaoa_runs}")

                quantum_result = solve_route_problem(
                    candidate_routes,
                    backend=selected_backend,
                )

                if not hasattr(quantum_result, "route_shots"):
                    print("QAOA skipped. Only one candidate route.")
                    break

                route_shots = quantum_result.route_shots

                for i, shots in enumerate(route_shots):
                    total_route_shots[i] += shots

                valid_shots = sum(route_shots)

                if valid_shots == 0:
                    continue

                optimal_shots = sum(
                    route_shots[i]
                    for i in optimal_indices
                )

                optimal_probability = optimal_shots / valid_shots

                most_frequent = max(
                    range(len(route_shots)),
                    key=lambda i: route_shots[i]
                )

                is_optimal = most_frequent in optimal_indices

                trial_results.append({
                    "Layout": len(layouts) + 1,
                    "Trial": run + 1,
                    "Optimal Probability (%)": optimal_probability * 100,
                    "Most Frequent Route": most_frequent,
                    "Optimal Selection": is_optimal,
                    "Route Shots": route_shots.copy(),
                    "Invalid Shots": quantum_result.invalid_shots,
                })

                optimal_probabilities.append(optimal_probability)

                if is_optimal:
                    correct_selections += 1

            if optimal_probabilities:
                average_probability = sum(optimal_probabilities) / len(
                    optimal_probabilities
                )

                variance = sum(
                    (p - average_probability) ** 2
                    for p in optimal_probabilities
                ) / len(optimal_probabilities)

                standard_deviation = variance ** 0.5

                selection_accuracy = (
                    correct_selections / len(optimal_probabilities)
                ) * 100

                print("\n========== LAYOUT EXPERIMENT RESULTS ==========")
                print("Successful runs:", len(optimal_probabilities))

                if USE_QUANTUM_HARDWARE:
                    print(
                        f"Hardware optimal-route probability: "
                        f"{average_probability * 100:.2f}%"
                        )
                    print(
                        "Most frequent route was optimal:",
                        "Yes" if correct_selections else "No"
                    )
                else:
                    print(
                        f"Average optimal probability: "
                        f"{average_probability * 100:.2f}%"
                    )
                    print(
                        f"Standard deviation: "
                        f"{standard_deviation * 100:.2f}%"
                    )
                    print(
                        f"Optimal selection accuracy: "
                        f"{selection_accuracy:.2f}%"
                    )

                selected_index = max(
                    range(len(total_route_shots)),
                    key=lambda i: total_route_shots[i]
                )

                quantum_path = candidate_routes[selected_index]

                quantum_backend_status = (
                    "IBM Quantum Hardware"
                    if USE_QUANTUM_HARDWARE
                    else "QAOA Simulator"
                )

            else:
                if len(candidate_routes) == 1:
                    quantum_path = candidate_routes[0]
                    quantum_backend_status = "Single candidate - QAOA skipped"
                else:
                    quantum_path = None
                    quantum_backend_status = "QAOA skipped"

        except Exception as error:
            quantum_backend_status = f"QAOA error: {error}"
            print("Quantum execution failed:", type(error).__name__, str(error))
            traceback.print_exc()
            quantum_path = None

        quantum_time = time.perf_counter() - quantum_start

        layouts.append(
            {
                "obstacles": obstacles,
                "start": comparison_start.copy(),
                "goal": comparison_goal,
                "classical_path": classical_path,
                "quantum_path": quantum_path,
                "classical_energy": calculate_energy(classical_path),
                "quantum_energy": (
                    calculate_energy(quantum_path)
                    if quantum_path is not None
                    else None
                ),
                "classical_time": classical_time,
                "quantum_time": quantum_time,
                "candidate_count": len(candidate_routes),
                "qaoa_runs": len(optimal_probabilities),
                "optimal_probability": (
                    average_probability * 100
                    if optimal_probabilities
                    else None
                ),
                "optimal_probability_std": (
                    standard_deviation * 100
                    if optimal_probabilities
                    else None
                ),
                "selection_accuracy": (
                    selection_accuracy
                    if optimal_probabilities
                    else None
                ),
                "classical_index": 0,
                "quantum_index": 0,
                "classical_status": "Running",
                "quantum_status": "Running",
                "quantum_backend_status": quantum_backend_status,
                "last_move_time": pygame.time.get_ticks(),
            }
        )

    print("\n========== WAREHOUSE EXPERIMENT SUMMARY ==========")

    for i, layout in enumerate(layouts):
        print(f"\nLayout {i + 1}")
        print("Candidate routes:", layout["candidate_count"])

        if layout["optimal_probability"] is not None:
            print(f"Average optimal probability: {layout['optimal_probability']:.2f}%")
            print(f"Standard deviation: {layout['optimal_probability_std']:.2f}%")
            print(f"Optimal selection accuracy: {layout['selection_accuracy']:.2f}%")
        else:
            print("QAOA statistics unavailable.")

        print(f"Classical A* time: {layout['classical_time']:.6f} seconds")
        print(f"Total QAOA time: {layout['quantum_time']:.6f} seconds")

    with open("warehouse_experiment_results.csv", "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Layout",
            "Candidate Routes",
            "QAOA Runs",
            "Average Optimal Probability (%)",
            "Standard Deviation (%)",
            "Optimal Selection Accuracy (%)",
            "Classical A* Time (seconds)",
            "Total QAOA Time (seconds)",
        ])

        for i, layout in enumerate(layouts):
            writer.writerow([
                i + 1,
                layout["candidate_count"],
                layout["qaoa_runs"],
                layout["optimal_probability"],
                layout["optimal_probability_std"],
                layout["selection_accuracy"],
                layout["classical_time"],
                layout["quantum_time"],
            ])

    print("\nExperiment results saved to warehouse_experiment_results.csv")
    with open("warehouse_trial_results.csv", "w", newline="") as file:
        fieldnames = [
            "Layout",
            "Trial",
            "Optimal Probability (%)",
            "Most Frequent Route",
            "Optimal Selection",
            "Route Shots",
            "Invalid Shots",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()

        for trial in trial_results:
            writer.writerow(trial)

        print("Individual trial results saved to warehouse_trial_results.csv")

        return layouts


def generate_layouts():
    global generated_layouts, status_message, generation_in_progress

    if generation_in_progress:
        return

    generation_in_progress = True
    generated_layouts = []
    status_message = "Generating and solving three random layouts..."

    def worker():
        global generated_layouts, status_message, generation_in_progress

        try:
            new_layouts = create_three_layouts()
            generated_layouts = new_layouts
            if generated_layouts:
                status_message = (
                    "Three layouts solved: follow the blue A* and orange QAOA routes"
                )
            else:
                status_message = (
                    "Could not generate three valid layouts. Click regenerate"
                )
        except Exception as error:
            generated_layouts = []
            status_message = f"Generation stopped safely: {error}"
            print("Layout generation error:")
            traceback.print_exc()
        finally:
            generation_in_progress = False

    threading.Thread(target=worker, daemon=True, name="layout-generation").start()


def panel_origin(index):
    return (20 + index * 390, 150)


def advance_layout(layout):
    current_time = pygame.time.get_ticks()
    if current_time - layout["last_move_time"] < ROBOT_SPEED:
        return

    layout["last_move_time"] = current_time

    classical_path = layout["classical_path"]
    if layout["classical_index"] < len(classical_path) - 1:
        layout["classical_index"] += 1
    else:
        layout["classical_status"] = "Arrived"

    quantum_path = layout["quantum_path"]
    if quantum_path is None:
        layout["quantum_status"] = "Not executed"
        return
    if layout["quantum_index"] < len(quantum_path) - 1:
        layout["quantum_index"] += 1
    else:
        layout["quantum_status"] = "Arrived"


def draw_panel(layout, index):
    grid_x, grid_y = panel_origin(index)

    panel_rect = pygame.Rect(grid_x - 10, grid_y - 38, 370, 510)
    pygame.draw.rect(screen, (45, 45, 45), panel_rect, border_radius=12)
    pygame.draw.rect(screen, (90, 90, 90), panel_rect, 2, border_radius=12)

    title = title_font.render(
        f"Layout {index + 1}",
        True,
        (255, 255, 255),
    )
    screen.blit(title, (grid_x, grid_y - 32))

    start_row, start_col = layout["start"]
    start_label = font.render("CHARGER", True, (255, 255, 255))
    start_center = (
        grid_x + start_col * CELL_SIZE + CELL_SIZE // 2,
        grid_y + start_row * CELL_SIZE + CELL_SIZE // 2,
    )
    start_rect = start_label.get_rect(center=(start_center[0], start_center[1] - 14))
    pygame.draw.circle(screen, (255, 255, 255), start_center, 8, 2)
    screen.blit(start_label, start_rect)

    for row in range(ROWS):
        for col in range(COLS):
            x = grid_x + col * CELL_SIZE
            y = grid_y + row * CELL_SIZE
            rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

            if (row, col) in layout["obstacles"]:
                color = (70, 70, 70)
            elif [row, col] in CHARGING_CELLS:
                color = (40, 180, 100)
            else:
                color = (220, 220, 220)

            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (100, 100, 100), rect, 1)

    draw_route(
        layout["classical_path"],
        grid_x,
        grid_y,
        (30, 100, 255),
        layout["classical_index"],
        -4,
    )
    if layout["quantum_path"] is not None:
        draw_route(
            layout["quantum_path"],
            grid_x,
            grid_y,
            (255, 140, 30),
            layout["quantum_index"],
            4,
        )

    goal_row, goal_col = layout["goal"]
    goal_center = (
        grid_x + goal_col * CELL_SIZE + CELL_SIZE // 2,
        grid_y + goal_row * CELL_SIZE + CELL_SIZE // 2,
    )
    pygame.draw.circle(screen, (20, 180, 40), goal_center, 8, 3)
    task_label = font.render("TASK", True, (255, 255, 255))
    task_rect = task_label.get_rect(center=(goal_center[0], goal_center[1] - 14))
    screen.blit(task_label, task_rect)

    draw_layout_metrics(layout, index, grid_x, grid_y)


def draw_route(path, grid_x, grid_y, color, current_index, offset):
    points = [
        (
            grid_x + col * CELL_SIZE + CELL_SIZE // 2 + offset,
            grid_y + row * CELL_SIZE + CELL_SIZE // 2 + offset,
        )
        for row, col in path
    ]

    if len(points) > 1:
        pygame.draw.lines(screen, color, False, points, 3)

    if current_index < len(path):
        row, col = path[current_index]
        center = (
            grid_x + col * CELL_SIZE + CELL_SIZE // 2 + offset,
            grid_y + row * CELL_SIZE + CELL_SIZE // 2 + offset,
        )
        pygame.draw.circle(screen, color, center, 7)
        pygame.draw.circle(screen, (255, 255, 255), center, 7, 2)


def draw_layout_metrics(layout, index, grid_x, grid_y):
    metric_y = grid_y + 250

    quantum_energy_text = (
        f"{layout['quantum_energy']:.3f} energy"
        if layout["quantum_energy"] is not None
        else "No hardware result"
    )

    metrics = [
        (
            (30, 100, 255),
            "A* CLASSICAL",
            f"{layout['classical_energy']:.3f} energy  |  "
            f"{layout['classical_time']:.4f} s  |  {layout['classical_status']}",
        ),
        (
            (255, 140, 30),
            "QAOA QUANTUM",
            f"{quantum_energy_text}  |  "
            f"{layout['quantum_time']:.4f} s  |  {layout['quantum_status']}",
        ),
    ]

    for color, heading, details in metrics:
        card = pygame.Rect(grid_x + 5, metric_y, 350, 62)
        pygame.draw.rect(screen, (60, 60, 60), card, border_radius=8)
        pygame.draw.rect(screen, color, card, 2, border_radius=8)
        heading_label = panel_font.render(heading, True, color)
        details_label = small_font.render(details, True, (255, 255, 255))
        screen.blit(heading_label, (grid_x + 16, metric_y + 8))
        screen.blit(details_label, (grid_x + 16, metric_y + 34))
        metric_y += 68

    if layout["quantum_energy"] is None:
        verdict = "Quantum hardware not confirmed"
    elif layout["classical_energy"] < layout["quantum_energy"]:
        verdict = "A* lower energy"
    elif layout["quantum_energy"] < layout["classical_energy"]:
        verdict = "QAOA lower energy"
    else:
        verdict = "Equal route energy"

    verdict_rect = pygame.Rect(grid_x + 5, metric_y - 8, 350, 38)
    pygame.draw.rect(screen, (75, 75, 75), verdict_rect, border_radius=8)
    verdict_label = panel_font.render(verdict, True, (255, 255, 255))
    screen.blit(verdict_label, verdict_label.get_rect(center=verdict_rect.center))


def draw_button(rect, text, active=True):
    color = (35, 120, 190) if active else (70, 70, 70)
    pygame.draw.rect(screen, color, rect, border_radius=10)
    pygame.draw.rect(screen, (120, 190, 230), rect, 2, border_radius=10)
    label = panel_font.render(text, True, (255, 255, 255))
    screen.blit(label, label.get_rect(center=rect.center))


def draw_time_and_energy_explanation():
    card = pygame.Rect(20, 790, 1160, 38)
    pygame.draw.rect(screen, (45, 45, 45), card, border_radius=8)
    explanation = (
        "TIME = computation seconds   |   ENERGY = 1 straight  +  1.414 diagonal  +  0.5 per turn"
    )
    label = panel_font.render(explanation, True, (235, 235, 235))
    screen.blit(label, label.get_rect(center=card.center))


reset_warehouse([])
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if button_rect.collidepoint(event.pos):
                generate_layouts()
            elif regenerate_rect.collidepoint(event.pos):
                generate_layouts()

    if generated_layouts:
        for layout in generated_layouts:
            advance_layout(layout)

    screen.fill((30, 30, 30))
    title = title_font.render(
        "Classical A* vs QAOA Quantum Route Optimization",
        True,
        (255, 255, 255),
    )
    screen.blit(title, (20, 20))
    draw_button(button_rect, "Generate 3 Random Layouts")
    draw_button(regenerate_rect, "Regenerate Layouts")

    status = status_font.render(status_message, True, (220, 220, 220))
    screen.blit(status, (520, 82))

    legend_y = 745
    legend_card = pygame.Rect(20, 720, 1160, 58)
    pygame.draw.rect(screen, (45, 45, 45), legend_card, border_radius=10)

    pygame.draw.circle(screen, (30, 100, 255), (55, legend_y), 11)
    screen.blit(panel_font.render("A* Classical Robot", True, (255, 255, 255)), (75, legend_y - 11))
    pygame.draw.circle(screen, (255, 140, 30), (310, legend_y), 11)
    screen.blit(panel_font.render("QAOA Quantum Robot", True, (255, 255, 255)), (330, legend_y - 11))
    pygame.draw.circle(screen, (40, 180, 100), (575, legend_y), 13)
    pygame.draw.circle(screen, (255, 255, 255), (575, legend_y), 13, 2)
    screen.blit(panel_font.render("Charging Start", True, (255, 255, 255)), (598, legend_y - 11))
    pygame.draw.circle(screen, (20, 180, 40), (805, legend_y), 11, 3)
    screen.blit(panel_font.render("Random Task", True, (255, 255, 255)), (825, legend_y - 11))

    if generated_layouts:
        for index, layout in enumerate(generated_layouts):
            draw_panel(layout, index)

    draw_time_and_energy_explanation()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
