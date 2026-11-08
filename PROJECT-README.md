# Quantum-Assisted Pathfinding for Warehouse Robots

**Florida Tech Qiskit Fallfest Hackathon 2026**

**Team:** Quantum Robot Pathfinding  
**Team Members:** Owen McBean and Ian Liu

## Project Overview



## Project Structure

warehouse.py - The basic layout of the warehouse grid.

pathfinding.py - How the robot moves and takes a path to the goal using the A* method of pathfinding

quantum_optimizer.py - Uses 5 different possible paths the robot could take, converts the energy in binary values so the quantum computer can decide which path is best.

visualization.py - display the calculation and animation of three randomly generated warehouse layouts.


## How It Works

### 1. Warehouse Environment

The program generates a 12x12 grid of spaces. There are randomly generated obstacles in different spaces, and the robot is assigned a starting point at the bottom of the grid. The obstacles also have inflated boundaries around them so that the robot doesn't cut corners of them and it doesn't get to close to an obstacle.

### 2. Classical Pathfinding (A*)

The robot uses the A* pathfinding algorithm to generate possible routes through the warehouse while avoiding obstacles. It evaluates each position using:
-G-cost: Distance traveled from the starting position.
-H-cost (Heuristic): Estimated distance remaining to the destination.
-F-cost: Combined cost used to determine which position to explore next.

### 3. Energy Calculation

Straight movement - 1 energy
Diagonal movement - sqrt(2) or 1.4 energy
Turn penalty - 0.5, used to calculate the path with the least amount of turns.

### 4. Quantum Optimization (QAOA)

A number of possible routes are given and converted into binary values. The quantum computer uses those values and determines which one is the least energy taken / best path.

### Hardware Results

| Test | Run | Binary Variables | Valid Outcomes | ValidPercentage |
|---|---|---|-------------|--------|
| 1 | 1 | 1 | 67 / 1,024  | 6.54%  |
| 1 | 2 | 2 | 535 / 1,024 | 52.25% |
| 1 | 3 | 3 | 52 / 1,024  | 5.08%  |
| 2 | 1 | 4 | 360 / 1,024 | 35.16% |
| 2 | 2 | 4 | 127 / 1,024 | 12.40% |
| 2 | 3 | 3 | 71 / 1,024  | 6.93%  |

## Installation

Install the required Python packages:


pip install -r requirements.txt

## Running the Project

Launch the visual warehouse comparison:

python visualization.py

Run the classical pathfinding tests:

python pathfinding.py

Run the quantum optimization implementation:

python quantum_optimizer.py

## Results and Limitations

### Classical A* Results

Run 1:

Layout 1: 
Energy: 9.328
Computation time: 0.0003s
Layout 2:
Energy: 11.828
Computation time: 0.0015s  
Layout 3:
Energy: 14.828
Computation time: 0.0034s 
Run 2:

Layout 1: 
Energy: 15.242
Computation time: 0.0043s  
Layout 2:
Energy: 25.570
Computation time: 0.0108s
Layout 3:
Energy: 8.414
Computation time: 0.0007s

### Quantum Results

Run 1:

Layout 1: 
Energy: 9.328
Computation time: 19.0923s
Layout 2:
Energy: 11.828
Computation time: 14.7987s  
Layout 3:
Energy: 14.828
Computation time: 15.3669s 
Run 2:

Layout 1: 
Energy: 15.242
Computation time: 19.6184s  
Layout 2:
Energy: 25.570
Computation time: 17.9714s
Layout 3:
Energy: 8.414
Computation time: 17.8090s


### Comparison

Classical (all 6 layouts):
Average energy: 14.2
Average calculation time: 0.0035 s

Quantum (all 6 layouts):
Average energy: 14.2 (same)
Average calculation time: 16.41 s

The quantum calculation took the same 
amount of energy (tiles on grid) to get to 
the goal.

Quantum calculations were slower by a factor
of 4,689 times bigger than the classical
calculation times, most likely due to long 
connectivity time to the IBM quantum 
computer.

The classical and quantum methods took
slightly different paths to reach the goal, 
however they were the same amount of 
energy used when the methods 
were compared.
