# Quantum optimization algorithm using Qiskit
import os
import time
from types import SimpleNamespace

from qiskit_optimization import QuadraticProgram
from qiskit import QuantumCircuit
from qiskit_optimization.algorithms import MinimumEigenOptimizer
from qiskit.primitives import StatevectorSampler
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit.circuit.library import QAOAAnsatz
from qiskit.transpiler import Layout
from qiskit_algorithms.minimum_eigensolvers import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from pathfinding import calculate_energy, astar

def build_problem(candidate_routes):
    problem = QuadraticProgram("Warehouse Pathfinding")

    route_costs = {}

    for i, route in enumerate(candidate_routes):
        route_name = f"route_{i}"

        problem.binary_var(name=route_name)
        route_costs[route_name] = calculate_energy(route)

    problem.minimize(linear=route_costs)

    problem.linear_constraint(
        linear={
            route_name: 1
            for route_name in route_costs
        },
        sense="==",
        rhs=1,
        name="select_one_route"
    )

    return problem
def generate_candidate_routes(start=None, goal=None):
    if start is None:
        start = [11, 5]
    if goal is None:
        goal = [0, 5]
    routes = []

    # Generate the baseline route.
    baseline = astar(start, goal, stop_adjacent=False)

    if baseline is not None:
        routes.append(baseline)
    else:
        return routes

    # Generate alternative routes by avoiding cells
    # along the baseline route.
    # Keep the presentation responsive by limiting the QAOA problem to a small
    # set of diverse alternative routes.
    alternative_cells = []

    # Try blocking different cells along the baseline route.
    for cell in baseline[1:-1]:
        if cell not in alternative_cells:
            alternative_cells.append(cell)

    for cell in alternative_cells:
        alternative = astar(
            start,
            goal,
            stop_adjacent=False,
            blocked_cells=[cell]
        )

        if alternative is not None and alternative not in routes:
            routes.append(alternative)

        if len(routes) == 3:
            break

    return routes


def build_hardware_cost_operator(candidate_routes):
    route_count = len(candidate_routes)

    route_costs = [
        calculate_energy(route)
        for route in candidate_routes
    ]

    penalty = sum(abs(cost) for cost in route_costs) + 1.0

    terms = []

    for i, cost in enumerate(route_costs):
        label = ["I"] * route_count
        label[route_count - 1 - i] = "Z"

        coefficient = ((2 - route_count) * penalty - cost) / 2.0
        terms.append(("".join(label), coefficient))

    for i in range(route_count):
        for j in range(i + 1, route_count):
            label = ["I"] * route_count
            label[route_count - 1 - i] = "Z"
            label[route_count - 1 - j] = "Z"

            terms.append(("".join(label), penalty / 2.0))

    return SparsePauliOp.from_list(terms)

def build_initial_state(route_count):
    initial_state = QuantumCircuit(route_count)

    amplitudes = [0.0] * (2 ** route_count)

    for i in range(route_count):
        amplitudes[1 << i] = 1 / (route_count ** 0.5)

    initial_state.prepare_state(amplitudes, range(route_count))

    return initial_state

def build_xy_mixer(route_count):
    terms = []

    for i in range(route_count):
        for j in range(i + 1, route_count):

            xx_label = ["I"] * route_count
            yy_label = ["I"] * route_count

            xx_label[route_count - 1 - i] = "X"
            xx_label[route_count - 1 - j] = "X"

            yy_label[route_count - 1 - i] = "Y"
            yy_label[route_count - 1 - j] = "Y"

            terms.append(("".join(xx_label), 0.5))
            terms.append(("".join(yy_label), 0.5))

    return SparsePauliOp.from_list(terms)

def solve_route_problem(candidate_routes, backend="simulator"):
    if backend not in ("simulator", "hardware"):
        raise ValueError("backend must be 'simulator' or 'hardware'")

    if len(candidate_routes) == 1:
        print("Only one candidate route available. Skipping QAOA.")
        return SimpleNamespace(x=[1.0])
    
    problem = build_problem(candidate_routes)

    if backend == "hardware":
        service = QiskitRuntimeService()

        quantum_backend = service.backend("ibm_fez")

        print("Selected quantum hardware:", quantum_backend.name)
        print("Backend status:", quantum_backend.status().operational)
        print("Submitting job to real backend:", quantum_backend.name)

        route_count = len(candidate_routes)

        # Calculate the energy cost of each candidate route.
        route_costs = [
            calculate_energy(route)
            for route in candidate_routes
        ]

        # Penalty for selecting anything other than exactly one route.
        penalty = sum(abs(cost) for cost in route_costs) + 1.0

        terms = []

        # Add individual route costs and penalty contributions.
        for i, cost in enumerate(route_costs):
            label = ["I"] * route_count
            label[route_count - 1 - i] = "Z"

            coefficient = ((2 - route_count) * penalty - cost) / 2.0
            terms.append(("".join(label), coefficient))

        # Add pairwise interactions for the one-route constraint.
        for i in range(route_count):
            for j in range(i + 1, route_count):
                label = ["I"] * route_count
                label[route_count - 1 - i] = "Z"
                label[route_count - 1 - j] = "Z"

                terms.append(("".join(label), penalty / 2.0))

        cost_operator = build_hardware_cost_operator(candidate_routes)
        print("Hardware cost operator:", cost_operator)
        # Test every possible route-selection combination.
        test_results = []

        for state in range(2 ** route_count):
            bitstring = format(state, f"0{route_count}b")

            energy = Statevector.from_label(
                bitstring
            ).expectation_value(cost_operator).real

            selected_routes = [
                i for i in range(route_count)
                if (state >> i) & 1
            ]

            test_results.append((energy, selected_routes))

        best_result = min(test_results, key=lambda result: result[0])

        print("\nCost Operator Test:")
        print("Best selection:", best_result[1])
        print("Expected selection:", route_costs.index(min(route_costs)))
        # Optimize QAOA parameters locally before using IBM hardware.
        initial_state = build_initial_state(len(candidate_routes))
        xy_mixer = build_xy_mixer(len(candidate_routes))

        parameter_optimizer = QAOA(
            sampler=StatevectorSampler(),
            optimizer=COBYLA(maxiter=30),
            reps=1,
            initial_state=initial_state,
            mixer=xy_mixer,
        )

        optimization_result = parameter_optimizer.compute_minimum_eigenvalue(
            cost_operator
        )

        print("\nConstraint-Preserving QAOA Circuit:")
        print(parameter_optimizer.ansatz.draw())

        print("\nOptimized QAOA Parameters:")

        for parameter, value in optimization_result.optimal_parameters.items():
            print(f"{parameter}: {value}")

        print(
            "Optimized QAOA energy:",
            optimization_result.eigenvalue.real,
        )

        # Retrieve the optimized parameters and the ansatz used to obtain them.
        ansatz = parameter_optimizer.ansatz
        parameter_values = optimization_result.optimal_parameters

        print("QAOA circuit qubits:", ansatz.num_qubits)
        print("Available hardware qubits:", quantum_backend.num_qubits)
        layout = Layout({
            ansatz.qubits[index]: index
            for index in range(route_count)
        })

        bound_circuit = ansatz.assign_parameters(parameter_values)
        bound_circuit.measure_all()

        pass_manager = generate_preset_pass_manager(
            optimization_level=1,
            backend=quantum_backend,
            initial_layout=layout,
            seed_transpiler=42,
        )
        transpiled_circuit = pass_manager.run(bound_circuit)

        sampler = Sampler(mode=quantum_backend)
        hardware_job = sampler.run(
            [transpiled_circuit],
            shots=1024,
        )
        print(
            "IBM hardware job:",
            hardware_job.job_id(),
            "| status:",
            hardware_job.status(),
        )

        primitive_result = hardware_job.result()
        print(
            "IBM hardware job completed:",
            hardware_job.job_id(),
            "| status:",
            hardware_job.status(),
        )
        pub_result = primitive_result[0]
        data = pub_result.data
        counts = data.meas.get_counts()

        route_shots = [0] * route_count
        invalid_shots = 0

        count_width = len(next(iter(counts)))

        for bitstring, shots in counts.items():
            one_hot = []

            for route_index in range(route_count):
                char_index = count_width - 1 - route_index
                one_hot.append(
                    int(bitstring[char_index]) if char_index < count_width else 0
                )

            if sum(one_hot) != 1:
                invalid_shots += shots
                continue

            selected_index = one_hot.index(1)
            route_shots[selected_index] += shots

        if sum(route_shots) == 0:
            raise RuntimeError("Hardware returned no valid one-route bitstrings.")

        selected_index = max(
            range(route_count),
            key=lambda i: route_shots[i],
        )

        selected = [0.0] * route_count
        selected[selected_index] = 1.0

        print("\nHardware Measurement Results:")
        for i, shots in enumerate(route_shots):
            probability = shots / sum(route_shots) * 100
            print(f"Route {i}: {shots} shots ({probability:.2f}%)")

        print("Invalid shots:", invalid_shots)
        print("Selected route:", selected_index)

        return SimpleNamespace(
            x=selected,
            route_shots=route_shots,
            invalid_shots=invalid_shots,
        )

     # Test QAOA parameter optimization locally.
    cost_operator = build_hardware_cost_operator(candidate_routes)

    initial_state = build_initial_state(len(candidate_routes))
    xy_mixer = build_xy_mixer(len(candidate_routes))

    parameter_optimizer = QAOA(
    sampler=StatevectorSampler(),
    optimizer=COBYLA(maxiter=30),
    reps=1,
    initial_state=initial_state,
    mixer=xy_mixer,
)


    optimization_result = parameter_optimizer.compute_minimum_eigenvalue(
    cost_operator
)

    print("\nConstraint-Preserving QAOA Circuit:")
    print(parameter_optimizer.ansatz.draw())

    print("\nOptimized QAOA Parameters:")

    for parameter, value in optimization_result.optimal_parameters.items():
        print(f"{parameter}: {value}")

    print(
        "Optimized QAOA energy:",
        optimization_result.eigenvalue.real,
    )

    # Return the best valid route found by the optimized QAOA circuit.
    ansatz = parameter_optimizer.ansatz
    parameter_values = optimization_result.optimal_parameters

    bound_circuit = ansatz.assign_parameters(parameter_values)
    bound_circuit.measure_all()

    sampler = StatevectorSampler()
    sampler_result = sampler.run(
        [bound_circuit],
        shots=1024,
    ).result()

    counts = sampler_result[0].data.meas.get_counts()

    route_shots = [0] * len(candidate_routes)
    invalid_shots = 0

    for bitstring, shots in counts.items():
        selected = [
            i for i in range(len(candidate_routes))
            if bitstring[-1 - i] == "1"
        ]

        if len(selected) == 1:
            route_shots[selected[0]] += shots
        else:
            invalid_shots += shots

    print("\nQAOA Measurement Statistics:")

    for i, shots in enumerate(route_shots):
        print(
            f"Route {i}: {shots} shots | "
            f"Energy: {calculate_energy(candidate_routes[i]):.3f}"
        )

    print("Invalid selections:", invalid_shots)

    total_valid_shots = sum(route_shots)

    if total_valid_shots == 0:
        raise RuntimeError("No valid one-route selections were measured.")

    most_frequent_index = max(
        range(len(route_shots)),
        key=lambda i: route_shots[i]
    )

    print("Most frequently selected route:", most_frequent_index)

    print(
        "Most frequent route probability:",
        f"{route_shots[most_frequent_index] / total_valid_shots * 100:.2f}%"
    )

    best_energy = min(
    calculate_energy(route)
    for route in candidate_routes
    )

    optimal_indices = [
        i for i, route in enumerate(candidate_routes)
        if calculate_energy(route) == best_energy
    ]

    print("Classically optimal candidates:", optimal_indices)

    optimal_shots = sum(
    route_shots[i] for i in optimal_indices
    )  

    print(
        "Optimal route measurement probability:",
        f"{optimal_shots / total_valid_shots * 100:.2f}%"
    )

    selected = [0.0] * len(candidate_routes)
    selected[most_frequent_index] = 1.0

    return SimpleNamespace(
    x=selected,
    route_shots=route_shots,
    invalid_shots=invalid_shots
    )


if __name__ == "__main__":
    candidate_routes = generate_candidate_routes()

    print("\nGenerated Candidate Routes:")

    for i, route in enumerate(candidate_routes):
        print(f"Route {i}: {route}")
        print("Energy cost:", calculate_energy(route))

    if not candidate_routes:
        print("No candidate routes available.")
    else:
        print("\nTesting Hardware Cost Operator:")

        cost_operator = build_hardware_cost_operator(candidate_routes)

        test_results = []

        for state in range(2 ** len(candidate_routes)):
            bitstring = format(state, f"0{len(candidate_routes)}b")

            energy = Statevector.from_label(
                bitstring
            ).expectation_value(cost_operator).real

            selected_routes = [
                i for i in range(len(candidate_routes))
                if bitstring[-1 - i] == "1"
            ]

            test_results.append((energy, selected_routes))

        best_result = min(test_results, key=lambda result: result[0])

        expected_index = min(
            range(len(candidate_routes)),
            key=lambda i: calculate_energy(candidate_routes[i])
        )

        print("Best selection:", best_result[1])
        print("Expected selection:", [expected_index])
        print("Constraint satisfied:", len(best_result[1]) == 1)
        qaoa_runs = 30
        total_qaoa_time = 0

        optimal_probabilities = []
        correct_selections = 0

        best_energy = min(
            calculate_energy(route)
            for route in candidate_routes
        )

        optimal_indices = [
            i for i, route in enumerate(candidate_routes)
            if calculate_energy(route) == best_energy
        ]

        for run in range(qaoa_runs):
            print(f"\nQAOA Run {run + 1}/{qaoa_runs}")

            start_time = time.perf_counter()
            result = solve_route_problem(candidate_routes)
            end_time = time.perf_counter()

            total_qaoa_time += end_time - start_time

            if not hasattr(result, "route_shots"):
                print("QAOA was skipped. No measurement statistics available.")
                continue

            total_valid_shots = sum(result.route_shots)

            if total_valid_shots == 0:
                continue

            optimal_shots = sum(
                result.route_shots[i]
                for i in optimal_indices
            )

            optimal_probability = optimal_shots / total_valid_shots

            optimal_probabilities.append(optimal_probability)

            most_frequent_index = max(
                range(len(result.route_shots)),
                key=lambda i: result.route_shots[i]
            )

            if most_frequent_index in optimal_indices:
                correct_selections += 1

            print(
                f"Optimal route probability: "
                f"{optimal_probability * 100:.2f}%"
            )

        if optimal_probabilities:
            average_probability = (
                sum(optimal_probabilities) / len(optimal_probabilities)
            )

            variance = sum(
                (p - average_probability) ** 2
                for p in optimal_probabilities
            ) / len(optimal_probabilities)

            standard_deviation = variance ** 0.5

            average_time = total_qaoa_time / qaoa_runs

            print("\n========== EXPERIMENT SUMMARY ==========")
            print("Successful QAOA runs:", len(optimal_probabilities))
            print(f"Average optimal-route probability: {average_probability * 100:.2f}%")
            print(f"Standard deviation: {standard_deviation * 100:.2f}%")
            print(
                "Runs selecting an optimal route most frequently:",
                f"{correct_selections}/{len(optimal_probabilities)}"
            )
            print(f"Average execution time: {average_time:.4f} seconds")
        print("\nQuantum Optimization Result:")
        print(result)

        selected_index = next(
            (
                index
                for index, selected in enumerate(result.x)
                if selected == 1
            ),
            None
        )

        if selected_index is not None:
            print("\nSelected Quantum Route:")
            print(candidate_routes[selected_index])
            print(
                "Selected Route Energy:",
                calculate_energy(candidate_routes[selected_index])
            )